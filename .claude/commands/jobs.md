---
description: Show the extraction dashboard, pick a job, and work on it in small saved steps
---

Help me work on the extraction queue in jobs/. Plain language, no git jargon. Follow CLAUDE.md,
especially "Big jobs". $ARGUMENTS may be a job id; otherwise help me choose.

1. Get the latest: switch to `main`, pull. Run `python3 scripts/jobs.py dashboard`, show me the
   top of the table, and send me `jobs/dashboard.html` as a file.
2. Choose a job with me. Suggest from `python3 scripts/jobs.py next` (priority 1 = first), and
   explain size (S/M/L) and scanned pages. I may pick anything, in any order.
   - `on-hold`: only the owner (playerplayrh) releases a job. Ask me to confirm I am the owner,
     then set it to `todo` on a small pull request, or tell me to ask the owner.
   - `blocked`: explain why (its Notes) and pick another.
3. Get the job's files. Each job has its own Drive folder `Surgery Group/job-files/<id>/` (link in
   the job's `files` field) with the paper, its key(s) and a READ ME; `source` and `key_sources`
   name the files (`job-files/_shared-keys/` holds keys used by many jobs). Textbook jobs link
   to the Surgery folder that holds the book PDFs.
   - If `.claude/drive.local.json` exists (rclone set up): `rclone copy "<remote>job-files/<id>"
     <tmp>`, plus any shared keys, into a fresh temp folder OUTSIDE the repo.
   - Otherwise: give me the `files` link, tell me to download the folder (right-click >
     Download, then unzip), and ask where I saved it. Never ask for my Drive password.
   - Never copy these PDFs into the repo, and never change anything in Drive.
4. Start or resume:
   - If branch `origin/job/<id>` exists: switch to it and pull. Read the job file's `checkpoint`
     and `## Log`, open the output file, check the last saved item against the source, and
     continue from the bookmark. If its `owner` is someone else and status is `in-progress`,
     ask me first: they may still be working on it.
   - Otherwise: `git switch -c job/<id>` from main, set `status=in-progress owner=<me>`,
     commit "job <id>: start", push with `-u`.
5. Work in small steps (see CLAUDE.md "Big jobs"): after every page, or every 5 questions,
   write the output file, update `checkpoint` (e.g. "p.1-6 done, next Q13"), commit and push.
   Never keep more than one step unsaved. If my usage limit or the context is running out, save
   and push immediately and tell me where it stopped.
6. Stopping before the end: push, set `status=todo` (keep owner and checkpoint) so anyone can
   continue, log one line saying what is left, push again.
7. Finishing: run `python3 scripts/validate.py` (0 errors), set `status=done`, log a summary,
   push, open a pull request titled "Job <id>". The dashboard shows it as "Waiting for review"
   until it is merged, then "Done".
8. End by showing the dashboard again.
