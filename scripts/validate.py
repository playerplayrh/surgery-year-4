#!/usr/bin/env python3
"""Validate the repo. Standard library only.

    python3 scripts/validate.py                  check the working tree
    python3 scripts/validate.py --base origin/main
                                                 also compare with a base ref: merged ids and
                                                 exam set/year/rotation/numbers/stems may not
                                                 change, and new files must start ai-generated

Exit code 1 if there are errors. Warnings and notes do not fail the run.

Limits (also in README): the DDx and facts coverage checks prove nothing was skipped, not that
the meaning was kept. The identifier scan catches obvious slips only. Thai word counts are
approximate.
"""
import argparse
import datetime
import difflib
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mdutil import count_words, norm, read_text, split_front_matter, tag_lines  # noqa: E402

ALLOWED = {
    "type": {"case-note", "concept-note", "facts-note", "exam", "digest", "synthesis",
             "textbook-map", "ward-guide"},
    # Optional: where the author met it. Never used to organise content (the Gs overlap).
    # No subspecialty values on purpose: subspecialties are out of scope for now.
    "group": {"G1", "G2", "G3", "G4", "cross"},
    "source": {"bedside", "textbook", "lecture", "exam-recall", "senior-summary",
               "survival-guide", "mixed", "unknown"},
    "status": {"ai-generated", "human-verified"},
    "answer_source": {"official", "recalled", "ai-derived"},
    "exam_format": {"mcq", "meq", "osce"},
}
KNOWN_KEYS = {"id", "type", "topic", "group", "source", "author", "date", "status", "verified_by",
              "raw", "references", "digest_of", "built_from", "exam_set", "exam_format",
              "exam_year", "exam_rotation", "answer_source", "valid_year"}
CORE_KEYS = ["id", "type", "topic", "source", "author", "date", "status"]
TOPIC_OPTIONAL = {"exam", "ward-guide"}

FOLDER_TYPES = {
    "notes": {"case-note", "concept-note"},
    "facts": {"facts-note"},
    "exams": {"exam"},
    "digests": {"digest"},
    "synthesis": {"synthesis"},
    "textbook-map": {"textbook-map"},
    "ward-guide": {"ward-guide"},
}
SCAN_DIRS = ["raw", "notes", "facts", "exams", "digests", "synthesis", "textbook-map", "ward-guide"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".heic", ".webp", ".bmp", ".tif", ".tiff"}

DIGEST_MAX_WORDS = 450
NOTE_DIGEST_WORDS = 400

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
URL_RE = re.compile(r"https?://\S+")
_MONTHS = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
           r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|"
           r"มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|"
           r"พฤศจิกายน|ธันวาคม|ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|"
           r"ต\.ค\.|พ\.ย\.|ธ\.ค\.)")
ID_PATTERNS = [
    # a run of only 5s is the Thai laugh ("55555"), not an identifier
    ("long digit string", re.compile(r"(?<!\d)(?!5+(?!\d))\d{6,}(?!\d)")),
    ("HN/AN number", re.compile(r"\b(?:HN|Hn|hn|AN)\s*[:.#\-]?\s*\d+")),
    ("full date", re.compile(r"(?<!\d)\d{1,2}([/.\-])\d{1,2}\1(?:\d{4}|\d{2})(?!\d)")),
    ("ISO date", re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")),
    ("date with month name", re.compile(r"(?<!\d)\d{1,2}\s*" + _MONTHS + r"\s*\d{2,4}", re.I)),
    ("phone number", re.compile(r"(?<!\d)(?:\+66|0)\d{1,2}[- ]?\d{3}[- ]?\d{4}(?!\d)")),
]

Q_HEAD = re.compile(r"^##\s+Q\s*(\d+)\s*(?:\(\s*original\s+no\.?\s*(\d+)\s*\))?\s*$", re.I)
LABEL = re.compile(r"^\*\*([^*:]+?):?\*\*:?\s*(.*)$")
OPTION = re.compile(r"^\s*([A-H])[.)]\s+(.*)$")
EXAM_LABELS = {"mcq": ("answer", "explanation"), "meq": ("answer", "explanation"),
               "osce": ("checklist", "explanation")}


class Report:
    def __init__(self):
        self.items = []  # (severity, rel, message)

    def error(self, rel, msg):
        self.items.append(("ERROR", rel, msg))

    def warn(self, rel, msg):
        self.items.append(("WARN", rel, msg))

    def note(self, rel, msg):
        self.items.append(("NOTE", rel, msg))

    def count(self, severity):
        return sum(1 for s, _, _ in self.items if s == severity)

    def print(self, checked):
        for sev, rel, msg in sorted(self.items, key=lambda i: (i[1], i[0], i[2])):
            print(f"{sev:5} {rel}: {msg}")
        print(f"\n{checked} files checked, {self.count('ERROR')} errors, "
              f"{self.count('WARN')} warnings, {self.count('NOTE')} notes")


class Rec:
    def __init__(self, rel, fm, body, fm_lines):
        self.rel, self.fm, self.body, self.fm_lines = rel, fm, body, fm_lines
        self.parts = Path(rel).parts

    @property
    def id(self):
        return self.fm.get("id", "")

    @property
    def type(self):
        return self.fm.get("type", "")


def expected_location(parts):
    top = parts[0]
    if top in ("notes", "facts", "digests", "synthesis"):
        return len(parts) == 3, parts[1]
    if top == "exams":
        return len(parts) == 3 and parts[2] == "exam.md", parts[1]
    if top == "textbook-map":
        return len(parts) == 2, Path(parts[1]).stem
    return len(parts) == 2, None  # ward-guide


def collect(root, rep):
    recs = []
    for folder in FOLDER_TYPES:
        base = root / folder
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            if p.name.startswith("_"):
                continue
            rel = p.relative_to(root).as_posix()
            try:
                text = read_text(p)
            except UnicodeDecodeError:
                rep.error(rel, "not valid UTF-8")
                continue
            fm, body, n = split_front_matter(text)
            if fm is None:
                rep.error(rel, "no front-matter block (--- ... ---) at the top")
                continue
            recs.append(Rec(rel, fm, body, n))
    return recs


def valid_date(value):
    try:
        datetime.date.fromisoformat(value)
        return True
    except ValueError:
        return False


def as_list(value):
    if isinstance(value, list):
        return value
    return [value] if value else []


def check_front_matter(rec, rep):
    fm, rel = rec.fm, rec.rel
    for key in CORE_KEYS:
        if key not in fm:
            rep.error(rel, f"front-matter field '{key}' is missing")
    for key in fm:
        if key not in KNOWN_KEYS:
            rep.warn(rel, f"unknown front-matter field '{key}'")
    for key, allowed in ALLOWED.items():
        val = fm.get(key)
        if val and val not in allowed:
            hint = ""
            if key == "group":
                hint = " (subspecialties are out of scope for now)"
            rep.error(rel, f"{key}: '{val}' is not one of {sorted(allowed)}{hint}")
    typ = rec.type
    if rec.id and not ID_RE.match(rec.id):
        rep.error(rel, f"id '{rec.id}' must be lowercase letters, digits and hyphens")
    for key in ("id", "author", "date", "status", "source", "type"):
        if key in fm and not fm[key]:
            rep.error(rel, f"front-matter field '{key}' is empty")
    if fm.get("date") and not valid_date(fm["date"]):
        rep.error(rel, f"date '{fm['date']}' is not a valid YYYY-MM-DD date")
    if typ and typ not in TOPIC_OPTIONAL and "topic" in fm and not fm["topic"]:
        rep.error(rel, "topic is empty")
    # type must match folder; topic must match folder / file name
    ok, key = expected_location(rec.parts)
    top = rec.parts[0]
    if not ok:
        rep.error(rel, "unexpected location (expected notes/<topic>/x.md, facts/<topic>/x.md, "
                       "exams/<set>/exam.md, digests/<topic>/x.md, synthesis/<topic>/x.md, "
                       "textbook-map/<topic>.md, ward-guide/x.md)")
    if typ and typ not in FOLDER_TYPES[top]:
        rep.error(rel, f"type '{typ}' does not belong in {top}/ (expected {sorted(FOLDER_TYPES[top])})")
    if ok and key and top != "exams" and fm.get("topic") and fm["topic"] != key:
        rep.error(rel, f"topic '{fm['topic']}' does not match its location '{key}'")
    # status rules
    status = fm.get("status")
    verifier = fm.get("verified_by", "")
    if status == "human-verified":
        if not verifier:
            rep.error(rel, "human-verified needs verified_by")
        elif verifier == fm.get("author"):
            rep.error(rel, "verified_by must be a second person, not the author")
    elif verifier:
        rep.warn(rel, "verified_by is filled but status is not human-verified")
    # type-specific fields
    if typ == "digest" and not fm.get("digest_of"):
        rep.error(rel, "digest needs digest_of (id of the source note)")
    if typ == "synthesis" and not as_list(fm.get("built_from")):
        rep.error(rel, "synthesis needs built_from (ids of the sources used)")
    if typ == "facts-note" and not fm.get("raw"):
        rep.error(rel, "facts-note needs raw (path of the raw file it came from)")
    if typ == "exam":
        for fld in ("exam_set", "exam_format", "exam_year", "exam_rotation", "answer_source"):
            if not fm.get(fld):
                rep.error(rel, f"exam needs {fld}")
        if ok and fm.get("exam_set") and fm["exam_set"] != key:
            rep.error(rel, f"exam_set '{fm['exam_set']}' must equal the folder name '{key}'")
        if fm.get("exam_year") and not re.fullmatch(r"\d{4}", fm["exam_year"]):
            rep.error(rel, "exam_year must be 4 digits")
    needs_year = typ == "ward-guide" or fm.get("source") in ("senior-summary", "survival-guide")
    if needs_year and not fm.get("valid_year"):
        rep.error(rel, "valid_year is required (the year this was written for)")
    if fm.get("valid_year") and not re.fullmatch(r"\d{4}|unknown", fm["valid_year"]):
        rep.error(rel, "valid_year must be 4 digits, or 'unknown' if the source does not say")


def load_topic_systems(root):
    """INDEX.md Topics: {topic: organ system heading}, or None if there is no Topics section."""
    idx = root / "INDEX.md"
    if not idx.is_file():
        return None
    text = read_text(idx)
    m = re.search(r"^## Topics\b.*?(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return None
    out, system = {}, "Other"
    for line in m.group(0).split("\n"):
        h = re.match(r"^###\s+(.+?)\s*$", line)
        if h:
            system = h.group(1)
            continue
        t = re.match(r"^[-*]\s+`([a-z0-9]+(?:-[a-z0-9]+)*)`", line)
        if t:
            out[t.group(1)] = system
    return out


def load_topics(root):
    systems = load_topic_systems(root)
    return None if systems is None else set(systems)


def near_duplicate(topic, known):
    tokens = set(topic.split("-"))
    for k in sorted(known):
        ktokens = set(k.split("-"))
        jac = len(tokens & ktokens) / len(tokens | ktokens)
        if (difflib.SequenceMatcher(None, topic, k).ratio() >= 0.8 or topic in k or k in topic
                or jac >= 0.6):
            return k
    return None


def check_topics(root, recs, rep):
    known = load_topics(root)
    if known is None:
        rep.warn("INDEX.md", "no '## Topics' section found; topic check skipped")
        return
    seen = {}
    for rec in recs:
        t = rec.fm.get("topic")
        if t and t not in known:
            seen.setdefault(t, []).append(rec.rel)
    for t, files in sorted(seen.items()):
        dup = near_duplicate(t, known)
        where = files[0] + (f" (+{len(files) - 1} more)" if len(files) > 1 else "")
        if dup:
            rep.warn(where, f"topic '{t}' is not in INDEX.md and looks like a near-duplicate of '{dup}'. "
                            "Reuse the existing topic?")
        else:
            rep.warn(where, f"topic '{t}' is not in INDEX.md. Add it to the Topics list if it is new")


def ddx_diagnoses(body):
    out, inside = [], False
    for line in body.split("\n"):
        if re.match(r"^##\s+Differential diagnosis", line, re.I):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            first = cells[0].replace("**", "").strip() if cells else ""
            if not first or set(first) <= set("-: "):
                continue
            if first.casefold() in ("diagnosis", "not stated"):
                continue
            out.append(first)
    return out


def check_digests(recs, by_id, rep):
    for rec in recs:
        if rec.type != "digest":
            continue
        rel, body = rec.rel, rec.body
        words = count_words(body)
        if words > DIGEST_MAX_WORDS:
            rep.error(rel, f"digest is {words} words (max {DIGEST_MAX_WORDS}). Use the note itself instead")
        if not re.search(r"^\s*(?:\*\*)?Left out:?(?:\*\*)?:?\s*\S", body, re.M | re.I):
            rep.error(rel, "digest has no 'Left out' line")
        src_id = rec.fm.get("digest_of", "")
        if not src_id:
            continue
        src = by_id.get(src_id)
        if src is None:
            rep.error(rel, f"digest_of '{src_id}' does not match any file id")
            continue
        if src.type not in ("case-note", "concept-note"):
            rep.error(rel, f"digest_of points to a {src.type}; only case and concept notes get digests")
            continue
        if src_id not in body:
            rep.error(rel, f"digest does not link to its note (the id '{src_id}' is not in the text)")
        if count_words(src.body) < NOTE_DIGEST_WORDS:
            rep.warn(rel, f"the note is under {NOTE_DIGEST_WORDS} words, so it needs no digest")
        if src.type == "case-note":
            text = norm(body)
            for dx in ddx_diagnoses(src.body):
                variants = {norm(dx), norm(re.sub(r"\(.*?\)", "", dx))} - {""}
                if not any(v in text for v in variants):
                    rep.error(rel, f"DDx '{dx}' from {src_id} is missing in the digest")


def check_synthesis(recs, by_id, rep):
    for rec in recs:
        if rec.type != "synthesis":
            continue
        for sid in as_list(rec.fm.get("built_from")):
            if sid not in by_id:
                rep.error(rec.rel, f"built_from '{sid}' does not match any file id")


def has_identifier(line):
    clean = URL_RE.sub(" ", line)
    return any(rx.search(clean) for _, rx in ID_PATTERNS)


def check_facts(root, recs, rep):
    groups = {}
    for rec in recs:
        # ward guides are held to the same rule when they say which raw file they came from
        if rec.type not in ("facts-note", "ward-guide") or (rec.type == "ward-guide" and not rec.fm.get("raw")):
            continue
        for ln in rec.body.split("\n"):
            if re.match(r"^\s*[-*]\s+\S", ln) and not tag_lines(ln):
                shown = "(text hidden)" if has_identifier(ln) else ln.strip()[:60]
                rep.error(rec.rel, f"fact line without a raw line tag [Lnn]: {shown}")
        raw = rec.fm.get("raw", "")
        if raw:
            groups.setdefault(Path(raw).as_posix(), []).append(rec)
    for raw, frecs in sorted(groups.items()):
        rp = root / raw
        label = ", ".join(r.rel for r in frecs)
        if not raw.startswith("raw/") or not rp.is_file():
            rep.error(label, f"raw file '{raw}' not found under raw/")
            continue
        try:
            lines = read_text(rp).split("\n")
        except UnicodeDecodeError:
            rep.error(raw, "raw file is not valid UTF-8")
            continue
        content = {i + 1: ln for i, ln in enumerate(lines) if ln.strip() and not ln.lstrip().startswith("#")}
        tagged = set()
        for r in frecs:
            tagged |= tag_lines(r.body)
        missing = sorted(set(content) - tagged)
        for n in missing[:10]:
            # never echo a line that looks like an identifier into the log
            shown = "(text hidden: looks like an identifier)" if has_identifier(content[n]) \
                else "'" + content[n].strip()[:50] + "'"
            rep.error(label, f"raw line {n} of {raw} is not accounted for: {shown}")
        if len(missing) > 10:
            rep.error(label, f"... and {len(missing) - 10} more raw lines not accounted for")
        stray = sorted(n for n in tagged if n not in content)
        if stray:
            rep.warn(label, f"tags point at blank, heading or missing lines of {raw}: "
                            + ", ".join(f"L{n}" for n in stray[:10]))


def parse_exam(body):
    questions, cur = [], None
    for line in body.split("\n"):
        m = Q_HEAD.match(line)
        if m:
            cur = {"num": int(m.group(1)), "orig": int(m.group(2)) if m.group(2) else None,
                   "stem_lines": [], "options": {}, "labels": {}, "last": None}
            questions.append(cur)
            continue
        if line.startswith("## "):
            cur = None
            continue
        if cur is None or not line.strip():
            continue
        lm = LABEL.match(line)
        if lm:
            name = lm.group(1).strip().casefold()
            cur["labels"][name] = lm.group(2).strip()
            cur["last"] = ("label", name)
            continue
        om = OPTION.match(line) if not cur["labels"] else None
        if om:
            cur["options"][om.group(1)] = om.group(2).strip()
            cur["last"] = ("opt", om.group(1))
            continue
        if cur["last"] is None:
            cur["stem_lines"].append(line.strip())
        elif cur["last"][0] == "label":
            k = cur["last"][1]
            cur["labels"][k] = (cur["labels"][k] + " " + line.strip()).strip()
        else:
            k = cur["last"][1]
            cur["options"][k] = (cur["options"][k] + " " + line.strip()).strip()
    for q in questions:
        q["stem"] = " ".join(" ".join(q["stem_lines"]).split())
    return questions


def check_exams(root, recs, rep):
    for rec in recs:
        if rec.type != "exam":
            continue
        rel, fm = rec.rel, rec.fm
        qs = parse_exam(rec.body)
        if not qs:
            rep.error(rel, "no questions found (expected '## Q<n> (original no. <n>)' headings)")
            continue
        fmt = fm.get("exam_format")
        seen = set()
        for q in qs:
            tag = f"Q{q['num']}"
            if q["num"] in seen:
                rep.error(rel, f"question number {q['num']} appears more than once in the set")
            seen.add(q["num"])
            if q["orig"] is None:
                rep.error(rel, f"{tag}: heading has no '(original no. n)'")
            elif q["orig"] != q["num"]:
                rep.error(rel, f"{tag}: question numbers are never renumbered (original no. {q['orig']})")
            if not q["stem"]:
                rep.error(rel, f"{tag}: empty stem")
            for label in EXAM_LABELS.get(fmt, ()):
                if not q["labels"].get(label):
                    rep.error(rel, f"{tag}: missing or empty '{label.capitalize()}'")
            if "guideline / source" not in q["labels"]:
                rep.warn(rel, f"{tag}: no 'Guideline / source' line (write 'not stated' if none)")
            if fmt == "mcq":
                opts = q["options"]
                if len(opts) < 4:
                    rep.error(rel, f"{tag}: needs at least 4 options (found {len(opts)})")
                m = re.match(r"^\(?([A-H])\b", q["labels"].get("answer", ""))
                if m and m.group(1) not in opts:
                    rep.error(rel, f"{tag}: answer {m.group(1)} is not one of the options")
                elif q["labels"].get("answer") and not m:
                    rep.error(rel, f"{tag}: answer must start with an option letter")
                elif m and len(opts) >= 2:
                    right = len(opts[m.group(1)])
                    others = [len(v) for k, v in opts.items() if k != m.group(1)]
                    if right > max(others):
                        rep.warn(rel, f"{tag}: the correct choice is the longest option (a giveaway)")
        # images
        img_dir = root / Path(rel).parent / "images"
        set_code = Path(rel).parts[1]
        if img_dir.is_dir():
            for p in sorted(img_dir.iterdir()):
                if not p.is_file() or p.name.startswith("."):
                    continue
                if not p.name.startswith(set_code + "-"):
                    rep.error(rel, f"image '{p.name}' must start with the set code '{set_code}-'")
                elif not re.fullmatch(re.escape(set_code) + r"-q\d{2,}-\d+\.\w+", p.name):
                    rep.warn(rel, f"image '{p.name}' should be named {set_code}-q<nn>-<k>.<ext>")


TAG_ASKS = {"diagnosis", "investigation", "management", "complication", "basic-science", "other"}
TAG_LINE = re.compile(r"^[-*]\s*Q(\d+)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*$")


def parse_tags(text):
    """exam-map/tags/<set>.md lines '- Q12 | topic | asks' -> list of (line no., q, topic, asks)."""
    out = []
    for n, line in enumerate(text.split("\n"), 1):
        m = TAG_LINE.match(line.strip())
        if m:
            out.append((n, int(m.group(1)), m.group(2), m.group(3)))
    return out


def check_exam_tags(root, recs, rep):
    """Topic tags for the exam topic map live outside the exam files, so exams stay untouched."""
    tag_dir = root / "exam-map" / "tags"
    known = load_topics(root) or set()
    exams = {rec.fm.get("exam_set"): rec for rec in recs if rec.type == "exam" and rec.fm.get("exam_set")}
    untagged = []
    for code, rec in sorted(exams.items()):
        nums = {q["num"] for q in parse_exam(rec.body)}
        f = tag_dir / f"{code}.md"
        if not f.is_file():
            if nums:
                untagged.append(code)
            continue
        rel = f.relative_to(root).as_posix()
        seen = set()
        for n, q, topic, asks in parse_tags(read_text(f)):
            where = f"{rel}:{n}"
            if q not in nums:
                rep.error(where, f"Q{q} is not a question in exams/{code}/exam.md")
            if q in seen:
                rep.error(where, f"Q{q} is tagged twice")
            seen.add(q)
            if topic not in known:
                dup = near_duplicate(topic, known) if topic else None
                rep.error(where, f"topic '{topic}' is not in INDEX.md" + (f" (did you mean '{dup}'?)" if dup else
                                 ". Add it under the right organ system in INDEX.md"))
            if asks not in TAG_ASKS:
                rep.error(where, f"asks '{asks}' must be one of {sorted(TAG_ASKS)}")
        missing = sorted(nums - seen)
        if missing:
            rep.warn(rel, f"{len(missing)} question(s) not tagged yet: "
                          + ", ".join(f"Q{q}" for q in missing[:15]) + (" ..." if len(missing) > 15 else ""))
    for f in sorted(tag_dir.glob("*.md")) if tag_dir.is_dir() else []:
        if f.stem not in exams and not f.name.startswith("_"):
            rep.error(f.relative_to(root).as_posix(), f"no exam '{f.stem}' in exams/ for these tags")
    if untagged:
        rep.note("exam-map/tags/", f"{len(untagged)} exam(s) have no topic tags yet (run /tag-exams): "
                                   + ", ".join(untagged[:8]) + (" ..." if len(untagged) > 8 else ""))


def scan_identifiers(root, rep):
    for folder in SCAN_DIRS:
        base = root / folder
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in (".md", ".txt"):
                continue
            rel = p.relative_to(root).as_posix()
            try:
                text = read_text(p)
            except UnicodeDecodeError:
                rep.warn(rel, "not UTF-8 text; identifier scan skipped")
                continue
            skip = 0 if folder == "raw" else split_front_matter(text)[2]
            for i, line in enumerate(text.split("\n")):
                if i < skip:
                    continue
                clean = URL_RE.sub(" ", line)
                for label, rx in ID_PATTERNS:
                    m = rx.search(clean)
                    if m:
                        rep.error(rel, f"line {i + 1}: possible patient identifier ({label}), "
                                       f"starts '{m.group(0)[:2]}...'. Remove it")


def flag_images(root, rep):
    textbook_images = 0
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        # .claude/ holds Claude's own worktrees (other checkouts of this repo), not content
        if ".git" in rel.parts or rel.parts[0] == ".claude" or not p.is_file() \
                or p.suffix.lower() not in IMAGE_EXTS:
            continue
        if rel.parts[0] == "textbook":
            textbook_images += 1  # one summary line instead of thousands of warnings
            continue
        rep.warn(rel.as_posix(), "image: check by eye for faces, names, labels, ID bands, HN/AN, dates")
    if textbook_images:
        rep.note("textbook/", f"{textbook_images} textbook figures; the extractor attests 'Identifiers in "
                              "image: none' for each. Spot-check some by eye")


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True)


def check_against_base(root, base, recs, rep):
    if git(root, "rev-parse", "--verify", "--quiet", base + "^{commit}").returncode != 0:
        rep.error("(git)", f"cannot resolve base ref '{base}'")
        return
    prefix = git(root, "rev-parse", "--show-prefix").stdout.decode().strip()
    ls = git(root, "ls-tree", "-r", "-z", "--name-only", base, "--", ".").stdout.decode("utf-8", "replace")
    base_files = {f for f in ls.split("\0") if f}
    current = {prefix + r.rel for r in recs}
    for f in sorted(base_files):
        rel = f[len(prefix):]
        if rel.startswith("exams/") and rel.endswith("/exam.md") and f not in current:
            rep.error(rel, "a merged exam may not be deleted or moved")
    for rec in recs:
        gpath = prefix + rec.rel
        if gpath not in base_files:
            if rec.fm.get("status") == "human-verified":
                rep.error(rec.rel, "new files must start as ai-generated; only a second person verifies later")
            continue
        shown = git(root, "show", f"{base}:{gpath}")
        if shown.returncode != 0:
            continue
        btext = shown.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
        bfm, bbody, _ = split_front_matter(btext)
        if not bfm:
            continue
        if bfm.get("id") and bfm["id"] != rec.id:
            rep.error(rec.rel, f"id changed from '{bfm['id']}' to '{rec.id}'. Ids never change after merge")
        if rec.type != "exam" or bfm.get("type") != "exam":
            continue
        for key in ("exam_set", "exam_year", "exam_rotation"):
            if bfm.get(key) and bfm[key] != rec.fm.get(key):
                rep.error(rec.rel, f"{key} changed from '{bfm[key]}' to '{rec.fm.get(key, '')}' "
                                   "(immutable after merge)")
        old = {q["num"]: q["stem"] for q in parse_exam(bbody)}
        new = {q["num"]: q["stem"] for q in parse_exam(rec.body)}
        for n, stem in sorted(old.items()):
            if n not in new:
                rep.error(rec.rel, f"Q{n} was removed from a merged exam")
            elif new[n] != stem:
                rep.error(rec.rel, f"Q{n}: the stem of a merged question was changed "
                                   "(only answer, explanation and guideline may change)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--base", help="git ref to compare against (e.g. origin/main)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    rep = Report()

    recs = collect(root, rep)
    ids = {}
    for rec in recs:
        check_front_matter(rec, rep)
        if rec.id:
            if rec.id in ids:
                rep.error(rec.rel, f"id '{rec.id}' is also used by {ids[rec.id].rel}")
            else:
                ids[rec.id] = rec
    check_topics(root, recs, rep)
    check_digests(recs, ids, rep)
    check_synthesis(recs, ids, rep)
    check_facts(root, recs, rep)
    check_exams(root, recs, rep)
    check_exam_tags(root, recs, rep)
    scan_identifiers(root, rep)
    flag_images(root, rep)
    if args.base:
        check_against_base(root, args.base, recs, rep)

    digested = {r.fm.get("digest_of") for r in recs if r.type == "digest"}
    for rec in recs:
        if rec.type in ("case-note", "concept-note") and rec.id not in digested \
                and count_words(rec.body) >= NOTE_DIGEST_WORDS:
            rep.note(rec.rel, f"over {NOTE_DIGEST_WORDS} words and has no digest yet (prompts/make-digest.md)")

    rep.print(len(recs))
    return 1 if rep.count("ERROR") else 0


if __name__ == "__main__":
    sys.exit(main())
