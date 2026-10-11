#!/usr/bin/env python3
"""Extraction job queue: one small job per exam paper, textbook part, or bank chunk.

    python3 scripts/jobs.py dashboard              table in the terminal + jobs/dashboard.html
    python3 scripts/jobs.py dashboard --no-fetch   skip `git fetch` (offline)
    python3 scripts/jobs.py next [--scope gen] [-n 5]   best jobs to start now
    python3 scripts/jobs.py show <id>
    python3 scripts/jobs.py set <id> status=in-progress owner=ploy "checkpoint=p.1-8 done, next Q25"
    python3 scripts/jobs.py log <id> "message"     append a dated line to the job's log

Each job is a file jobs/<id>.md. While someone works on a job, it lives on the branch
job/<id>; the dashboard reads those branches on GitHub, so it shows live progress (status,
owner, bookmark) without anyone editing main. Standard library only.
"""
import argparse
import datetime
import html
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mdutil import read_text, split_front_matter  # noqa: E402

FIELDS = ["id", "title", "kind", "scope", "priority", "status", "owner", "pages", "scan_pages",
          "files", "source", "key_sources", "output", "checkpoint", "updated"]
STATUSES = ["in-progress", "todo", "review", "blocked", "on-hold", "done"]
KINDS = {"exam", "textbook", "bank"}
SCOPES = {"gen", "subspe", "mixed"}
STATUS_LABEL = {"todo": "To do", "in-progress": "In progress", "review": "Waiting for review",
                "blocked": "Blocked", "on-hold": "On hold", "done": "Done"}


def root_dir(arg):
    return Path(arg).resolve() if arg else Path(__file__).resolve().parent.parent


def parse_job(text):
    fm, body, _ = split_front_matter(text)
    return (fm or {}), body


def dump_job(fm, body):
    lines = ["---"]
    for k in FIELDS + [k for k in fm if k not in FIELDS]:
        v = fm.get(k, "")
        if isinstance(v, list):
            v = "[" + ", ".join('"' + str(x).replace('"', "'") + '"' for x in v) + "]"
        elif v and (":" in str(v) or "#" in str(v) or str(v)[0] in "[{'\""):
            v = '"' + str(v).replace('"', "'") + '"'
        lines.append(f"{k}: {v}".rstrip())
    return "\n".join(lines) + "\n---\n" + body


def effort(job):
    """Rough size: text pages are quick, scanned pages need OCR (about 3x the work)."""
    try:
        pages, scans = int(job.get("pages") or 0), int(job.get("scan_pages") or 0)
    except ValueError:
        return 0, "?"
    if not pages:
        return 0, "?"
    units = (pages - scans) + 3 * scans
    return units, ("S" if units <= 12 else "M" if units <= 35 else "L")


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def load_jobs(root, fetch=True):
    jobs = {}
    for p in sorted((root / "jobs").glob("*.md")):
        if p.name.startswith("_"):
            continue
        fm, body = parse_job(read_text(p))
        if fm.get("id"):
            fm["_where"] = "main"
            jobs[fm["id"]] = fm
    if fetch:
        git(root, "fetch", "--quiet", "--prune", "origin")
    # live progress from job/<id> branches on GitHub (or local ones if there is no remote)
    refs = git(root, "for-each-ref", "--format=%(refname)|%(committerdate:short)",
               "refs/remotes/origin/job/", "refs/heads/job/").stdout.split("\n")
    for line in filter(None, refs):
        ref, date = line.split("|")
        jid = ref.split("/job/", 1)[1]
        shown = git(root, "show", f"{ref}:jobs/{jid}.md")
        if shown.returncode != 0:
            continue
        fm, _ = parse_job(shown.stdout.replace("\r\n", "\n"))
        if not fm.get("id"):
            continue
        prev = jobs.get(jid, {})
        if prev.get("_where", "").startswith("origin") and ref.startswith("refs/heads/"):
            continue  # the GitHub copy wins over a stale local branch
        fm["_where"] = ("origin" if "/remotes/" in ref else "local") + f" job/{jid}"
        fm["_last_push"] = date
        if prev.get("status") == "done":
            continue  # already merged
        if fm.get("status") == "done":
            base = "origin/main" if git(root, "rev-parse", "--verify", "--quiet", "origin/main").returncode == 0 else "main"
            if git(root, "merge-base", "--is-ancestor", ref, base).returncode == 0:
                continue  # merged: main's copy is the truth
            fm["status"] = "review"  # finished on its branch, pull request not merged yet
        jobs[jid] = fm
    return jobs


def sort_key(job):
    st = job.get("status", "todo")
    try:
        prio = int(job.get("priority") or 9)
    except ValueError:
        prio = 9
    return (STATUSES.index(st) if st in STATUSES else 9, prio, effort(job)[0], job.get("id", ""))


def cmd_dashboard(root, args):
    jobs = load_jobs(root, fetch=not args.no_fetch)
    rows = sorted(jobs.values(), key=sort_key)
    total_pages = sum(int(j.get("pages") or 0) for j in rows)
    done_pages = sum(int(j.get("pages") or 0) for j in rows if j.get("status") == "done")
    counts = {s: sum(1 for j in rows if j.get("status") == s) for s in STATUSES}
    print(f"{len(rows)} jobs | {done_pages}/{total_pages} pages done | "
          + ", ".join(f"{STATUS_LABEL[s].lower()}: {n}" for s, n in counts.items() if n))
    print(f"{'prio':4}  {'status':12} {'size':4} {'pages':>5}  {'owner':10} {'id':38} bookmark")
    for j in rows:
        print(f"{str(j.get('priority', '')):4}  {j.get('status', ''):12} {effort(j)[1]:4} "
              f"{str(j.get('pages', '')):>5}  {(j.get('owner') or '-')[:10]:10} {j['id'][:38]:38} "
              f"{j.get('checkpoint', '')}")
    out = Path(args.html) if args.html else root / "jobs" / "dashboard.html"
    out.write_text(render_html(rows, counts, done_pages, total_pages), encoding="utf-8")
    print(f"\ndashboard: {out}")
    return 0


def files_link(job):
    url = str(job.get("files") or "")
    if not url.startswith("https://"):
        return ""
    return f' · <a href="{html.escape(url)}" target="_blank" rel="noopener">files</a>'


def render_html(rows, counts, done_pages, total_pages):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    pct = int(100 * done_pages / total_pages) if total_pages else 0
    trs = []
    for j in rows:
        st = j.get("status", "todo")
        trs.append(
            f'<tr data-status="{st}" data-scope="{html.escape(j.get("scope", ""))}" '
            f'data-kind="{html.escape(j.get("kind", ""))}">'
            f'<td class="num">{html.escape(str(j.get("priority", "")))}</td>'
            f'<td><span class="pill s-{st}">{STATUS_LABEL.get(st, st)}</span></td>'
            f'<td><b>{html.escape(j.get("title", ""))}</b><div class="sub">{html.escape(j["id"])}'
            f'{files_link(j)}</div></td>'
            f'<td>{html.escape(j.get("scope", ""))} · {html.escape(j.get("kind", ""))}</td>'
            f'<td class="num">{html.escape(str(j.get("pages", "")))}'
            f'<div class="sub">{effort(j)[1]}{", " + str(j.get("scan_pages")) + " scanned" if str(j.get("scan_pages", "0")) not in ("", "0") else ""}</div></td>'
            f'<td>{html.escape(j.get("owner") or "—")}<div class="sub">{html.escape(j.get("_last_push", ""))}</div></td>'
            f'<td>{html.escape(j.get("checkpoint") or "")}</td></tr>')
    cards = "".join(f'<div class="card"><div class="n">{counts[s]}</div><div class="sub">{STATUS_LABEL[s]}</div></div>'
                    for s in STATUSES)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Extraction dashboard</title>
<style>
:root{{--bg:#fbfaf7;--fg:#22211e;--mut:#6d6b64;--line:#e4e1d8;--card:#fff;--acc:#534AB7;
--todo:#eceae3;--prog:#d9eefb;--rev:#fbf0d9;--blk:#fbe3e3;--hold:#eceae3;--done:#e5f3dc}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1c1b19;--fg:#ecebe6;--mut:#a8a69e;--line:#34322e;--card:#252421;
--todo:#34322e;--prog:#16354f;--rev:#4a3714;--blk:#4f1c1c;--hold:#34322e;--done:#23401a}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}}h1{{font-size:22px;font-weight:500;margin:0}}
.sub{{color:var(--mut);font-size:12px}}.cards{{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;min-width:96px}}
.n{{font-size:22px;font-weight:500}}.bar{{height:8px;border-radius:4px;background:var(--line);overflow:hidden;margin:6px 0 2px}}
.bar i{{display:block;height:100%;width:{pct}%;background:var(--acc)}}
.filters{{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}}select{{font:inherit;padding:4px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg)}}
.wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}th{{font-weight:500;font-size:13px;color:var(--mut)}}
.num{{text-align:right}}a{{color:var(--acc)}}.pill{{padding:2px 8px;border-radius:999px;font-size:12px;white-space:nowrap}}
.s-todo{{background:var(--todo)}}.s-in-progress{{background:var(--prog)}}.s-review{{background:var(--rev)}}
.s-blocked{{background:var(--blk)}}.s-on-hold{{background:var(--hold)}}.s-done{{background:var(--done)}}
</style></head><body><main>
<h1>Extraction dashboard</h1><div class="sub">Snapshot {now}. Priority 1 = do first. Pick a job, then run /jobs in Claude Code.</div>
<div class="bar"><i></i></div><div class="sub">{done_pages} of {total_pages} pages done ({pct}%)</div>
<div class="cards">{cards}</div>
<div class="filters"><select id="fs"><option value="">All statuses</option>{"".join(f'<option value="{s}">{STATUS_LABEL[s]}</option>' for s in STATUSES)}</select>
<select id="fc"><option value="">All scopes</option><option value="gen">General Sx</option><option value="subspe">Subspecialty</option><option value="mixed">Mixed</option></select>
<select id="fk"><option value="">All kinds</option><option value="exam">Exam paper</option><option value="bank">Exam bank chunk</option><option value="textbook">Textbook</option></select></div>
<div class="wrap"><table><thead><tr><th class="num">Prio</th><th>Status</th><th>Job</th><th>Scope</th><th class="num">Pages</th><th>Owner</th><th>Bookmark</th></tr></thead>
<tbody>{"".join(trs)}</tbody></table></div></main>
<script>
const f=()=>{{const s=fs.value,c=fc.value,k=fk.value;document.querySelectorAll('tbody tr').forEach(r=>{{
r.style.display=(!s||r.dataset.status===s)&&(!c||r.dataset.scope===c)&&(!k||r.dataset.kind===k)?'':'none'}})}};
[fs,fc,fk].forEach(e=>e.onchange=f);
</script></body></html>
"""


def cmd_next(root, args):
    jobs = load_jobs(root, fetch=not args.no_fetch)
    todo = [j for j in jobs.values() if j.get("status") == "todo" and (not args.scope or j.get("scope") == args.scope)]
    for j in sorted(todo, key=sort_key)[: args.n]:
        print(f"{j['id']}  (priority {j.get('priority')}, {j.get('pages')} pages, size {effort(j)[1]}) {j.get('title', '')}")
    if not todo:
        print("No jobs to do.")
    return 0


def job_path(root, jid):
    p = root / "jobs" / f"{jid}.md"
    if not p.is_file():
        sys.exit(f"No job '{jid}' in jobs/ on this branch")
    return p


def cmd_show(root, args):
    print(read_text(job_path(root, args.id)))
    return 0


def cmd_set(root, args):
    p = job_path(root, args.id)
    fm, body = parse_job(read_text(p))
    for pair in args.pairs:
        if "=" not in pair:
            sys.exit(f"Use key=value, got '{pair}'")
        k, v = pair.split("=", 1)
        if k not in FIELDS or k == "id":
            sys.exit(f"Unknown or fixed field '{k}'")
        if k == "status" and v not in STATUSES:
            sys.exit(f"status must be one of {STATUSES}")
        if k == "priority" and not re.fullmatch(r"[1-9]", v):
            sys.exit("priority must be 1 (first) to 9 (last)")
        fm[k] = v
    fm["updated"] = datetime.date.today().isoformat()
    p.write_text(dump_job(fm, body), encoding="utf-8")
    print(f"updated {p.relative_to(root)}")
    return 0


def cmd_log(root, args):
    p = job_path(root, args.id)
    fm, body = parse_job(read_text(p))
    if "## Log" not in body:
        body = body.rstrip() + "\n\n## Log\n"
    body = body.rstrip() + f"\n- {datetime.date.today().isoformat()} {args.message}\n"
    fm["updated"] = datetime.date.today().isoformat()
    p.write_text(dump_job(fm, body), encoding="utf-8")
    print(f"logged in {p.relative_to(root)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dashboard")
    d.add_argument("--no-fetch", action="store_true")
    d.add_argument("--html")
    n = sub.add_parser("next")
    n.add_argument("--scope", choices=sorted(SCOPES))
    n.add_argument("-n", type=int, default=5)
    n.add_argument("--no-fetch", action="store_true")
    s = sub.add_parser("show")
    s.add_argument("id")
    st = sub.add_parser("set")
    st.add_argument("id")
    st.add_argument("pairs", nargs="+")
    lg = sub.add_parser("log")
    lg.add_argument("id")
    lg.add_argument("message")
    args = ap.parse_args(argv)
    root = root_dir(args.root)
    return {"dashboard": cmd_dashboard, "next": cmd_next, "show": cmd_show,
            "set": cmd_set, "log": cmd_log}[args.cmd](root, args)


if __name__ == "__main__":
    sys.exit(main())
