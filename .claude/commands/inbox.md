---
description: Process new material from the Google Drive inbox into the repo, then share it
---

Process the Google Drive inbox. Follow CLAUDE.md (especially "Drive inbox"). Talk to me in plain
language: no git jargon, short sentences. Never delete anything in Drive; only move files.

1. Reach the Drive folder with rclone (never a Drive app path).
   - Read `.claude/drive.local.json` (`{"remote": "surgerygroup:"}`; git-ignored). If it is
     missing, run `rclone listremotes`, ask me which remote is the "Surgery Group" folder, and save
     it. In the steps below, R means that remote, e.g. `surgerygroup:`.
   - `rclone lsf R --dirs-only` must show `inbox/`, `needs-fix/`, `done/`, `repo-copy/`. Create
     a missing one with `rclone mkdir R<name>`.
   - If rclone says the token expired or access is denied, tell me to run
     `rclone config reconnect <remote>` in my terminal, and stop.
2. Get the latest repo: switch to `main`, pull, then create branch `inbox/<YYYY-MM-DD>`
   (add `-2`, `-3` if it exists).
3. List the files: `rclone lsf Rinbox --files-only`. Skip `READ ME` files. Download them to a
   fresh temp folder OUTSIDE the repo:
   `rclone copy Rinbox <tmp> --drive-export-formats docx,xlsx`
   (Google Docs arrive as .docx). Work from those copies; never edit the files in Drive.
4. For each file, in this order:
   a. Read it. `.docx`: convert with `textutil -convert txt -stdout`. `.pdf` and photos: read
      them visually and transcribe verbatim; mark the item "from photo/PDF, check spelling".
   b. Privacy check (CLAUDE.md hard rules). If you find a patient identifier, do NOT process the
      file: `rclone moveto "Rinbox/<name>" "Rneeds-fix/<name>"`, then write the note with
      `printf '%s\n' "<reason>" | rclone rcat "Rneeds-fix/<name> - NEEDS FIX.txt"`, saying which
      line and what kind of identifier (never copy the identifier itself).
   c. Who sent it: the file name is `G3 - topic - Name.ext`. Author = `drive-<name>` (lowercase,
      letters/digits/hyphens). If the G or the name is missing, ask me in the summary.
   d. Scope, type and topic per CLAUDE.md (G vs subspecialty, case/concept/facts/exam/ward guide,
      reuse an INDEX.md topic).
   e. Save the original text unchanged to `raw/drive-<name>/<YYYY-MM-DD>-<slug>.md` (for a photo
      or PDF: your verbatim transcription; never store the photo itself).
   f. Convert with the matching template, status `ai-generated`, add the INDEX.md row.
5. Run `python3 scripts/validate.py` and fix problems in the new files.
6. Show me one table: file | became | topic | G | problems. Under it, a short preview of each new
   file. Ask: "Share these with the group?" I may answer all, some, or "fix X first".
7. When I approve: commit only the approved files, push the branch, and open a pull request.
   - If `gh` is installed: wait for the validate check; if green, merge it and switch back to
     main and pull. If red, explain in one sentence, fix, push again.
   - If `gh` is not installed: give me the pull request link and tell me to merge it once the
     check is green.
8. Move each shared file: `rclone moveto "Rinbox/<name>" "Rdone/<YYYY-MM-DD> <name>"`.
   Files I did not approve stay in `inbox/`. Delete the temp folder.
9. Refresh the read-only copy: `python3 scripts/drive_sync.py --dry-run`, check the count looks
   sensible, then `python3 scripts/drive_sync.py`.
10. Finish with: what was added, what is waiting in needs-fix and why, and what I must tell
    which friend.
