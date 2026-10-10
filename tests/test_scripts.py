"""Tests for scripts/validate.py and scripts/build_facts.py.

Run:  python3 -m unittest discover -s tests -v

Every sample below is INVENTED. Nothing here is real patient or personal data. Each test builds
a throwaway repo in a temp folder, so the real notes/, facts/ ... folders are never touched.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def front(**kw):
    fields = dict(id="x-001", type="concept-note", topic="sample-topic", group="G1", source="mixed",
                  author="alice", date="2026-10-10", status="ai-generated", verified_by="", raw="",
                  references="[]")
    fields.update(kw)
    lines = [f"{k}: {v}" for k, v in fields.items() if v is not None]
    return "---\n" + "\n".join(lines) + "\n---\n"


INDEX = """# Index

## Topics
- `sample-topic` — invented
- `other-topic` — invented

## Notes
"""

RAW = """# Invented dump
widgetitis: first invented fact
widgetitis: second invented fact

half-written fragment
gadgetosis: third invented fact
"""

FACTS = front(id="facts-sample-001", type="facts-note", raw="raw/alice/batch1.md") + """
## Widgets
- widgetitis: first invented fact [L2]
- widgetitis: second invented fact [L3]

## Gadgets
- gadgetosis: third invented fact [L6]

## Needs clarification (original text kept)
- "half-written fragment" [L5]
"""

CASE = front(id="case-sample-001", type="case-note") + """
# Invented complaint

## Patient (de-identified)
60s F, week W1.

## History: key positives and negatives
Invented history.

## Differential diagnosis (from H&P only)
| Diagnosis | For (from Hx/PE) | Against (from Hx/PE) |
| --- | --- | --- |
| Disease Alpha | feature one | feature two |
| Disease Beta | feature three | feature four |

## Management and surgical indication
Invented.
"""

DIGEST = front(id="digest-sample-001", type="digest", digest_of="case-sample-001") + """
# Digest: Invented complaint

**One line:** invented

**DDx, ranked:** Disease Alpha (feature one); Disease Beta (feature three)

**Pearls:** none

**Left out:** nothing important

**Source note:** case-sample-001 (open it for full detail)
"""

EXAM = front(id="exam-seta-001", type="exam", topic="", group="cross", source="exam-recall",
             exam_set="set-a", exam_format="mcq", exam_year="2026", exam_rotation="G1",
             answer_source="recalled", references=None) + """
## Q1 (original no. 1)
An invented patient presents with invented symptoms. What is the next step?

A. Option one
B. Option two is somewhat longer
C. Option three
D. Option four
E. Option five

**Answer:** A
**Explanation:** Because invented. B is wrong because invented too.
**Guideline / source:** not stated

## Q2 (original no. 2)
Another invented stem.

A. Alpha
B. Beta
C. Gamma
D. Delta

**Answer:** C
**Explanation:** Invented reasoning.
**Guideline / source:** not stated
"""

WARD = front(id="ward-sample-001", type="ward-guide", topic="", group="cross", source="survival-guide",
             valid_year="2026") + """
# Invented survival guide

## Daily routine and people
Round 05.45, lecture 08.00 - 09.00/10.00. Dr Invented Name rounds with the senior resident.
BP target 120/80 for the invented example. See https://example.invalid/watch?v=1234567890.
เวรศัลย์ ราวน์เช้า 7 โมง อาจารย์ดุ แต่สอนดี 55555555555

## Out of scope for now (subspecialty, original text kept)
Invented subspecialty paragraph.
"""

FILES = {
    "INDEX.md": INDEX,
    "raw/alice/batch1.md": RAW,
    "facts/sample-topic/alice-001.md": FACTS,
    "notes/sample-topic/case-001.md": CASE,
    "digests/sample-topic/case-001-digest.md": DIGEST,
    "exams/set-a/exam.md": EXAM,
    "exams/set-a/images/set-a-q01-1.png": "not a real image",
    "ward-guide/guide-001.md": WARD,
}


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="surgery-test-"))
        for rel, text in FILES.items():
            self.write(rel, text)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def read(self, rel):
        return (self.tmp / rel).read_text(encoding="utf-8")

    def validate(self, *extra):
        r = subprocess.run([sys.executable, str(SCRIPTS / "validate.py"), "--root", str(self.tmp), *extra],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def build(self, *extra):
        r = subprocess.run([sys.executable, str(SCRIPTS / "build_facts.py"), "--root", str(self.tmp), *extra],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.tmp), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        *args], check=True, capture_output=True)

    def commit_all(self):
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")

    def assertFails(self, needle, *extra):
        code, out = self.validate(*extra)
        self.assertEqual(code, 1, out)
        self.assertIn(needle, out)
        return out

    def assertPasses(self, *extra):
        code, out = self.validate(*extra)
        self.assertEqual(code, 0, out)
        return out


class ValidSample(RepoCase):
    def test_sample_passes_without_false_alarms(self):
        out = self.assertPasses()
        self.assertIn("0 errors", out)
        # the sample deliberately contains times, a blood pressure, a URL with digits and Thai text
        self.assertNotIn("possible patient identifier", out)

    def test_image_is_flagged_for_manual_review(self):
        self.assertIn("image: check by eye", self.assertPasses())


class FrontMatter(RepoCase):
    def test_missing_field(self):
        self.write("notes/sample-topic/case-001.md", CASE.replace("author: alice\n", ""))
        self.assertFails("front-matter field 'author' is missing")

    def test_bad_group_and_subspecialty_group(self):
        self.write("notes/sample-topic/case-001.md", CASE.replace("group: G1", "group: G7"))
        self.assertFails("group: 'G7'")
        self.write("notes/sample-topic/case-001.md", CASE.replace("group: G1", "group: Colo"))
        self.assertFails("subspecialties are out of scope")

    def test_type_must_match_folder(self):
        self.write("notes/sample-topic/case-001.md", CASE.replace("type: case-note", "type: facts-note"))
        self.assertFails("does not belong in notes/")

    def test_duplicate_id(self):
        self.write("notes/sample-topic/case-002.md", CASE)
        self.assertFails("is also used by")

    def test_verifier_must_be_second_person(self):
        text = CASE.replace("status: ai-generated", "status: human-verified")
        self.write("notes/sample-topic/case-001.md", text)
        self.assertFails("human-verified needs verified_by")
        self.write("notes/sample-topic/case-001.md", text.replace("verified_by: ", "verified_by: alice"))
        self.assertFails("must be a second person")
        self.write("notes/sample-topic/case-001.md", text.replace("verified_by: ", "verified_by: bob"))
        self.assertPasses()

    def test_ward_guide_needs_valid_year(self):
        self.write("ward-guide/guide-001.md", WARD.replace("valid_year: 2026\n", ""))
        self.assertFails("valid_year is required")

    def test_valid_year_may_be_unknown_but_not_garbage(self):
        self.write("ward-guide/guide-001.md", WARD.replace("valid_year: 2026", "valid_year: unknown"))
        self.assertPasses()
        self.write("ward-guide/guide-001.md", WARD.replace("valid_year: 2026", "valid_year: soon"))
        self.assertFails("valid_year must be 4 digits")

    def test_ward_guide_with_raw_must_account_for_every_line(self):
        raw = "# Invented guide\nRound at dawn\nLecture at noon\n"
        self.write("raw/alice/guide.md", raw)
        guide = WARD.replace("raw: \n", "raw: raw/alice/guide.md\n")
        guide = guide.replace("Round 05.45, lecture", "- Round at dawn [L2]\n- Lecture at noon [L3]\nRound 05.45, lecture")
        self.write("ward-guide/guide-001.md", guide)
        self.assertPasses()
        self.write("ward-guide/guide-001.md", guide.replace("- Lecture at noon [L3]\n", ""))
        self.assertFails("raw line 3 of raw/alice/guide.md")
        self.write("ward-guide/guide-001.md", guide.replace("Lecture at noon [L3]", "Lecture at noon"))
        self.assertFails("fact line without a raw line tag")

    def test_near_duplicate_topic_is_only_a_warning(self):
        self.write("notes/sample-topics/case-002.md",
                   CASE.replace("case-sample-001", "case-sample-002").replace("topic: sample-topic", "topic: sample-topics"))
        out = self.assertPasses()
        self.assertIn("near-duplicate of 'sample-topic'", out)


class IdentifierScan(RepoCase):
    def test_planted_identifiers_are_caught_and_masked(self):
        self.write("raw/alice/batch1.md", RAW + "seen HN 12345678\ntel 081-234-5678\nadmitted 12/03/2026\nID 7654321\n")
        code, out = self.validate()
        self.assertEqual(code, 1, out)
        for label in ("HN/AN number", "phone number", "full date", "long digit string"):
            self.assertIn(label, out)
        for secret in ("12345678", "081-234-5678", "12/03/2026", "7654321"):
            self.assertNotIn(secret, out)  # the log never repeats the identifier

    def test_thai_laugh_is_not_an_identifier_but_55_inside_a_number_is(self):
        self.write("raw/alice/batch1.md", RAW + "funny 5555555555\n")  # only 5s: the Thai laugh
        out = self.validate()[1]
        self.assertNotIn("possible patient identifier", out)
        self.write("raw/alice/batch1.md", RAW + "number 55555512\n")
        self.assertFails("long digit string")

    def test_thai_and_month_dates(self):
        self.write("notes/sample-topic/case-001.md", CASE + "\nadmitted 3 March 2026 and 5 ม.ค. 69\n")
        self.assertFails("date with month name")

    def test_identifier_in_front_matter_date_is_not_flagged(self):
        self.assertPasses()  # date: 2026-10-10 sits in every sample file


class Digests(RepoCase):
    def test_missing_left_out_line(self):
        self.write("digests/sample-topic/case-001-digest.md", DIGEST.replace("**Left out:** nothing important\n", ""))
        self.assertFails("no 'Left out' line")

    def test_missing_ddx(self):
        self.write("digests/sample-topic/case-001-digest.md", DIGEST.replace("Disease Beta (feature three)", "something else"))
        self.assertFails("DDx 'Disease Beta'")

    def test_too_long(self):
        self.write("digests/sample-topic/case-001-digest.md", DIGEST + "\n" + "word " * 460)
        self.assertFails("max 450")

    def test_unknown_source_note(self):
        self.write("digests/sample-topic/case-001-digest.md", DIGEST.replace("digest_of: case-sample-001", "digest_of: nope-001"))
        self.assertFails("does not match any file id")

    def test_digest_must_mention_its_note(self):
        self.write("digests/sample-topic/case-001-digest.md", DIGEST.replace("**Source note:** case-sample-001", "**Source note:** the note"))
        self.assertFails("does not link to its note")


class FactsCoverage(RepoCase):
    def test_uncovered_raw_line(self):
        self.write("raw/alice/batch1.md", RAW + "unlisted: extra fact\n")
        self.assertFails("raw line 7")

    def test_fact_without_tag(self):
        self.write("facts/sample-topic/alice-001.md", FACTS.replace("third invented fact [L6]", "third invented fact"))
        out = self.assertFails("fact line without a raw line tag")
        self.assertIn("raw line 6", out)

    def test_out_of_scope_section_counts_as_covered(self):
        self.write("raw/alice/batch1.md", RAW + "colorectal-ish line\n")
        self.write("facts/sample-topic/alice-001.md",
                   FACTS + '\n## Out of scope for now (subspecialty, original text kept)\n- "colorectal-ish line" [L7]\n')
        self.assertPasses()

    def test_range_and_list_tags(self):
        self.write("facts/sample-topic/alice-001.md",
                   FACTS.replace("[L2]", "[L2-3]").replace("- widgetitis: second invented fact [L3]\n", ""))
        self.assertPasses()

    def test_missing_raw_file(self):
        self.write("facts/sample-topic/alice-001.md", FACTS.replace("batch1.md", "gone.md"))
        self.assertFails("not found under raw/")


class Exams(RepoCase):
    def test_duplicate_number(self):
        self.write("exams/set-a/exam.md", EXAM.replace("## Q2 (original no. 2)", "## Q1 (original no. 1)"))
        self.assertFails("appears more than once")

    def test_renumbered_question(self):
        self.write("exams/set-a/exam.md", EXAM.replace("## Q2 (original no. 2)", "## Q2 (original no. 9)"))
        self.assertFails("never renumbered")

    def test_missing_explanation(self):
        self.write("exams/set-a/exam.md", EXAM.replace("**Explanation:** Invented reasoning.\n", ""))
        self.assertFails("missing or empty 'Explanation'")

    def test_answer_not_among_options(self):
        self.write("exams/set-a/exam.md", EXAM.replace("**Answer:** C", "**Answer:** G"))
        self.assertFails("answer G is not one of the options")

    def test_image_must_start_with_set_code(self):
        self.write("exams/set-a/images/wrongname.png", "x")
        self.assertFails("must start with the set code")

    def test_longest_correct_option_is_a_warning(self):
        self.write("exams/set-a/exam.md", EXAM.replace("C. Gamma", "C. Gamma, which is clearly the longest"))
        self.assertIn("longest option", self.assertPasses())

    def test_exam_set_must_match_folder(self):
        self.write("exams/set-a/exam.md", EXAM.replace("exam_set: set-a", "exam_set: set-b"))
        self.assertFails("must equal the folder name")

    def test_osce_and_meq_formats(self):
        osce = front(id="exam-seto-001", type="exam", topic="", group="cross", source="exam-recall",
                     exam_set="set-o", exam_format="osce", exam_year="2026", exam_rotation="G1",
                     answer_source="recalled", references=None) + """
## Q1 (original no. 1)
Close the invented wound.

**Station type:** suturing
**Checklist:** washes hands
puts on gloves
**Explanation:** invented
**Guideline / source:** not stated
"""
        self.write("exams/set-o/exam.md", osce)
        self.assertPasses()
        self.write("exams/set-o/exam.md", osce.replace("**Checklist:** washes hands\nputs on gloves\n", ""))
        self.assertFails("missing or empty 'Checklist'")


class AgainstBase(RepoCase):
    def test_unchanged_tree_passes(self):
        self.commit_all()
        self.assertPasses("--base", "HEAD")

    def test_stem_change_rejected_but_explanation_change_allowed(self):
        self.commit_all()
        self.write("exams/set-a/exam.md", EXAM.replace("Because invented.", "Corrected reasoning."))
        self.assertPasses("--base", "HEAD")
        self.write("exams/set-a/exam.md", EXAM.replace("Another invented stem.", "A reworded stem."))
        self.assertFails("the stem of a merged question was changed", "--base", "HEAD")

    def test_exam_year_and_rotation_immutable(self):
        self.commit_all()
        self.write("exams/set-a/exam.md", EXAM.replace("exam_year: 2026", "exam_year: 2027"))
        self.assertFails("exam_year changed", "--base", "HEAD")
        self.write("exams/set-a/exam.md", EXAM.replace("exam_rotation: G1", "exam_rotation: G2"))
        self.assertFails("exam_rotation changed", "--base", "HEAD")

    def test_removed_question_and_deleted_exam(self):
        self.commit_all()
        self.write("exams/set-a/exam.md", EXAM.split("## Q2")[0])
        self.assertFails("Q2 was removed", "--base", "HEAD")
        (self.tmp / "exams/set-a/exam.md").unlink()
        self.assertFails("may not be deleted", "--base", "HEAD")

    def test_id_is_immutable(self):
        self.commit_all()
        self.write("notes/sample-topic/case-001.md", CASE.replace("id: case-sample-001", "id: case-renamed-001"))
        self.assertFails("Ids never change", "--base", "HEAD")

    def test_new_file_cannot_start_verified(self):
        self.commit_all()
        new = CASE.replace("case-sample-001", "case-sample-002").replace(
            "status: ai-generated", "status: human-verified").replace("verified_by: ", "verified_by: bob")
        self.write("notes/sample-topic/case-002.md", new)
        self.assertFails("new files must start as ai-generated", "--base", "HEAD")

    def test_bad_base_ref(self):
        self.commit_all()
        self.assertFails("cannot resolve base ref", "--base", "no-such-ref")


class BuildFacts(RepoCase):
    def second_batch(self):
        self.write("raw/bob/batch1.md", "# Another dump\nwidgetitis: first invented fact\nhatstand: invented fact\n")
        self.write("facts/sample-topic/bob-001.md",
                   front(id="facts-sample-002", type="facts-note", author="bob", raw="raw/bob/batch1.md") + """
## Widgets
- widgetitis: first invented fact [L2]
- hatstand: invented fact [L3]
""")

    def test_merge_groups_tags_and_flags_duplicates(self):
        self.second_batch()
        code, out = self.build()
        self.assertEqual(code, 0, out)
        merged = self.read("facts/sample-topic/_merged.md")
        self.assertIn("GENERATED", merged)
        self.assertIn("### widgetitis", merged)
        self.assertIn("first invented fact [L2] <alice-001>", merged)
        self.assertIn("exact duplicate", merged)
        self.assertIn("## Needs clarification", merged)
        self.assertIn('"half-written fragment" [L5]', merged)
        self.assertIn("| alice-001 | facts-sample-001 | alice | G1 | ai-generated |", merged)
        self.assertPasses()  # _merged.md must not confuse the validator

    def test_idempotent_and_check_mode(self):
        self.assertEqual(self.build("--check")[0], 1)  # nothing generated yet
        self.build()
        code, out = self.build()
        self.assertIn("up to date", out)
        self.assertEqual(self.build("--check")[0], 0)
        self.write("facts/sample-topic/alice-001.md", FACTS + "- gadgetosis: late fact [L6]\n")
        self.assertEqual(self.build("--check")[0], 1)

    def test_out_of_scope_kept_separate(self):
        self.write("raw/alice/batch1.md", RAW + "colorectal-ish line\n")
        self.write("facts/sample-topic/alice-001.md",
                   FACTS + '\n## Out of scope for now (subspecialty, original text kept)\n- "colorectal-ish line" [L7]\n')
        self.build()
        merged = self.read("facts/sample-topic/_merged.md")
        self.assertIn("## Out of scope for now (subspecialty)", merged)
        self.assertNotIn("### colorectal", merged)


if __name__ == "__main__":
    unittest.main()
