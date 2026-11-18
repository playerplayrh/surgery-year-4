#!/usr/bin/env python3
"""Past-exam question bank: one Google-Sheet-ready .xlsx for every organ system, built from the exams and tags.

    python3 scripts/question_bank.py build [--out DIR]     write "Past exam bank.xlsx" (upload it to Drive as a Sheet)
    python3 scripts/question_bank.py incomplete [--set CODE] [--limit N]
                                                           list questions that still need their missing choices filled
    python3 scripts/question_bank.py status                counts per paper: complete / filled in / still needing
    python3 scripts/question_bank.py check                 validate the filled-in files; exit 1 on a problem

Recalled questions often miss choices. exam-map/completed/<set>.md holds a filled-in copy of those questions
(see CLAUDE.md "Question bank"). The rules, enforced by `check`: every recalled word stays where it was (stems may only
grow, recalled choices keep their letter and text), only gaps are filled, and an answer never appears. The Sheet has a
blank "Your answer" column; the answers written by seniors in the original papers sit in "เฉลยรุ่นพี่" and always refer to
the ORIGINAL recalled choices. Text goes into the xlsx as plain strings, so no cell can be read as a formula.
Standard library only.
"""
import argparse
import collections
import datetime
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mdutil import read_text, split_front_matter  # noqa: E402
from validate import in_exam_map, load_topic_systems, parse_exam, parse_tags_full  # noqa: E402

RAW = "https://raw.githubusercontent.com/playerplayrh/surgery-year-4/main/"
BLOB = "https://github.com/playerplayrh/surgery-year-4/blob/main/"
MIN_CHOICES, MAX_CHOICES = 4, 5
NOT_RECALLED = "(not recalled)"
IMG = re.compile(r"!\[(.*?)\]\((.*?)\)")
HINTS = re.compile(r"(\bcorrect\b|\banswer\b|\bright choice\b|✓|✔|☑|\*\*|เฉลย)", re.I)
LETTERS = "ABCDEFGH"


def cohort(code):
    m = re.match(r"mdcu(\d+)", code)
    return m.group(1) if m else code


def norm(s):
    return re.sub(r"[\s\W_]+", "", s.lower())


# ---------------------------------------------------------------- data
def load_questions(root):
    systems = load_topic_systems(root) or {}
    exams = {}
    for f in sorted((root / "exams").glob("*/exam.md")):
        fm, body, _ = split_front_matter(read_text(f))
        fm = fm or {}
        code = fm.get("exam_set") or f.parent.name
        exams[code] = {"fm": fm, "q": {q["num"]: q for q in parse_exam(body)}, "path": f.relative_to(root).as_posix()}
    out = []
    for tf in sorted((root / "exam-map" / "tags").glob("*.md")):
        code = tf.stem
        if code not in exams or not in_exam_map(code):
            continue
        for _, qn, topic, asks, concept, sub, read in parse_tags_full(read_text(tf)):
            q = exams[code]["q"].get(qn)
            if not q:
                continue
            stem_lines, pics = [], []
            for ln in q["stem_lines"]:
                for m in IMG.finditer(ln):
                    pics.append(RAW + f"exams/{code}/" + m.group(2))
                ln = IMG.sub("", ln).strip()
                if ln:
                    stem_lines.append(ln)
            opts = {k: (None if v.strip() == NOT_RECALLED else v) for k, v in q["options"].items()}
            ans = re.match(r"^\(?([A-H])\b", q["labels"].get("answer", ""))
            out.append(dict(
                set=code, num=qn, cohort=cohort(code), system=systems.get(topic, "Other"), topic=topic,
                concept=concept or "not labelled yet", asks=asks, sub=sub, read=read, stem="\n".join(stem_lines),
                options=opts, key=ans.group(1) if ans else "", pics=" ".join(pics),
                link=BLOB + exams[code]["path"], ref=f"MDCU{cohort(code)} {code.split('-', 2)[1]}-{code.split('-')[-1]} Q{qn}"))
    return out


def real_options(opts):
    return {k: v for k, v in opts.items() if v}


def needs_completion(q):
    return len(real_options(q["options"])) < MIN_CHOICES


def load_completed(root, code):
    """exam-map/completed/<set>.md -> ({num: {"stem": str|None, "options": {letter: text}, "added": [letters]}}, errors)"""
    f = root / "exam-map" / "completed" / f"{code}.md"
    if not f.is_file():
        return {}, []
    res, errs, cur = {}, [], None
    for n, line in enumerate(read_text(f).split("\n"), 1):
        line = line.rstrip()
        m = re.match(r"^##\s+Q(\d+)\s*$", line)
        if m:
            cur = res.setdefault(int(m.group(1)), {"stem": None, "options": {}, "added": [], "line": n})
            continue
        if cur is None or not line.strip() or line.startswith("#"):
            continue
        if line.startswith("Stem:"):
            cur["stem"] = line[5:].strip()
        elif line.startswith("Added:"):
            cur["added"] = [x.strip() for x in line[6:].split(",") if x.strip()]
        elif re.match(r"^[A-H]\.\s", line):
            cur["options"][line[0]] = line[3:].strip()
        else:
            errs.append(f"{f.relative_to(root).as_posix()}:{n}: unexpected line '{line[:50]}'")
    return res, errs


def check_one(q, comp):
    """Problems with a filled-in question: it may only add words, never change recalled ones or hint at the answer."""
    errs = []
    if comp["stem"] is not None:
        if norm(q["stem"]) and norm(q["stem"]) not in norm(comp["stem"]):
            errs.append("the stem must still contain every recalled word (stems may only grow)")
        if HINTS.search(comp["stem"]):
            errs.append("the stem looks like it contains an answer or hint")
    orig = real_options(q["options"])
    for k, v in orig.items():
        if comp["options"].get(k, "").strip() != v.strip():
            errs.append(f"recalled choice {k} must stay exactly as recalled")
    added = sorted(k for k in comp["options"] if k not in orig)
    if sorted(comp["added"]) != added:
        errs.append(f"'Added:' says {','.join(sorted(comp['added'])) or 'nothing'} but the added letters are {','.join(added) or 'none'}")
    final = list(comp["options"].values())
    if not MIN_CHOICES <= len(final) <= max(MAX_CHOICES, len(orig)):
        errs.append(f"needs {MIN_CHOICES}-{MAX_CHOICES} choices (found {len(final)})")
    if len({norm(x) for x in final}) != len(final):
        errs.append("two choices are the same")
    for k in added:
        t = comp["options"][k]
        if not t or len(t) > 200 or HINTS.search(t):
            errs.append(f"added choice {k} is empty, too long, or looks like an answer or hint")
    if sorted(comp["options"]) != list(LETTERS[:len(comp["options"])]):
        errs.append("choice letters must run A, B, C ... without gaps")
    return errs


def merged(q, comp):
    """The question as shown in the Sheet: recalled text plus filled-in gaps, never an answer."""
    stem = (comp or {}).get("stem") or q["stem"]
    opts = dict((comp or {}).get("options") or {k: v for k, v in q["options"].items() if v})
    return stem, dict(sorted(opts.items())), sorted((comp or {}).get("added", []))


# ---------------------------------------------------------------- sheet
def paste(stem, opts):
    return stem + ("\n" + "\n".join(f"{k}. {v}" for k, v in opts.items()) if opts else "") + "\nAnswer:"


def original_text(q):
    ch = "\n".join(f"{k}. {v}" for k, v in q["options"].items() if v)
    return q["stem"] + ("\n" + ch if ch else "")


def build_rows(root):
    qs = load_questions(root)
    comps = {}
    rows = []
    for q in qs:
        if q["set"] not in comps:
            comps[q["set"]] = load_completed(root, q["set"])[0]
        comp = comps[q["set"]].get(q["num"])
        if comp and check_one(q, comp):
            comp = None                      # a filled-in copy that breaks the rules is ignored, never shown
        stem, opts, added = merged(q, comp)
        key = f"{q['key']}. {q['options'][q['key']]}" if q["key"] and q["options"].get(q["key"]) else ""
        rows.append(dict(q=q, stem=stem, opts=opts, added=added, key=key, paste=paste(stem, opts)))
    return rows


def sheets(root):
    rows = build_rows(root)
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r["q"]["system"], r["q"]["topic"], r["q"]["concept"])].append(r)

    def best(v):
        return max(v, key=lambda r: (len(r["opts"]) >= 4, len(r["stem"]) < 450, int(r["q"]["cohort"]) if r["q"]["cohort"].isdigit() else 0))

    concept_rows = []
    for (system, topic, concept), v in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], -len(kv[1]), kv[0][2])):
        ex = best(v)
        cohorts = sorted({int(r["q"]["cohort"]) for r in v if r["q"]["cohort"].isdigit()})
        asks = collections.Counter(r["q"]["asks"] for r in v).most_common(1)[0][0]
        read = collections.Counter(r["q"]["read"] for r in v if r["q"]["read"]).most_common(1)
        concept_rows.append([system, topic, concept, len(v), "MDCU " + ", ".join(map(str, cohorts)), asks, ex["paste"],
                             read[0][0] if read else "",
                             "; ".join(r["q"]["ref"] for r in sorted(v, key=lambda r: (r["q"]["cohort"], r["q"]["num"]), reverse=True)),
                             ex["q"]["pics"]])
    q_rows = []
    for r in sorted(rows, key=lambda r: (r["q"]["system"], r["q"]["topic"], r["q"]["concept"],
                                         -int(r["q"]["cohort"]) if r["q"]["cohort"].isdigit() else 0, r["q"]["num"])):
        q = r["q"]
        q_rows.append([q["system"], q["topic"], q["concept"], int(q["cohort"]) if q["cohort"].isdigit() else q["cohort"],
                       q["set"], q["num"], q["asks"], r["paste"], "", r["key"],
                       ("Yes: " + ", ".join(r["added"]) + " filled in" if r["added"] else "No"),
                       original_text(q), q["sub"], q["read"], q["pics"], q["link"]])
    c_head = ["Organ system", "Topic", "Concept", "Times asked", "Years asked", "Usually asks", "Example question (copy this)",
              "Read", "All questions", "Picture"]
    q_head = ["Organ system", "Topic", "Concept", "MDCU", "Paper", "Q", "Type", "Question (copy this)", "Your answer (fill in)",
              "เฉลยรุ่นพี่", "Completed from recall", "Original recalled wording", "What it asks", "Read", "Picture", "Source on GitHub"]
    return rows, c_head, concept_rows, q_head, q_rows


def readme_lines(n_concepts, n_questions, n_filled):
    return ["Past exam bank: every organ system",
            f"{n_questions} past General Sx MCQ questions from MDCU69-79, grouped into {n_concepts} concepts (the same point tested again, in different words).",
            "",
            "HOW TO USE (this file is a template to copy from, not to edit)",
            "- Topics tab: the list of every topic with a link to its own tab (the tabs are at the bottom of the screen).", "- Concepts tab: one row per concept. Copy the 'Example question' cell to paste a ready-made question with its choices.",
            "- All questions tab: every question, newest first. Copy the 'Question (copy this)' cell. It ends with a blank 'Answer:' line for you to fill.",
            "- 'Your answer (fill in)' is blank on purpose.",
            "- Use the filter arrows in the header row to filter by organ system, topic, concept, year (MDCU) or type.",
            "- To change something, make your own copy: File > Make a copy.",
            "",
            "READ THIS BEFORE TRUSTING ANYTHING",
            "- Questions were recalled by students after each exam, in their own words (Thai and English). They can be incomplete or wrong.",
            f"- Because recall is partial, {n_filled} questions were missing choices. They are filled in so each has 4-5 choices. 'Completed from recall' says which letters were filled in, and 'Original recalled wording' shows exactly what was recalled. The real exam may have worded them differently.",
            "- เฉลยรุ่นพี่ = the answer written by seniors in the original paper. It is NOT an official key and may be wrong. It always refers to the original recalled choices.",
            "- Concept names, question types and reading references are first-pass labels that nobody has reviewed. Check them against the textbook or your attending.",
            "- Read = Board Review note number (BR nn), then Chula Surgery 1 chapter and pages.",
            "- Pictures are links to the picture in the repo. Open the link to see the picture.",
            "",
            "SOURCE",
            "- Built automatically from https://github.com/playerplayrh/surgery-year-4 (exams, exam-map/tags and exam-map/completed). Corrections go to the repo owner, not into this file.",
            f"- Built {datetime.date.today().isoformat()}. No patient details are included."]


# ---------------------------------------------------------------- xlsx writer (plain strings only)
def col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def clean(s):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(s))


def sheet_xml(head, data, widths, wrap_cols, flt=True, links=None):
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>',
           "<cols>" + "".join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths, 1)) + "</cols>",
           "<sheetData>",
           '<row r="1">' + "".join(f'<c r="{col(i)}1" s="1" t="inlineStr"><is><t xml:space="preserve">{escape(clean(h))}</t></is></c>'
                                   for i, h in enumerate(head, 1)) + "</row>"]
    for ri, row in enumerate(data, 2):
        cells = []
        for ci, v in enumerate(row, 1):
            ref, st = f"{col(ci)}{ri}", (' s="2"' if ci in wrap_cols else "")
            if isinstance(v, int):
                cells.append(f'<c r="{ref}"{st}><v>{v}</v></c>')
            else:
                cells.append(f'<c r="{ref}"{st} t="inlineStr"><is><t xml:space="preserve">{escape(clean(v))}</t></is></c>')
        out.append(f'<row r="{ri}">' + "".join(cells) + "</row>")
    out.append("</sheetData>" + (f'<autoFilter ref="A1:{col(len(head))}{len(data) + 1}"/>' if flt else ""))
    if links:
        out.append("<hyperlinks>" + "".join(f'<hyperlink ref="{ref}" location="{escape(loc, {chr(34): "&quot;"})}" display="{escape(clean(disp), {chr(34): "&quot;"})}"/>'
                                            for ref, loc, disp in links) + "</hyperlinks>")
    out.append("</worksheet>")
    return "".join(out)


STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
          '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
          '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
          '<fill><patternFill patternType="solid"><fgColor rgb="FFD9EAD3"/></patternFill></fill></fills>'
          '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
          '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
          '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
          '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
          '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs>'
          '</styleSheet>')


def write_xlsx(path, tabs):
    tabs = [t if len(t) == 6 else t + (None,) for t in tabs]
    n = len(tabs)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, n + 1))
                   + "</Types>")
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join(f'<sheet name="{escape(t[0])}" sheetId="{i}" r:id="rId{i}"/>' for i, t in enumerate(tabs, 1)) + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, n + 1))
                   + f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr("xl/styles.xml", STYLES)
        for i, (name, head, data, widths, wrap, links) in enumerate(tabs, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(head, data, widths, wrap, flt=name != "Read me" and links is None, links=links))


# ---------------------------------------------------------------- commands
def cmd_build(root, args):
    rows, c_head, c_rows, q_head, q_rows = sheets(root)
    n_filled = sum(1 for r in rows if r["added"])
    out = Path(args.out) if args.out else root / "exam-map"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "Past exam bank.xlsx"
    q_widths = [22, 24, 40, 8, 22, 6, 12, 80, 22, 40, 20, 70, 50, 34, 40, 50]
    q_wrap = {3, 8, 10, 11, 12, 13, 14, 15, 16}
    by_topic = collections.OrderedDict()
    for r in q_rows:
        by_topic.setdefault((r[0], r[1]), []).append(r)
    names, topic_tabs, idx_rows, links = {}, [], [], []
    for (system, topic), v in by_topic.items():
        name = topic.replace("-", " ").capitalize()[:31]
        names[(system, topic)] = name
    for i, ((system, topic), v) in enumerate(by_topic.items(), 2):
        name = names[(system, topic)]
        idx_rows.append([system, topic.replace("-", " ").capitalize(), len(v), "Open tab: " + name])
        links.append((f"D{i}", f"'{name}'!A1", "Open tab: " + name))
        topic_tabs.append((name, q_head, v, q_widths, q_wrap))
    write_xlsx(path, [
        ("Read me", ["About this file"], [[x] for x in readme_lines(len(c_rows), len(q_rows), n_filled)], [130], {1}),
        ("Topics", ["Organ system", "Topic", "Questions", "Go to its tab (click)"], idx_rows, [34, 34, 10, 40], set(), links),
        ("Concepts", c_head, c_rows, [22, 24, 44, 9, 22, 14, 70, 34, 50, 40], {3, 7, 8, 9, 10}),
        ("All questions", q_head, q_rows, q_widths, q_wrap),
    ] + topic_tabs)
    print(f"{len(c_rows)} concepts, {len(q_rows)} questions ({n_filled} filled in) -> {path}")
    return 0


def cmd_incomplete(root, args):
    qs = [q for q in load_questions(root) if needs_completion(q) and (not args.set or q["set"] == args.set)]
    done = {}
    todo = []
    for q in qs:
        if q["set"] not in done:
            done[q["set"]] = load_completed(root, q["set"])[0]
        if q["num"] not in done[q["set"]]:
            todo.append(q)
    for q in todo[: args.limit or len(todo)]:
        print(f"== {q['set']} Q{q['num']} | {q['topic']} | {q['asks']}")
        print(f"   concept: {q['concept']}")
        print(f"   what it asks: {q['sub']}")
        print(f"   read: {q['read']}")
        print("   stem: " + q["stem"].replace("\n", " / "))
        for k in sorted(q["options"]):
            print(f"   {k}. {q['options'][k] or NOT_RECALLED}")
    print(f"-- {len(todo)} question(s) still to fill in" + (f" in {args.set}" if args.set else f" across {len({q['set'] for q in todo})} papers")
          + f" ({len(qs) - len(todo)} already filled in)")
    return 0


def cmd_status(root, args):
    qs = load_questions(root)
    per = collections.defaultdict(lambda: [0, 0, 0, 0])
    comps = {}
    for q in qs:
        if q["set"] not in comps:
            comps[q["set"]] = load_completed(root, q["set"])[0]
        s = per[q["set"]]
        s[0] += 1
        if not needs_completion(q):
            s[1] += 1
        elif q["num"] in comps[q["set"]] and not check_one(q, comps[q["set"]][q["num"]]):
            s[2] += 1
        else:
            s[3] += 1
    print(f"{'paper':24} {'questions':>9} {'complete':>9} {'filled in':>9} {'to do':>6}")
    for code, (n, a, b, c) in sorted(per.items()):
        print(f"{code:24} {n:>9} {a:>9} {b:>9} {c:>6}")
    t = [sum(v[i] for v in per.values()) for i in range(4)]
    print(f"{'TOTAL':24} {t[0]:>9} {t[1]:>9} {t[2]:>9} {t[3]:>6}")
    return 0


def cmd_check(root, args):
    problems = 0
    byset = collections.defaultdict(dict)
    for q in load_questions(root):
        byset[q["set"]][q["num"]] = q
    for f in sorted((root / "exam-map" / "completed").glob("*.md")) if (root / "exam-map" / "completed").is_dir() else []:
        comps, errs = load_completed(root, f.stem)
        rel = f.relative_to(root).as_posix()
        for e in errs:
            print("ERROR", e)
            problems += 1
        if f.stem not in byset:
            print(f"ERROR {rel}: no tagged exam '{f.stem}'")
            problems += 1
            continue
        for num, comp in comps.items():
            q = byset[f.stem].get(num)
            if not q:
                print(f"ERROR {rel}:{comp['line']}: Q{num} is not a question of {f.stem}")
                problems += 1
                continue
            for e in check_one(q, comp):
                print(f"ERROR {rel}:{comp['line']}: Q{num}: {e}")
                problems += 1
    print(f"{problems} problem(s)")
    return 1 if problems else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out")
    i = sub.add_parser("incomplete")
    i.add_argument("--set")
    i.add_argument("--limit", type=int)
    sub.add_parser("status")
    sub.add_parser("check")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    return {"build": cmd_build, "incomplete": cmd_incomplete, "status": cmd_status, "check": cmd_check}[args.cmd](root, args)


if __name__ == "__main__":
    sys.exit(main())
