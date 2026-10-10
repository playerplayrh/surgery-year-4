# Where this repo differs from surgery-repo-spec-final.md

The spec file stays in the repo root unchanged. Decisions below were made by the owner on
2026-10-10 after reading the three survival guides.

| Spec | This repo | Why |
| --- | --- | --- |
| Repo `surgery-pool`, new folder | This folder is the repo; suggested GitHub name `surgery-year-4` | Owner's preference; the guides and PDFs already live here |
| G1 hepatobiliary, G2 vascular, G3 colon, G4 breast and anorectal | G map from the Survival guide Yr. 4 (README). Colorectal is a subspecialty | The guides disagree with the spec; the owner follows the guides |
| `group` includes only G1-G4 and cross | Same; no subspecialty values, and CLAUDE.md says to keep subspecialty material out | Exam is General Sx first; no subspecialty info during the first 6 weeks |
| Starter topics: acute-abdomen, biliary-obstruction, PAD, colorectal-cancer, breast-mass, anorectal-disease | Topic vocabulary in INDEX.md built from the guides, G-only | Colorectal and anorectal are subspecialty |
| Exam template is MCQ only | Added `exam-meq.md` and `exam-osce.md`, plus `exam_format`, `exam_year`, `exam_rotation` fields | Exams are MCQ, MEQ and OSCE; the spec's immutable "year" and "rotation" had no field to live in |
| 4 prompts | Same 4; convert-notes also does the G-vs-subspecialty check | |
| Types: case, concept, facts, exam, digest, synthesis, textbook-map | Added `ward-guide` and the `valid_year` field | Survival guides are year-specific rotation advice |
| `source` values per spec | Added `senior-summary` and `survival-guide` | |
| Privacy covers patient identifiers | Unchanged. Staff names and candid remarks are explicitly allowed | Owner: these are crucial for living through the rotation |
| Facts coverage: every raw line in a facts file or "Needs clarification" | Also accepted in "Out of scope for now (subspecialty)" | Mixed sources keep every line without mixing subspecialty into G topics |
| Yellow forms not mentioned | Tracker table in INDEX.md | Both guides say G4 has few cases and cases should be split |
| Textbook-map: references only, no scans | Reference keys in `textbook-map/_keys.md`; the two big PDFs are shared on Google Drive (git-ignored), everything else is pushed | Both PDFs exceed GitHub's 100 MiB limit; Drive chosen over Git LFS (no install, no quota) |
| Validator, checks 1-7 | All implemented, plus: verified_by must differ from author; new files cannot start human-verified; merged ids immutable; exams cannot be deleted; logs never echo a suspected identifier; the Thai laugh "555" is not an identifier | Found while testing against the real guides |
| Shared code in two scripts | Added `scripts/mdutil.py` (shared helpers) and `tests/test_scripts.py` | |
| Workflow checks out full history | Shallow checkout plus a fetch of the base branch | The PDFs make full history heavy |

## Checked on 2026-10-10 (GitHub rules)

- Branch protection and required reviews are not available for private repos on the Free plan.
  "A second person approves synthesis" is therefore a group convention.
- GitHub Free includes 2,000 Actions minutes a month for private repos; a validator run takes
  seconds.
- Normal Git pushes block files over 100 MiB (warning from 50 MiB). The two PDFs (now in sources/)
  are about 156 MiB and 212 MiB, so they cannot be pushed as ordinary files.
