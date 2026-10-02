"""rag_cite.py: the documents of each condition, the per-question grammar, parsing, HotpotQA's normalisation."""
import unittest

from locallm import rag_cite as rc

ROW = {"id": "q1", "question": "Who directed it?", "answer": "Frank Marshall", "type": "bridge",
       "supporting_facts": {"title": ["A", "B"], "sent_id": [0, 0]},
       "context": {"title": ["A", "B", "C", "D", "E", "F"],
                   "sentences": [["It was directed by Frank Marshall.", " It premiered in 2022."], ["B one."], ["C one."],
                                 ["D one."], ["E \"quoted\" one."], ["F one."]]}}


class Cite(unittest.TestCase):
    def test_conditions(self):
        p = {d["title"] for d in rc.documents(ROW, "present")}
        a = {d["title"] for d in rc.documents(ROW, "absent")}
        self.assertTrue({"A", "B"} <= p and len(p) == 5)
        self.assertFalse({"A", "B"} & a)
        self.assertEqual(rc.documents(ROW, "present"), rc.documents(ROW, "present"))     # seeded

    def test_grammar_binds_each_citation_to_its_own_sentences(self):
        docs = rc.documents(ROW, "present")
        g = rc.grammar(docs)
        k = [d["title"] for d in docs].index("A") + 1
        line = [l for l in g.splitlines() if l.startswith(f"c{k} ::=")][0]
        self.assertIn('"It was directed by Frank Marshall."', line)
        self.assertNotIn("B one.", line)
        self.assertIn("root ::= reject | claims", g)
        self.assertIn('\\"quoted\\"', rc.grammar(rc.documents(ROW, "absent")) + rc.grammar(docs))

    def test_parse_and_right(self):
        r = "%<Frank Marshall>%(Document 2)%[It was directed by Frank Marshall.]%"
        self.assertEqual(rc.parse(r), [("Frank Marshall", 2, "It was directed by Frank Marshall.")])
        self.assertTrue(rc.right(r, "Frank Marshall"))
        self.assertFalse(rc.right("%<Steven Spielberg>%(Document 2)%[It was directed by Frank Marshall.]%", "Frank Marshall"))
        self.assertEqual(rc.norm("The  Frank-Marshall!"), "frankmarshall")

    def test_sample_keeps_bridge_questions_only(self):
        rows = [dict(ROW, id="a"), dict(ROW, id="b", type="comparison"), dict(ROW, id="c", answer="yes")]
        self.assertEqual([r["id"] for r in rc.sample(rows, 10)], ["a"])

    def test_report(self):
        rows = [{"id": "q1", "condition": "present", "reply": "%<Frank Marshall>%(Document 1)%[x]%", "answer": "Frank Marshall"},
                {"id": "q2", "condition": "absent", "reply": rc.REJECT, "answer": "z"},
                {"id": "q3", "condition": "absent", "reply": "%<Oslo>%(Document 1)%[y]%", "answer": "Paris"}]
        rep = rc.report(rows, {("q1", "present"): [0.9], ("q3", "absent"): [0.2]})
        self.assertEqual((rep["present"]["shown at 0.5"], rep["present"]["shown and right at 0.5"]), (1, 1))
        self.assertEqual((rep["absent"]["refused"], rep["absent"]["shown at 0.5"]), (1, 0))


if __name__ == "__main__":
    unittest.main()
