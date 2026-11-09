#!/usr/bin/env python3
"""Compact lookup in the repo, so a chat reads only the lines it needs. Read-only, standard library only.

    python3 scripts/find.py search cholangitis [more terms] [--in textbook,exams,tags,ward,notes,lectures,all]
                                                [--any] [--max 10] [--chars 6000] [--json]
    python3 scripts/find.py topic <name>        INDEX.md topics, tagged exam questions, textbook files
    python3 scripts/find.py outline <file>      headings with line numbers
    python3 scripts/find.py read <file>:<a>-<b> [--max-lines 120]

search: case-insensitive and Unicode-normalised (Thai and English). By default every term must be in the
same section (or the same exam question); --any means any term. One line per hit:
`kind | path:line | nearest heading | snippet`. Exam hits say `set Q12`, and [student-key] when the front-matter
answer_source says so. Skipped: .claude/, .git/, images, jobs/, docs/, templates/, scripts/, tests/, raw/.
"""
import argparse
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mdutil import read_text, split_front_matter  # noqa: E402

# kind -> folders searched (kinds follow the --in values)
KINDS = {
    "textbook": ["textbook", "textbook-map"],
    "exams": ["exams"],
    "tags": ["exam-map/tags"],
    "ward": ["ward-guide"],
    "notes": ["notes", "facts", "digests", "synthesis"],
    "lectures": ["lectures"],
}
SKIP_DIRS = {".claude", ".git", "images", "jobs", "docs", "templates", "scripts", "tests", "raw", "node_modules"}
HEAD_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
EXAM_Q_RE = re.compile(r"^##[ \t]+Q(\d+)[ \t]*\(original no\. (\d+)(?:,[ \t]*topic:[ \t]*([^)]*))?\)")
PLAIN_Q_RE = re.compile(r"^\s*(?:[-*]\s*)?([A-Za-z][\w +/&-]{0,40}? Q\d+):")


def norm(text):
    return unicodedata.normalize("NFKC", text).casefold()


def kind_files(root, kind):
    for folder in KINDS[kind]:
        base = root / folder
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            rel = p.relative_to(root).parts
            if any(part in SKIP_DIRS for part in rel[:-1]):
                continue
            yield p


def short(text, n):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


# ---------------------------------------------------------------- units
def units_of(path, kind, root):
    """Yield (line_number, heading, label, text) for each searchable unit of a file."""
    text = read_text(path)
    fm, body, skipped = split_front_matter(text)
    lines = body.split("\n")
    fm = fm or {}
    set_code = path.parent.name if kind == "exams" else ""
    flag = " [student-key]" if fm.get("answer_source") == "student-key" else ""
    if kind == "tags":
        set_code = path.stem
        for i, ln in enumerate(lines, skipped + 1):
            m = re.match(r"^- (Q\d+)\b", ln)
            if m:
                yield i, "", f"{set_code} {m.group(1)}", ln.split("|", 1)[-1]
        return
    cur = None  # [line, heading, label, [lines]]
    heading = ""
    section = ""
    fence = False

    def flush():
        if cur and any(x.strip() for x in cur[3]):
            yield cur[0], cur[1], cur[2], "\n".join(cur[3])

    for i, ln in enumerate(lines, skipped + 1):
        if ln.lstrip().startswith("```"):
            fence = not fence
        h = None if fence else HEAD_RE.match(ln)
        if h:
            yield from flush()
            heading = h.group(2)
            label = ""
            if kind == "exams":
                q = EXAM_Q_RE.match(ln)
                if q:
                    label = f"{set_code} " + (f"{q.group(3).strip()} Q{q.group(2)}" if q.group(3)
                                              else f"Q{q.group(2)}") + flag
                else:
                    section = heading
            cur = [i, heading, label, [ln]]
            continue
        if cur is None:
            cur = [i, "", "", []]
        if kind == "exams" and not cur[2] and re.match(r"(?i)(repeated|unnumbered)", section) and not ln.strip():
            # plain-line questions under "Repeated question numbers" / "Unnumbered questions"
            yield from flush()
            cur = [i + 1, heading, "", []]
            continue
        cur[3].append(ln)
        if kind == "exams" and not cur[2] and re.match(r"(?i)(repeated|unnumbered)", section) and ln.strip():
            pm = PLAIN_Q_RE.match(ln)
            nm = re.search(r"\b(\d+)\.", ln) or re.search(r"\bQ?(\d+)\b", ln)
            label = f"{set_code} {pm.group(1)}" if pm else (
                f"{set_code} Q{nm.group(1)} (repeated)" if nm and section.lower().startswith("repeated")
                else f"{set_code} unnumbered")
            cur[2] = label + flag
            cur[0] = i
    yield from flush()


def run_search(root, terms, kinds, any_mode, per_kind):
    nterms = [norm(t) for t in terms]
    result = {}
    for kind in kinds:
        hits = []
        for p in kind_files(root, kind):
            rel = p.relative_to(root).as_posix()
            for line, heading, label, text in units_of(p, kind, root):
                low = norm(text)
                counts = [low.count(t) for t in nterms]
                ok = any(counts) if any_mode else all(counts)
                if not ok:
                    continue
                # first line of the unit that holds a term
                first = line
                snippet = ""
                for off, ln in enumerate(text.split("\n")):
                    nl = norm(ln)
                    pos = [nl.find(t) for t in nterms if t in nl]
                    if pos and not (HEAD_RE.match(ln) and off == 0 and len(text.split("\n")) > 1):
                        first = line + off
                        c = max(0, min(pos) - 30)
                        snippet = ln.strip()[c:c + 100]
                        if c and " " in snippet[:12]:
                            snippet = snippet.split(" ", 1)[1]
                        break
                if not snippet:
                    snippet = text.strip().split("\n")[0]
                hits.append({"kind": kind, "path": rel, "line": first, "heading": short(heading, 60),
                             "label": label, "snippet": short(snippet, 100), "score": sum(counts)})
        hits.sort(key=lambda h: (-h["score"], h["path"], h["line"]))
        result[kind] = hits
    return result


def cmd_search(root, a):
    kinds = list(KINDS) if "all" in a.in_ else [k for k in a.in_ if k in KINDS]
    bad = [k for k in a.in_ if k not in KINDS and k != "all"]
    if bad:
        sys.exit(f"unknown --in value: {', '.join(bad)} (use {', '.join(KINDS)}, all)")
    res = run_search(root, a.terms, kinds, a.any, a.max)
    if a.json:
        out = {k: {"total": len(v), "hits": v[: a.max]} for k, v in res.items()}
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    out, size, cut = [], 0, False
    summary = ", ".join(f"{k} {len(v)}" for k, v in res.items() if v) or "no hits"
    out.append(f"hits: {summary}")
    for kind, hits in res.items():
        if not hits:
            continue
        for h in hits[: a.max]:
            ref = f"{h['path']}:{h['line']}"
            line = f"{kind} | {ref} | {h['label'] or h['heading']} | {h['snippet']}"
            if size + len(line) > a.chars:
                cut = True
                break
            out.append(line)
            size += len(line) + 1
        if cut:
            break
        if len(hits) > a.max:
            out.append(f"{kind} | ... {len(hits) - a.max} more (narrow the terms or raise --max)")
    if cut:
        out.append(f"(output cut at --chars {a.chars}; counts above are complete)")
    print("\n".join(out))
    return 0


# ---------------------------------------------------------------- topic
def index_topics(root):
    """{topic: (system, description)} from INDEX.md."""
    p = root / "INDEX.md"
    topics, system, in_topics = {}, "", False
    if not p.is_file():
        return topics
    for ln in read_text(p).split("\n"):
        if ln.startswith("## "):
            in_topics = ln.strip() == "## Topics"
        elif ln.startswith("### ") and in_topics:
            system = ln[4:].strip()
        elif in_topics:
            m = re.match(r"^[-*][ \t]+`([a-z0-9-]+)`(?:[ \t]+[—-][ \t]+(.*))?$", ln)
            if m:
                topics[m.group(1)] = (system, (m.group(2) or "").strip())
    return topics


def cmd_topic(root, a):
    topics = index_topics(root)
    q = norm(a.name).strip().replace(" ", "-")
    exact = [t for t in topics if t == q]
    cands = exact or [t for t, (_, d) in topics.items() if q in t or norm(a.name) in norm(d)]
    if not cands:
        cands = difflib.get_close_matches(q, list(topics), n=5, cutoff=0.5)
    if not cands:
        print(f"no INDEX.md topic matches '{a.name}'. Try: find.py search {a.name}")
        return 0
    if len(cands) > 1:
        print(f"{len(cands)} topics match '{a.name}'; rerun with one name:")
        by_sys = {}
        for t in cands:
            by_sys.setdefault(topics[t][0], []).append(t)
        for s, ts in by_sys.items():
            print(f"{s}: {', '.join(ts)}")
        return 0
    t = cands[0]
    print(f"topic {t} ({topics[t][0]}) {topics[t][1]}".rstrip())
    tags = root / "exam-map" / "tags"
    qs = []
    if tags.is_dir():
        for p in sorted(tags.glob("*.md")):
            for ln in read_text(p).split("\n"):
                f = [x.strip() for x in ln.lstrip("- ").split("|")]
                if len(f) >= 3 and f[1] == t:
                    qs.append((p.stem, f[0], f[2], f[3] if len(f) > 3 else ""))
    if qs:
        src = {}
        for s, *_ in qs:
            fm = root / "exams" / s / "exam.md"
            if fm.is_file():
                src[s] = (split_front_matter(read_text(fm))[0] or {}).get("answer_source", "")
        print(f"exam questions tagged ({len(qs)}):")
        for s, n, asks, concept in qs:
            flag = " [student-key]" if src.get(s) == "student-key" else ""
            print(f"  {s} {n} ({asks}){flag} {short(concept, 70)}".rstrip())
    else:
        print("exam questions tagged: none")
    books = []
    for p in sorted((root / "textbook").rglob("*.md")) if (root / "textbook").is_dir() else []:
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts[:-1]):
            continue
        with p.open(encoding="utf-8") as fh:
            head = fh.read(1500)
        fm = split_front_matter(head.replace("\r\n", "\n"))[0]
        if fm and fm.get("topic") == t:
            books.append(f"{p.relative_to(root).as_posix()} (pages {fm.get('pages', '?')})")
    print(f"textbook files ({len(books)}):" if books else "textbook files: none")
    for b in books:
        print("  " + b)
    other = [d for d in ("notes", "facts", "digests", "synthesis") if (root / d / t).is_dir()]
    if other:
        print("other folders: " + ", ".join(f"{d}/{t}/" for d in other))
    return 0


# ---------------------------------------------------------------- outline / read
def inside(root, arg):
    p = (root / arg).resolve() if not Path(arg).is_absolute() else Path(arg).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        sys.exit(f"refused: {arg} is outside the repo")
    if not p.is_file():
        sys.exit(f"not a file: {arg}")
    return p


def cmd_outline(root, a):
    p = inside(root, a.file)
    fence = False
    for i, ln in enumerate(read_text(p).split("\n"), 1):
        if ln.lstrip().startswith("```"):
            fence = not fence
        if not fence:
            m = HEAD_RE.match(ln)
            if m:
                print(f"{i}: {'  ' * (len(m.group(1)) - 1)}{short(m.group(2), 90)}")
    return 0


def cmd_read(root, a):
    m = re.match(r"^(.*):(\d+)(?:-(\d+))?$", a.target)
    if not m:
        sys.exit("use find.py read <file>:<a>-<b>")
    p = inside(root, m.group(1))
    lo = max(1, int(m.group(2)))
    hi = int(m.group(3) or lo)
    if hi < lo:
        sys.exit("range end is before its start")
    lines = read_text(p).split("\n")
    stop = min(hi, lo + a.max_lines - 1, len(lines))
    for i in range(lo, stop + 1):
        print(f"{i}: {lines[i - 1]}")
    if stop < min(hi, len(lines)):
        print(f"(stopped after {a.max_lines} lines; {min(hi, len(lines)) - stop} more; use --max-lines)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("terms", nargs="+")
    s.add_argument("--in", dest="in_", default="all", type=lambda v: [x.strip() for x in v.split(",") if x.strip()])
    s.add_argument("--any", action="store_true")
    s.add_argument("--max", type=int, default=10)
    s.add_argument("--chars", type=int, default=6000)
    s.add_argument("--json", action="store_true")
    t = sub.add_parser("topic")
    t.add_argument("name")
    o = sub.add_parser("outline")
    o.add_argument("file")
    r = sub.add_parser("read")
    r.add_argument("target")
    r.add_argument("--max-lines", type=int, default=120)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    return {"search": cmd_search, "topic": cmd_topic, "outline": cmd_outline, "read": cmd_read}[a.cmd](root, a)


if __name__ == "__main__":
    sys.exit(main())
