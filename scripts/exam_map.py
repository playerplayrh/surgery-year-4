#!/usr/bin/env python3
"""Exam topic map: every topic past exams have asked, by organ system (never by G).

    python3 scripts/exam_map.py                 writes exam-map/index.html
    python3 scripts/exam_map.py --out map.html

Reads exams/<set>/exam.md (General Sx papers and every OSCE/MEQ paper; subspecialty MCQ papers
are kept apart) and the tags in exam-map/tags/<set>.md ('- Q12 | topic | asks'),
plus INDEX.md for the organ system of each topic. The map shows breadth: a topic asked once
counts as much as one asked every year. Each topic shows which cohorts and formats asked it,
how it was asked, and what the repo has for studying it. Standard library only.
"""
import argparse
import datetime
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mdutil import read_text, split_front_matter  # noqa: E402
from validate import in_exam_map, load_topic_systems, parse_exam, parse_tags  # noqa: E402

REPO_URL = "https://github.com/playerplayrh/surgery-year-4/blob/main/"
ASKS = ["diagnosis", "investigation", "management", "complication", "basic-science", "other"]
LEVELS = [  # what the repo has for a topic, weakest first
    ("exam", "Exam questions only"),
    ("textbook", "Textbook section or lecture"),
    ("notes", "Notes or facts"),
    ("verified", "Verified by a person"),
]


def topic_descriptions(root):
    text = read_text(root / "INDEX.md") if (root / "INDEX.md").is_file() else ""
    return {m.group(1): m.group(2).strip() for m in
            re.finditer(r"^[-*][ \t]+`([a-z0-9-]+)`(?:[ \t]+[—-][ \t]+([^\n]*))?$", text, re.M) if m.group(2)}


def cohort_of(fm):
    m = re.match(r"mdcu(\d+)", fm.get("exam_set", ""))
    return f"MDCU{m.group(1)}" if m else (fm.get("exam_year") or "unknown")


def readiness(root, topics):
    """Highest level the repo reaches for each topic."""
    level = {t: 0 for t in topics}
    def bump(t, n):
        if t in level:
            level[t] = max(level[t], n)
    for folder in ("textbook", "lectures", "textbook-map", "notes", "facts", "digests", "synthesis"):
        base = root / folder
        if not base.is_dir():
            continue
        for p in base.rglob("*.md"):
            fm, _, _ = split_front_matter(read_text(p))
            fm = fm or {}
            t = fm.get("topic") or (p.stem if folder == "textbook-map" else p.parent.name)
            n = 1 if folder in ("textbook", "lectures", "textbook-map") else 2
            if fm.get("status") == "human-verified":
                n = 3
            # a lecture covering several topics lists them all in `topics`
            extra = fm.get("topics") or []
            for topic in [t] + (extra if isinstance(extra, list) else [extra]):
                bump(topic, n)
    return level


def collect(root):
    systems = load_topic_systems(root) or {}
    papers, questions = [], []
    for f in sorted((root / "exams").glob("*/exam.md")):
        fm, body, _ = split_front_matter(read_text(f))
        fm = fm or {}
        code = fm.get("exam_set") or f.parent.name
        if not in_exam_map(code):
            continue  # subspecialty MCQ papers are kept apart from General Surgery
        qs = {q["num"]: q for q in parse_exam(body)}
        tf = root / "exam-map" / "tags" / f"{code}.md"
        tags = {q: (topic, asks) for _, q, topic, asks in parse_tags(read_text(tf))} if tf.is_file() else {}
        papers.append({"code": code, "total": len(qs), "tagged": len(set(tags) & set(qs)),
                       "format": fm.get("exam_format", ""), "cohort": cohort_of(fm)})
        for num, (topic, asks) in sorted(tags.items()):
            if num not in qs:
                continue
            questions.append({"set": code, "q": num, "topic": topic, "asks": asks,
                              "format": fm.get("exam_format", ""), "cohort": cohort_of(fm),
                              "stem": qs[num]["stem"], "path": f.relative_to(root).as_posix()})
    return systems, papers, questions


def render(root, systems, papers, questions):
    desc = topic_descriptions(root)
    by_topic = {}
    for q in questions:
        by_topic.setdefault(q["topic"], []).append(q)
    level = readiness(root, by_topic)
    cohorts = sorted({p["cohort"] for p in papers}, key=lambda c: (len(c), c))
    formats = sorted({p["format"] for p in papers if p["format"]})
    order = list(dict.fromkeys(systems.values()))
    grouped = {}
    for t in by_topic:
        grouped.setdefault(systems.get(t, "Other"), []).append(t)
    e = html.escape

    def tile(t):
        qs = sorted(by_topic[t], key=lambda q: (q["cohort"], q["set"], q["q"]))
        asked = {q["cohort"] for q in qs}
        dots = "".join(f'<i class="dot{" on" if c in asked else ""}" title="{e(c)}">{e(c.replace("MDCU", ""))}</i>'
                       for c in cohorts)
        chips = "".join(f'<span class="chip">{e(f)}</span>' for f in sorted({q["format"] for q in qs}))
        asks = "".join(f'<span class="chip ask">{e(a)}</span>' for a in ASKS if any(q["asks"] == a for q in qs))
        lis = "".join(
            f'<li data-cohort="{e(q["cohort"])}" data-format="{e(q["format"])}">'
            f'<a href="{REPO_URL}{e(q["path"])}" target="_blank" rel="noopener">{e(q["set"])} Q{q["q"]}</a> '
            f'<span class="ask-tag">{e(q["asks"])}</span> {e(q["stem"][:140])}{"…" if len(q["stem"]) > 140 else ""}</li>'
            for q in qs)
        lv = LEVELS[level[t]][0]
        return (f'<details class="tile lv-{lv}"><summary><span class="name">{e(t)}</span>'
                f'<span class="sub">{e(desc.get(t, ""))}</span>'
                f'<span class="dots" aria-label="cohorts that asked it">{dots}</span>'
                f'<span class="chips">{chips}{asks}</span></summary><ol>{lis}</ol></details>')

    sections = "".join(
        f'<section><h2>{e(s)}</h2><div class="grid">{"".join(tile(t) for t in sorted(grouped[s]))}</div></section>'
        for s in order + sorted(set(grouped) - set(order)) if s in grouped)
    gaps = sorted(t for t in by_topic if level[t] == 0)
    total_q = sum(p["total"] for p in papers)
    tagged_q = sum(p["tagged"] for p in papers)
    untagged = [p for p in papers if p["tagged"] < p["total"]]
    legend = "".join(f'<span class="key lv-{k}"><i></i>{e(label)}</span>' for k, label in LEVELS)
    cohort_opts = "".join(f'<option>{e(c)}</option>' for c in cohorts)
    format_opts = "".join(f'<option>{e(f)}</option>' for f in formats)
    gap_html = ("".join(f'<span class="chip">{e(t)}</span>' for t in gaps)
                if gaps else '<span class="sub">None. Every examined topic has something to study from.</span>')
    todo = ("".join(f'<li>{e(p["code"])}: {p["tagged"]} of {p["total"]} tagged</li>' for p in untagged)
            if untagged else "<li>All papers are fully tagged.</li>")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    empty = "" if by_topic else ('<p class="sub">No tagged questions yet. Tag merged papers with /tag-exams '
                                 'in Claude Code, then build the map again.</p>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Exam Topic Map</title>
<style>
:root{{--bg:#f7f8f6;--card:#fff;--fg:#1d2420;--mut:#5f6b65;--line:#dde3df;--acc:#2f6f5e;
--l0:#eef0ee;--l1:#e3ecf7;--l2:#dcefe4;--l3:#bfe3cb;--dot:#d3d9d5}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#141917;--card:#1b211e;--fg:#e5ebe7;--mut:#9eaba4;
--line:#2c3531;--acc:#79c6ae;--l0:#232a27;--l1:#1f2c3b;--l2:#1d3428;--l3:#24503a;--dot:#38423d;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#141917;--card:#1b211e;--fg:#e5ebe7;--mut:#9eaba4;--line:#2c3531;--acc:#79c6ae;
--l0:#232a27;--l1:#1f2c3b;--l2:#1d3428;--l3:#24503a;--dot:#38423d;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1150px;margin:0 auto;padding-inline:16px;padding-block:24px 48px;display:grid;gap:22px}}
h1{{font-size:24px;font-weight:600;margin:0}}h2{{font-size:17px;font-weight:600;margin:0 0 10px}}
.sub{{color:var(--mut);font-size:12.5px}}.stats{{display:flex;gap:10px;flex-wrap:wrap}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 12px}}
.stat b{{display:block;font-size:20px;font-weight:600;font-variant-numeric:tabular-nums}}
.bar{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
select{{font:inherit;padding:4px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg)}}
.legend{{display:flex;gap:12px;flex-wrap:wrap;font-size:12.5px;color:var(--mut)}}
.key i{{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-2px;border:1px solid var(--line)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}}
.tile{{border:1px solid var(--line);border-radius:10px;min-width:0}}
.tile summary{{list-style:none;cursor:pointer;padding:10px 12px;display:grid;gap:5px}}
.tile summary::-webkit-details-marker{{display:none}}
.tile[open]{{grid-column:1/-1}}.name{{font-weight:600}}
.tile.lv-exam,.key.lv-exam i{{background:var(--l0)}}.tile.lv-textbook,.key.lv-textbook i{{background:var(--l1)}}
.tile.lv-notes,.key.lv-notes i{{background:var(--l2)}}.tile.lv-verified,.key.lv-verified i{{background:var(--l3)}}
.dots{{display:flex;gap:3px;flex-wrap:wrap}}.dot{{font:600 10.5px/1 ui-monospace,Menlo,monospace;font-style:normal;padding:3px 4px;
border-radius:4px;color:var(--mut);border:1px dashed var(--dot);font-variant-numeric:tabular-nums}}
.dot.on{{background:var(--acc);border:1px solid var(--acc);color:var(--card)}}
.chips{{display:flex;gap:4px;flex-wrap:wrap}}.chip{{font-size:11.5px;padding:1px 7px;border-radius:999px;border:1px solid var(--line);background:var(--card)}}
.chip.ask{{color:var(--mut)}}ol{{margin:0;padding:4px 14px 12px 34px;display:grid;gap:6px;font-size:13.5px}}
ol a{{color:var(--acc);font-weight:500;white-space:nowrap}}.ask-tag{{color:var(--mut);font-size:12px}}
a:focus-visible,summary:focus-visible,select:focus-visible{{outline:2px solid var(--acc);outline-offset:2px}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;display:grid;gap:8px}}
.panel ul{{margin:0;padding-left:18px;font-size:13.5px}}
</style></head><body><main>
<div><h1>Exam Topic Map</h1><div class="sub">Every topic past exams have asked, by organ system. A topic asked once counts as much
as one asked every year. Built {now}. The numbers on each topic are the cohorts (MDCU70, 72, …); filled = that cohort's paper asked it.
Tap a topic to see its questions.</div></div>
<div class="stats"><div class="stat"><b>{len(by_topic)}</b><span class="sub">topics examined</span></div>
<div class="stat"><b>{len(papers)}</b><span class="sub">papers</span></div>
<div class="stat"><b>{tagged_q}/{total_q}</b><span class="sub">questions tagged</span></div>
<div class="stat"><b>{len(gaps)}</b><span class="sub">topics with exam questions only</span></div></div>
<div class="bar"><select id="fc" aria-label="Cohort"><option value="">All cohorts</option>{cohort_opts}</select>
<select id="ff" aria-label="Format"><option value="">All formats</option>{format_opts}</select>
<div class="legend">{legend}</div></div>
{empty}{sections}
<div class="panel"><h2>Examined, but nothing to study from in the repo yet</h2><div class="chips">{gap_html}</div></div>
<div class="panel"><h2>Papers still to tag</h2><ul>{todo}</ul></div>
</main><script>
const apply=()=>{{const c=fc.value,f=ff.value;document.querySelectorAll('.tile').forEach(t=>{{let n=0;
t.querySelectorAll('li').forEach(li=>{{const ok=(!c||li.dataset.cohort===c)&&(!f||li.dataset.format===f);li.hidden=!ok;if(ok)n++}});
t.hidden=n===0}});document.querySelectorAll('section').forEach(s=>{{s.hidden=!s.querySelector('.tile:not([hidden])')}})}};
fc.onchange=ff.onchange=apply;
</script></body></html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    systems, papers, questions = collect(root)
    out = Path(args.out) if args.out else root / "exam-map" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(root, systems, papers, questions), encoding="utf-8")
    topics = len({q["topic"] for q in questions})
    print(f"{len(papers)} papers, {len(questions)} tagged questions, {topics} topics -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
