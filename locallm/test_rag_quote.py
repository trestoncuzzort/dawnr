"""rag_quote.py: GopherCite's inline-evidence syntax (arXiv:2203.11147 2.1), the verbatim check, the support rule."""
import unittest

from locallm import rag_quote as rq

DOCS = ["The documentary premiered on CNN on January 2, 2022.\nIt is directed by Frank   Marshall.",
        "Iga Świątek won the 2022 French Open, beating Coco Gauff."]


class Quote(unittest.TestCase):
    def test_parse_two_claims(self):
        r = "%<Frank Marshall>%(Document 1)%[It is directed by Frank Marshall.]% %<January 2, 2022>%(Document 1)%[premiered on CNN on January 2, 2022.]%"
        self.assertEqual(len(rq.parse(r)), 2)
        self.assertTrue(rq.verdict(r, DOCS)["shown"])

    def test_quote_not_in_any_document_is_refused(self):
        r = "%<Frank Marshall>%(Document 1)%[The film was directed by Frank Marshall.]%"
        v = rq.verdict(r, DOCS)
        self.assertFalse(v["verbatim"]); self.assertFalse(v["shown"])

    def test_claim_not_in_its_quote_is_refused(self):
        r = "%<Steven Spielberg>%(Document 1)%[It is directed by Frank Marshall.]%"
        v = rq.verdict(r, DOCS)
        self.assertTrue(v["verbatim"]); self.assertFalse(v["supported"]); self.assertFalse(v["shown"])

    def test_diacritics_and_whitespace_fold(self):
        r = "%<Iga Swiatek>%(Document 2)%[Iga Świątek won the 2022 French Open]%"
        self.assertTrue(rq.verdict(r, DOCS)["shown"])
        r2 = "%<Frank Marshall>%(Document 1)%[It is directed by Frank Marshall.]%"
        self.assertTrue(rq.verdict(r2, DOCS)["verbatim"])          # three spaces in the document

    def test_prose_and_rejection(self):
        self.assertFalse(rq.verdict("Frank Marshall directed it.", DOCS)["shown"])
        v = rq.verdict("I can not answer the question because of the insufficient information in documents.", DOCS)
        self.assertTrue(v["rejected"]); self.assertFalse(v["shown"])

    def test_messages_number_the_documents(self):
        m = rq.messages("q?", ["a", "b"])
        self.assertIn("%<", m[0]["content"]); self.assertIn("Document 2:\nb", m[1]["content"])


if __name__ == "__main__":
    unittest.main()
