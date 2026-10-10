# Surgery Pool: repo build spec (FINAL)

**Purpose:** a private GitHub repo where a group of medical students pools surgery-rotation study material across G1-G4 (G1 hepatobiliary, G2 vascular, G3 colon, G4 breast and anorectal). Each student sees only one G, so pooling gives everyone the others. Each friend uses their own Claude account to convert their material into a standard format. Cross-G comparison reads short digests, not raw notes, to save tokens.

**Instruction to Claude Code:** read this whole file, then build the repo exactly as specified. Create every file listed in section B, with the contents given. Write and test `scripts/validate.py` and `scripts/build_facts.py` using **invented sample data only**, never real patient or personal data. Show me the test results and a file tree before the first commit.

---

## A. Decisions (final)

| ID | Decision |
| --- | --- |
| A1 | Repo name: `surgery-pool` (private) |
| A2 | Anything Claude writes (headings, converted structure) is in English. The author's own wording is kept exactly as written, in any language (Thai included) |
| A3 | **Notes and facts: add first, check later.** Anyone can merge them once the validator passes. They stay `ai-generated` until a second person verifies them. **Cross-G synthesis: check first.** It needs a second person's approval on the pull request before merging. This is a group convention. Free private repos may not be able to enforce it, so check GitHub's current rules |
| A4 | **Exams are in.** The owner reports the school's rules do not prohibit sharing them. **Lectures are out** of the pilot and can be added later if a friend has material worth sharing |
| A5 | **Pilot:** owner + 1 friend in a different G, 3 topics, 2 weeks. Then invite everyone else (see section L) |
| A6 | Starter topics: `acute-abdomen`, `biliary-obstruction`, `peripheral-arterial-disease`, `colorectal-cancer`, `breast-mass`, `anorectal-disease`. New topics are allowed when none fits (see CLAUDE.md) |
| A7 | **Verifying a facts file:** the verifier reads "Needs clarification" and "Flagged for checking" fully, skims the rest, and checks a few random lines against the textbook |

---

## B. Folder structure

```
surgery-pool/
├─ README.md
├─ CLAUDE.md                     rules every friend's Claude reads first
├─ INDEX.md                      topics and exam sets, G, author, status
├─ templates/
│  ├─ case-note.md
│  ├─ concept-note.md
│  ├─ facts-note.md
│  ├─ exam.md
│  └─ digest.md
├─ prompts/
│  ├─ convert-notes.md
│  ├─ make-digest.md
│  ├─ compare-across-g.md
│  └─ make-quiz.md
├─ raw/<author>/<batch>.md       untouched originals, identifiers removed
├─ notes/<topic>/                case notes and concept notes
├─ facts/<topic>/                one file per batch, plus _merged.md (generated)
├─ exams/<set-code>/             exam.md plus images/
├─ digests/<topic>/
├─ synthesis/<topic>/
├─ textbook-map/<topic>.md       section/page references only, no scans
├─ scripts/
│  ├─ validate.py
│  └─ build_facts.py
└─ .github/workflows/validate.yml
```

- The G (G1-G4) is a tag in front-matter, not a folder, so one topic lives in one place.
- `raw/` is for audit and re-conversion. Claude does not read it unless asked.
- `INDEX.md` is kept up to date by whoever adds a file.

---

## C. Front-matter schema (top of every file except raw files and `_merged.md`)

```yaml
---
id: facts-pleurodynia-001          # unique, never changed after merge
type: facts-note                   # case-note | concept-note | facts-note | exam | digest | synthesis | textbook-map
topic: chest-wall-pain             # reuse a topic from INDEX.md when one fits; blank for exams
group: G1                          # G1 | G2 | G3 | G4 | cross
source: mixed                      # bedside | textbook | lecture | exam-recall | mixed | unknown
author: github-username
date: 2026-10-10                   # date written, NOT the patient encounter
status: ai-generated               # ai-generated | human-verified
verified_by:                       # filled when verified
raw:                               # raw file this was converted from
references: []                     # textbook section or page, if any
digest_of:                         # digests only: id of the source note
built_from: []                     # synthesis only: ids of the sources used
exam_set:                          # exams only: set code
answer_source:                     # exams only: official | recalled | ai-derived
---
```

- `id` is immutable after merge.
- `status` starts as `ai-generated` for **every** type. Only a second person sets `human-verified`.

---

## D. Templates

### D1. `templates/case-note.md` (H&P first)

```markdown
# <Presenting problem, e.g. "RUQ pain with fever and jaundice">

## Patient (de-identified)
Age band and sex only (e.g. "60s F"). Encounter timing as week of rotation (W1-W4).
NO names, HN/AN, birthdates, exact dates, ward or bed, photos.

## History: key positives and negatives

## Physical examination: key positives and negatives

## Differential diagnosis (from H&P only)
| Diagnosis | For (from Hx/PE) | Against (from Hx/PE) |
| --- | --- | --- |

## Confirmation (only after H&P can go no further)
Which investigations, and what each would show.

## Management and surgical indication

## Attending pearls
What the teacher actually stressed at the bedside.

## Not sure / to check
```

Missing sections are written as "not stated", so gaps are visible.

### D2. `templates/concept-note.md` (textbook and lecture content)

```markdown
# <Concept or condition>

## Key points

## Indications / contraindications (or when to use / avoid)

## Pitfalls and pearls

## Source
Textbook section or page, lecture title.
```

Missing sections are written as "not stated".

### D3. `templates/facts-note.md` (dumps of small facts, one-line pearls)

```markdown
## <Subtopic heading>
- <Subject>: <fact, original wording> [L12]
- <Subject>: <fact, original wording> [L13]

## Needs clarification (original text kept)
- "<original text>" [L88]

## Flagged for checking
- <original line> [L20] — why it may need checking, phrased as a question
```

- `[L12]` is the line number in the raw file. It makes every fact traceable and makes the coverage check possible.
- Headings follow whatever subtopics the dump contains.
- Omit "Flagged for checking" when empty.

Illustration (invented, do not commit):

```markdown
## Example subtopic
- Example condition: example fact in the author's own words [L3]
- Example condition: another fact [L4]

## Needs clarification (original text kept)
- "half-written fragment" [L9]
```

### D4. `templates/exam.md`

```markdown
## Q<n> (original no. <n>)
<Stem. Case-based, formal English.>

A. ...
B. ...
C. ...
D. ...
E. ...

**Answer:** <letter>
**Explanation:** why the answer is right, and why each other choice is wrong
**Guideline / source:** name the guideline or textbook section, or "not stated"
```

Rules for exams:
- Keep the **original question number** from the source exam. Never renumber.
- Refer to a question as `<set-code> Q<original no.>`, never by its position in a file or app.
- Image files are named `<set-code>-q<nn>-<k>.<ext>` in `exams/<set-code>/images/`.
- Set `answer_source` honestly. Recalled answer keys are often wrong, so recalled and AI-derived answers stay `ai-generated` until verified.
- **Immutable after merge:** set code, year, rotation, original question number, and the stem. Only the answer, explanation, and guideline may be corrected later.
- Questions written by a friend (not recalled) must be case-based with formal English stems and choices.
- Quality checks: no hints in the stem, the correct choice is not longer than the others, and the guideline is named when one applies.

### D5. `templates/digest.md` (case notes and concept notes only)

```markdown
# Digest: <title>

**One line:** <what this teaches>

**Key Hx/PE clues:**

**DDx, ranked:** each diagnosis with the one feature that separates it

**Confirmation:** one line

**Management / surgical indication:**

**Pearls:**

**Left out:** one line listing what the note contained that this digest omitted

**Source note:** <note id> (open it for full detail)
```

Digest rules:
1. **Never drop:** every pearl, every DDx diagnosis with its discriminating feature, and every surgical indication from the note must appear. Only the total length is limited (max 450 words).
2. If those items cannot fit in 450 words, skip the digest and use the note itself.
3. Notes under about 400 words need no digest. The note is its own digest.
4. A digest only restates what is in its note. Gaps are "not stated".
5. The note's author skims the digest against the note (about 30 seconds).
6. Facts notes and exams get no digest.

---

## E. `CLAUDE.md` (create at the repo root with this content)

```markdown
# Rules for Claude in this repo

This repo pools surgery-rotation study material across G1-G4. Read README.md and this
file before creating, converting, or editing anything.

## Privacy (hard rules)
- Never write or keep patient names, HN/AN, birthdates, exact dates, ward/bed numbers,
  phone numbers, or photos showing faces, labels, or ID bands. This applies to raw/ too.
- If the user's input contains any of these, stop, tell them what you found, and ask
  them to remove it. Do not "clean" it silently.

## Intake
- The user may paste anything: typed notes, dictation, a dump of facts, textbook
  points, or an exam. They only need to tell you the G.
- Detect the topic and note type (case / concept / facts / exam). Reuse a topic already
  in INDEX.md before creating a new one. Do not create near-duplicates of existing topics.
- For an exam you need the set code and whether answers are official, recalled, or
  to be derived. Ask for both in one question.
- Otherwise ask at most one question, and only if you cannot proceed without the answer.
- Save the user's original text unchanged to raw/<author>/<batch>.md before converting
  (identifiers removed by the user first).

## Accuracy
- Use only what is in the source. Do not add clinical facts from your own knowledge.
  Write "not stated" for missing sections in case and concept notes.
- Every file you create has status: ai-generated. Never set human-verified yourself.
- This repo is for study, not for real patient decisions.

## Facts notes
- One fact per line, each starting with its subject, so lines make sense when moved.
- Keep the author's original wording and language. Fix only obvious typos.
- Cryptic, cut-off, or ambiguous lines go to "Needs clarification" with the original
  text. Never guess what they mean.
- Every line carries its raw line number, e.g. [L12]. Every content line of the
  original must appear in a facts file or in "Needs clarification".
- You may list doubtful lines under "Flagged for checking" as a question. Never edit
  or correct the line itself.

## Exams
- Follow templates/exam.md. Keep original question numbers. Never renumber.
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

## Workflow
- Work on a branch and open a pull request. Do not commit straight to main.
- Run scripts/validate.py before pushing.
- Cross-G synthesis needs a second person's approval before merging.
```

---

## F. Prompts (`prompts/`)

**`convert-notes.md`**
> My G is <G1-G4>. Below is my raw material. Follow CLAUDE.md: save it unchanged to raw/, detect topic and note type, convert with the matching template, fill front-matter. Stop if you find patient identifiers. Add nothing from your own knowledge.

**`make-digest.md`**
> Read the note at <path>. If it is under about 400 words, tell me no digest is needed. Otherwise write a digest using templates/digest.md: max 450 words, keep every pearl, every DDx diagnosis with its discriminating feature, and every surgical indication. Include the "Left out" line. Use only facts in the note.

**`compare-across-g.md`**
> Read digests/<topic>/ and facts/<topic>/_merged.md only. Write synthesis/<topic>/<topic>.md: a comparison table (symptom character, key exam findings, risk factors, first action) across the diagnoses, plus 3 "how to tell them apart" points. List the sources in built_from. Do not add facts not in the sources. This file needs a second person's approval before merging.

**`make-quiz.md`**
> From synthesis/<topic>/ (and the facts file if needed), write 5 OSCE-style cases. Present history and exam first, ask for the DDx, reveal investigations only after. Give an answer key with why / why not. Add 5 short recall questions from the facts file. In the answer key, state whether each source is ai-generated or human-verified.

---

## G. Validator (`scripts/validate.py`, runs on every pull request via GitHub Actions)

Checks:
1. Required front-matter fields are present and values are from the allowed lists. `id` is unique. `type` matches the folder.
2. Digests: under 450 words, with a "Left out" line, `digest_of`, and a link to the note. Synthesis has `built_from`.
3. **Identifier scan** over notes, facts, exams, and raw files: digit strings of 6+ digits, 13-digit numbers, full dates, "HN"/"AN" followed by digits, phone-like numbers. Image files are flagged for manual review.
4. **DDx coverage:** every diagnosis in a case note's DDx table also appears in its digest.
5. **Facts coverage:** every content line of a raw file is referenced by an `[Lnn]` tag in a facts file derived from it, or appears in "Needs clarification". Headings and blank lines are ignored.
6. **Topic check:** warn when a topic is not in INDEX.md and looks like a near-duplicate of one that is.
7. **Exams:** every question has an answer and an explanation. Question numbers are unique within a set. Image names start with the set code. A pull request that changes a merged exam's set code, year, rotation, original question number, or stem is rejected (compare against `main`).

Honest limits (put these in README too):
- Checks 4 and 5 prove nothing was *skipped*, not that the meaning was *kept*. The author's spot-check and the verifier still matter.
- The identifier scan catches obvious slips only. It does not replace a human check.

**`scripts/build_facts.py`:** gathers all per-batch files in `facts/<topic>/` into `facts/<topic>/_merged.md`, grouped by subject, with each line tagged by its source file, and flags exact duplicate lines. The output is generated and must never be edited by hand. It uses no tokens.

**`.github/workflows/validate.yml`:** runs `validate.py` on pull requests and on pushes to `main`. Keep it light: check GitHub's current free-plan limits for Actions on private repos.

---

## H. Workflow for contributors

1. Paste your material (notes, dump, pearls, exam) into your Claude and say your G. Small pearls can be batched into one paste at the end of the week.
2. Claude saves the original to `raw/`, converts it, and shows you the result. Fix anything wrong.
3. Run the validator, push a branch, open a pull request.
4. Notes, facts, and exams merge once the validator passes. They are labeled `ai-generated`.
5. Later, a second person verifies (see A7 for facts files) and sets `human-verified`.
6. After merge: case and concept notes over about 400 words get a digest. Facts are regrouped by `build_facts.py`.
7. When 2+ Gs have material on a topic, one person runs `compare-across-g.md`. A different person approves it before it merges.
8. Anyone can then run `make-quiz.md`.

---

## I. README (create with this content)

```markdown
# Surgery Pool

Private study repo for our surgery rotation. Each of us sees only one of G1-G4;
together we cover all four.

- Add: paste your material (any messy form) into your Claude with the prompt in
  prompts/convert-notes.md and say your G. Review the result, then open a PR.
- Read: start from synthesis/, digests/, and facts/<topic>/_merged.md.
  Open raw notes only when needed.
- Exams: one folder per set in exams/. Original question numbers never change.
- Rules: see CLAUDE.md. No patient identifiers, ever, including in raw/.
- Status: ai-generated means unchecked. human-verified means a second person checked it.
- Limits: the automatic checks catch skipped content and obvious identifiers, not wrong
  meaning. Verify against the textbook or your attending before relying on anything.
```

---

## J. Owner checklist (you do these, not Claude Code)

1. Create a **private** GitHub repo named `surgery-pool`.
2. Invite your pilot friend: repo Settings → Collaborators. Follow GitHub's current instructions.
3. Clone the repo to your computer and open Claude Code in that folder.
4. Give Claude Code this instruction: *"Read surgery-repo-spec-final.md and build the repo exactly as specified. Test the scripts with invented sample data only and show me results before committing."*
5. Review the result, then push.
6. At the end of the pilot, add a second admin so the repo does not depend on one account.

---

## K. Deliberately left out
- Lectures (A4), may be added later
- A web front-end
- Enforced branch protection (free private repos may not support it; check GitHub's current rules)
- Image handling beyond flagging
- Semantic de-duplication of near-identical facts across people (the script catches exact duplicates only)

---

## L. Pilot plan and success checklist

**Who and what:** owner + 1 friend in a different G, 3 topics chosen from A6 (default: `acute-abdomen` plus two that match your two Gs), 2 weeks.

After 2 weeks, check:
1. The friend converted a real dump in about 10 minutes without help.
2. The validator did not block them with false alarms, and it caught a deliberately planted fake identifier in a test.
3. The coverage check passed on their facts file.
4. The other person found a digest useful, with the key pearls kept.
5. One cross-G synthesis was built and approved by a second person.
6. Both found the exam format workable, if an exam set was added.

If all pass, invite the rest of the group. If any fail, fix the template, prompt, or validator first. IDs cannot change after merge, which is why the pilot is small.
