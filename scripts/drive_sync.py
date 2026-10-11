#!/usr/bin/env python3
"""Copy the repo into the Google Drive "repo-copy" folder with rclone, for friends without GitHub.

    python3 scripts/drive_sync.py              use the remote in .claude/drive.local.json
    python3 scripts/drive_sync.py --dest DEST  DEST must end in repo-copy (rclone remote or path)
    python3 scripts/drive_sync.py --dry-run    show what would change, change nothing

The copy mirrors the repo: files deleted from the repo are deleted from repo-copy too (on Google
Drive they go to the Drive trash). Nothing outside repo-copy is touched. Git history, local
settings and the PDFs are left out.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDES = [".git/**", ".claude/**", "sources/**/*.pdf", "__pycache__/**", ".DS_Store"]


def default_dest():
    cfg = ROOT / ".claude" / "drive.local.json"
    if not cfg.is_file():
        sys.exit("No --dest given and .claude/drive.local.json is missing. Run /inbox once, "
                 "or pass --dest <remote>:repo-copy")
    return json.loads(cfg.read_text(encoding="utf-8"))["remote"].rstrip("/") + "/repo-copy"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest")
    ap.add_argument("--src", default=str(ROOT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    dest = args.dest or default_dest()
    src = Path(args.src).resolve()
    if not re.search(r"(^|[:/])repo-copy/?$", dest):
        sys.exit(f"Refusing: the destination must be a folder named repo-copy (got {dest})")
    local = Path(dest).expanduser()
    if ":" not in dest.split("/")[0] and (local.resolve() == src or src in local.resolve().parents):
        sys.exit("Refusing: the destination is inside the repo")
    if not shutil.which("rclone"):
        sys.exit("rclone is not installed (brew install rclone)")
    cmd = ["rclone", "sync", str(src), dest, "--stats-one-line", "-v"]
    for e in EXCLUDES:
        cmd += ["--exclude", e]
    if args.dry_run:
        cmd.append("--dry-run")
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(out.stderr.strip()[-2000:])
    changes = [ln for ln in out.stderr.splitlines()
               if re.search(r": (Copied|Deleted|Updated|Skipped .*(copy|delete))", ln)]
    print(("would change" if args.dry_run else "changed") + f": {len(changes)} files -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
