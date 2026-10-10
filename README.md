# Surgery Year 4

Private study repo for the MDCU Year 4 surgery rotation. Not everyone rotates through every
G, so together we cover all four. **Scope: General Surgery (G1-G4) only.** Subspecialty
rotations (Colorectal, Neuro, CVT, Plastic, Uro, Ped) are left out for now.

- Add: paste your material (any messy form) into your Claude with the prompt in
  prompts/convert-notes.md and say your G. Review the result, then open a PR.
- Read: start from synthesis/, digests/, and facts/<topic>/_merged.md.
  Open raw notes only when needed.
- Exams: one folder per set in exams/. Original question numbers never change. MCQ, MEQ and
  OSCE each have a template.
- Ward life: ward-guide/ holds survival guides and tips (daily routine, on-call, OR cases
  worth seeing, exam advice). Staff names are kept.
- Rules: see CLAUDE.md. No **patient** identifiers, ever, including in raw/.
- Status: ai-generated means unchecked. human-verified means a second person checked it.
- Limits: the automatic checks catch skipped content and obvious identifiers, not wrong
  meaning. Verify against the textbook or your attending before relying on anything.

## What each G covers (year-stamped, check your own year)

Taken from the Survival guide Yr. 4 (main source) and P'Prung's review (MDCU 78) in
`Survival Guide/`. The two guides disagree in places and rotations change every year, so
treat this as a map, not a rule. A topic lives in one place whatever G you saw it in.

| G | Main content (Survival guide Yr. 4) | Differences / extras (P'Prung, MDCU 78) |
| --- | --- | --- |
| G1 | Liver: liver mass, jaundice, RUQ pain; HCC, liver metastasis, cholangiocarcinoma; liver segments, CT appearance | Heaviest G; liver transplant; OR cases: hernia, Whipple, transplant |
| G2 | Vascular and thyroid, some breast: AAA, thyroid and neck mass, PAD, venous insufficiency, claudication | Only G with vascular attendings; one attending's breast surgery worth watching |
| G3 | Biliary, pancreas, spleen, stomach, esophagus: cholecystitis, cholangitis, gallstones, periampullary tumor, gastric and esophageal CA, GIST, caustic ingestion; Whipple, HIPEC, gastric bypass, adult hernia; approach to abdominal pain, abdominal mass, jaundice, dysphagia, obstruction | Heavy; kind attendings; OR cases: HIPEC, esophagus |
| G4 | Breast and soft tissue: breast mass, discharge, necrotizing fasciitis, SSTI; mammogram, breast USG, clinical breast exam | Lightest G; breast and endoscopy; few yellow-form cases |
| All | Acute appendicitis and its signs | |
| Not a G | **Colorectal is a subspecialty** (hemorrhoids, colorectal CA, colonoscopy, PR exam, lower GI bleed). Out of scope for now | |

## Folders

```
README.md  CLAUDE.md  INDEX.md
templates/     note, exam, digest and ward-guide templates, front-matter schema
prompts/       the four prompts
raw/<author>/  untouched originals (patient identifiers removed)
notes/<topic>/ case notes and concept notes
facts/<topic>/ one file per batch, plus _merged.md (generated)
exams/<set>/   exam.md plus images/
digests/<topic>/   synthesis/<topic>/   textbook-map/<topic>.md
ward-guide/    survival guides and rotation tips
textbook/<book>/   full textbook extractions: _manifest.md, chapter files, images/
scripts/       validate.py, build_facts.py (standard library only)
tests/         tests for the scripts, invented sample data only
Survival Guide/  the three survival guides as received
sources/         PDFs live on Google Drive, not in git; links in sources/README.md
docs/spec-deviations.md   where this repo differs from surgery-repo-spec-final.md
```

## Checks (scripts/validate.py)

Run `python3 scripts/validate.py` before you push. GitHub Actions runs it on every pull
request. It checks front-matter, digests (450 words, "Left out" line, DDx coverage), facts
coverage (every line of the raw file accounted for), patient-identifier patterns, topic
near-duplicates, and exams (answers, unique numbers, image names, merged questions not
edited when run with `--base`).

Honest limits:
- DDx and facts coverage prove nothing was *skipped*, not that the meaning was *kept*. The
  author's spot-check and the verifier still matter.
- The identifier scan catches obvious slips only. It does not replace a human check. Images
  are flagged for manual review.
- Word counts for Thai text are approximate.
- Free private GitHub repos have no branch protection, so "a second person approves
  synthesis" is a group convention, not something GitHub enforces.

## Facts tooling

`python3 scripts/build_facts.py` regroups the per-batch files in facts/<topic>/ into
facts/<topic>/_merged.md by subject, tags every line with its source file, and flags exact
duplicates. It uses no tokens. Never edit `_merged.md` by hand.
