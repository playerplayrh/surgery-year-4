---
description: Look something up in the repo cheaply (textbook, exams, tags, ward guides, notes) with scripts/find.py
---

Answer the lookup question in $ARGUMENTS using `scripts/find.py` only. Read-only: create and edit nothing.
If this chat's history is already long, say so and suggest a new chat for lookups; it is cheaper.

Steps, in this order, stopping as soon as you can answer:
1. `python3 scripts/find.py topic <name>` for a topic (INDEX.md topic, tagged exam questions, textbook files).
   If it lists several topics, pick the matching one or ask which.
2. `python3 scripts/find.py search <term> [more terms] [--in textbook,exams,tags,ward,notes,all] [--any]`.
   All terms must be in the same section by default. Try English and Thai spellings. Raise `--max` only if needed.
3. `python3 scripts/find.py outline <file>` to see a file's headings and line numbers.
4. `python3 scripts/find.py read <file>:<a>-<b>` for only the lines you need. Never cat a whole file or use grep.

Report as a table `source | file:line | what it says` (what it says: under 20 words, paraphrased):
- Group rows by organ system / topic (the `###` headings of INDEX.md). Never by G1-G4.
- Cite exam questions as set code + question number (e.g. mdcu76-gen-c-mcq Q12). If the script shows
  `[student-key]`, say the answer is a student-written key, not official.
- Everything in this repo is ai-generated unless its front-matter says human-verified; say so when it matters.
- Add no outside facts. If the repo does not cover the question, say so plainly.
- Stop at about 10 hits, then give the counts the script printed and how to narrow the search.
- Names of staff in ward guides are kept as written; never write patient identifiers.
