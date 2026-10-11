# Rules for Claude in this repo

This repo pools **General Surgery (G1-G4)** study material for MDCU Year 4. Each student sees
only some of the Gs, so pooling gives everyone the rest. Read README.md and this file before
creating, converting, or editing anything. The front-matter schema is in
templates/front-matter.md.

## Scope: General Surgery only
- In scope: G1, G2, G3, G4 and things every G sees (e.g. appendicitis).
- **Out of scope for now: every subspecialty rotation** (Colorectal, Neuro, CVT, Plastic, Uro,
  Ped). Colorectal is a subspecialty, not part of any G. Nothing from the Gs goes into
  subspecialty files, and nothing from a subspecialty is filed as a G topic.
- **Check first, every time:** before filing anything, decide for each part whether it belongs
  to a G or to a subspecialty. If you cannot tell, ask in one question.
- Mixed sources (e.g. a survival guide that covers both): convert the G parts normally. Keep the
  subspecialty parts word-for-word in an "Out of scope for now (subspecialty)" section of the
  same file, with their [L..] tags. Do not drop them, do not summarise them, do not file them
  under a topic.
- Exams: a set must be a General Surgery exam. Subspecialty questions stay out. Keep the
  original numbers of the questions you do file, so gaps are fine. Add the line
  `Omitted (subspecialty): Q31-Q60` under the front-matter of the exam file.
- **Exception: textbook extractions** (textbook/<book>/) cover the whole book, subspecialty
  chapters included, so the book is never processed twice. Subspecialty chapters are kept
  apart: file name `<nn>-subspe-<slug>.md`, topic `subspecialty-<rotation>` (colorectal, neuro,
  cvt, plastic, uro, ped), never a G topic, and not listed in the INDEX.md topic vocabulary.
  The rules for the extraction are in the instructions given to the extractor.

## Privacy (hard rules)
- Never write or keep **patient** names, HN/AN, birthdates, exact dates, ward/bed numbers,
  phone numbers, or photos showing faces, labels, or ID bands. This applies to raw/ too.
- If the user's input contains any of these, stop, tell them what you found, and ask
  them to remove it. Do not "clean" it silently.
- **Staff names are not restricted.** Names of attendings, residents, and other teachers,
  and candid remarks about rotation life, are crucial information here. Keep them exactly as
  the source has them. Never mask, shorten, or leave them out.

## Intake
- The user may paste anything: typed notes, dictation, a dump of facts, textbook
  points, an exam, or a survival guide. They only need to tell you the G.
- Detect the topic and note type (case / concept / facts / exam / ward-guide). Reuse a topic
  already in INDEX.md before creating a new one. Do not create near-duplicates of existing
  topics.
- For an exam you need the set code, year, rotation, the format (mcq / meq / osce), and whether
  answers are official, recalled, or to be derived. Ask for all of it in one question.
- Otherwise ask at most one question, and only if you cannot proceed without the answer.
- Save the user's original text unchanged to raw/<author>/<batch>.md before converting
  (patient identifiers removed by the user first).

## Accuracy
- Use only what is in the source. Do not add clinical facts from your own knowledge.
  Write "not stated" for missing sections in case and concept notes.
- Every file you create has status: ai-generated. Never set human-verified yourself.
- Claims that may conflict with a guideline (e.g. "residents sometimes use antibiotics that do
  not follow the guideline") are kept as written and also listed under "Flagged for checking"
  as a question. Never edit or correct the author's line.
- This repo is for study, not for real patient decisions.

## Facts notes
- One fact per line, each starting with its subject, so lines make sense when moved.
- Keep the author's original wording and language. Fix only obvious typos.
- Cryptic, cut-off, or ambiguous lines go to "Needs clarification" with the original
  text. Never guess what they mean.
- Every line carries its raw line number, e.g. [L12]. Every content line of the
  original must appear in a facts file or in "Needs clarification" (or in "Out of scope").
- You may list doubtful lines under "Flagged for checking" as a question. Never edit
  or correct the line itself.

## Ward guides (survival guides, reviews, tips)
- Use templates/ward-guide.md. type: ward-guide, with `valid_year`. Rotations change every
  year, so say which year and cohort the guide was written for.
- Keep the author's wording and language. Teachers' names stay.
- Set `raw` to the saved original. Write every source line as a bullet in the author's words,
  ending with its [Lnn] tag, under the section where it fits (a line that mixes G and
  subspecialty content goes in the G section). The validator checks no line was dropped.
- If the source does not say which year it was written for, use `valid_year: unknown`.

## Exams
- Follow the template for the format: templates/exam.md (mcq), exam-meq.md, exam-osce.md.
  Keep original question numbers. Never renumber.
- Never change set code, year, rotation, original number, or stem of a merged exam.
- Do not write hints into stems. Do not make the correct choice longer than the others.
  Name the guideline when one applies.
- Be honest about answer_source. Do not present a guessed answer as official.

## Format
- Use the templates in templates/. Front-matter is required.
- Reason H&P first in case notes: DDx with why / why not from history and exam. Labs
  and imaging only afterwards, as confirmation.
- Never change an existing file's id. Do not rewrite other people's merged files
  except to fix typos.

## Token economy
- For comparisons, quizzes, and synthesis, read digests/ and facts/<topic>/_merged.md
  for the relevant topic first. Open a raw note or the raw/ folder only if needed or asked.
- Facts notes and exams need no digest.
- Do not open the PDFs in sources/ unless asked (they are on Drive, not in git).

## Drive inbox (contributors without GitHub)
- Friends without GitHub upload to the Google Drive folder "Surgery Group/inbox"; the guide they
  follow is docs/drive-inbox-guide.txt. Someone with repo access runs `/inbox`
  (.claude/commands/inbox.md) to process it.
- Author for these files is `drive-<name>`; their originals go to `raw/drive-<name>/`.
- A file with a patient identifier is never processed: move it to `needs-fix/` with a note that
  says which line and what kind of identifier, without copying the identifier.
- Claude reaches Drive only through rclone (remote saved in .claude/drive.local.json).
- Never delete files in Drive; only move them (inbox -> done or needs-fix).
- `job-files/` and `sources/` in Drive hold the extraction sources (see "Big jobs"); /inbox
  never touches them.
- `repo-copy/` in Drive is a read-only mirror made by scripts/drive_sync.py. Never edit it by hand.

## Big jobs (extraction queue)
- Long work (exam papers, exam banks, textbooks) is split into jobs, one file each in jobs/.
  The queue and its rules are run with `/jobs` (.claude/commands/jobs.md) and
  scripts/jobs.py. The dashboard is jobs/dashboard.html (generated, not committed).
- Each exam/bank job's files are in Drive `Surgery Group/job-files/<id>/` (link in the job's
  `files` field); keys used by many jobs are in `job-files/_shared-keys/`. The original zips are
  kept in `Surgery Group/sources/AC-original-zips/`. These PDFs never go into git, and nobody
  edits job-files/ by hand.
- One job per branch `job/<id>`. Save in small steps: after every page or every 5 questions,
  write the output, update the job's `checkpoint`, commit and push. A session that runs out
  must lose at most one step.
- To resume, read the checkpoint and Log, re-check the last saved item against the source, then
  continue. Never restart a job from scratch if its branch exists.
- Only the owner (playerplayrh) moves a job off `on-hold`. Anyone may pick any `todo` job in
  any order; priority (1 = first) is a suggestion.
- Exam decisions (2026-10-11): subspecialty papers are extracted but kept apart from General
  Surgery; per-cohort papers before the big AC bank; answer keys written by students or the
  academic team use answer_source `student-key`; set codes look like `mdcu76-gen-c-mcq`.

## Terms
- AC = past exam (the owner does not remember what the letters stand for).

## Workflow
- Work on a branch and open a pull request. Do not commit straight to main.
- Run `python3 scripts/validate.py` before pushing.
- Cross-G synthesis needs a second person's approval before merging. (Free private repos
  cannot enforce this, so it is a group convention.)
