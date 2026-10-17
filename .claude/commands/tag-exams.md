---
description: Tag past-exam questions with a topic and question type, then rebuild the exam topic map
---

Tag exam questions for the exam topic map. Plain language, no git jargon. Follow CLAUDE.md
("Exam topic map"). $ARGUMENTS may name set codes; otherwise tag every merged exam that has no
complete tag file.

1. Get the latest: switch to `main`, pull, create branch `tags/<YYYY-MM-DD>` (add `-2` if it exists).
2. Find the work: run `python3 scripts/validate.py` and read the "no topic tags yet" note and the
   "not tagged yet" warnings. Show me the list and how many questions that is.
3. For each paper, read exams/<set>/exam.md and write exam-map/tags/<set>.md:
   ```
   # Topic tags: <set>
   - Q1 | thyroid-mass | investigation
   ```
   - One line per question, using the question's original number. Never edit exam.md itself.
   - topic: the most specific topic in INDEX.md "## Topics" that fits the question's main point.
     Reuse before creating. If none fits, add a new topic under the right organ-system `###`
     heading in INDEX.md (or a new organ-system heading); never under a G, and never a
     near-duplicate. Questions that look like a subspecialty (pediatric, colorectal, uro, neuro,
     CVT, plastic) get ordinary topics under an organ-system heading (e.g. `intussusception`
     under "Pediatric surgery"): General Sx papers are General Surgery in full, and OSCE/MEQ
     papers combine General Surgery and subspecialty content. Only subspecialty MCQ papers (`-subspe-...-mcq`) are not tagged into the map.
   - asks: diagnosis | investigation | management | complication | basic-science | other.
     Pick what the question wants the student to produce, not the disease's main theme.
   - Judge from the stem, choices and key only; do not add facts. If a question is too garbled
     to tell, use topic of the closest fit and asks `other`, and list it for me.
4. Save after every paper: commit, push. Run `python3 scripts/validate.py` (0 errors).
5. Rebuild the map: `python3 scripts/exam_map.py`, send me exam-map/index.html as a file, and
   tell me: new topics added (with their organ system), questions marked `other`, and the topics
   in "Examined, but nothing to study from in the repo yet".
6. Open a pull request titled "Exam tags <date>" and give me its link.
