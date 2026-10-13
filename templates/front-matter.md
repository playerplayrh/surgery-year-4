# Front-matter schema

Top of every file in notes/, facts/, exams/, digests/, synthesis/, textbook-map/ and
ward-guide/ (except `_merged.md` and files starting with `_`). Raw files have none.

```yaml
---
id: facts-example-001              # unique, never changed after merge
type: facts-note                   # case-note | concept-note | facts-note | exam | digest | synthesis | textbook-map | ward-guide
topic: abdominal-pain              # reuse a topic from INDEX.md; blank for exams and ward guides
group: G1                          # optional: where the author met it (G1 | G2 | G3 | G4 | cross); never used to organise content
source: mixed                      # bedside | textbook | lecture | exam-recall | senior-summary | survival-guide | mixed | unknown
author: github-username
date: 2026-10-10                   # date written, NOT the patient encounter
status: ai-generated               # ai-generated | human-verified
verified_by:                       # filled when verified; must be someone other than the author
raw:                               # raw file this was converted from, e.g. raw/alice/batch1.md (required for facts-note; a ward-guide that gives it is checked the same way)
references: []                     # textbook section or page, if any (keys in textbook-map/_keys.md)
digest_of:                         # digests only: id of the source note
built_from: []                     # synthesis only: ids of the sources used
exam_set:                          # exams only: set code, same as the folder name
exam_format:                       # exams only: mcq | meq | osce
exam_year:                         # exams only: e.g. 2026
exam_rotation:                     # exams only: e.g. G3 or "General Sx"
answer_source:                     # exams only: official | recalled | ai-derived
valid_year:                        # ward-guide, and anything from senior-summary or survival-guide: the year it was written for (4 digits, or unknown if the source does not say)
---
```

- `id` is immutable after merge.
- `status` starts as `ai-generated` for **every** type. Only a second person sets `human-verified`.
- `group` has no subspecialty values on purpose: subspecialties are out of scope for now.
