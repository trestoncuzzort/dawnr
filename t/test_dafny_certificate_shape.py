"""test_dafny_certificate_shape.py: the certificate-shape check of the Dafny
verifier (t/verifiers/dafny.py, `_certificate_shape`) and the one declaration
kind it admits beyond function/method/lemma since 2026-09-28: a bare datatype
(SPEC.md "Datatypes (v1)"). Pure text: it reads rprint-shaped programs the
way the verifier does, no dafny binary needed."""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from verifiers import dafny as D                                   # noqa: E402

CERT = """lemma t_refutation_certificate()
  ensures false
{
}
"""
METHOD = """method M(c: Color) returns (r: int)
  ensures r >= 0
{
  r := 0;
}
"""


def shape(*decls: str) -> str:
    return D._certificate_shape("\n".join(decls))[1]


class BareDatatypesAreInert(unittest.TestCase):
    def test_an_enum_beside_the_certificate_keeps_the_honest_shape(self) -> None:
        self.assertEqual(shape("datatype Color = Red | Green | Blue", METHOD, CERT), "")

    def test_a_record_with_plain_fields_keeps_it(self) -> None:
        self.assertEqual(shape("datatype Point = Point(x: int, y: seq<int>, ok: bool)", METHOD, CERT), "")

    def test_without_the_certificate_the_reason_is_still_the_missing_lemma(self) -> None:
        self.assertIn("no `lemma", shape("datatype Color = Red | Green", METHOD))


class EverythingElseStillRefuses(unittest.TestCase):
    def assertRefused(self, *decls: str) -> None:
        self.assertNotEqual(shape(*decls), "", decls[0])

    def test_an_attribute_on_the_datatype(self) -> None:
        self.assertRefused("datatype {:fuel 3} Color = Red | Green", METHOD, CERT)

    def test_a_modern_attribute_form(self) -> None:
        self.assertRefused("datatype @Axiom Color = Red | Green", METHOD, CERT)

    def test_an_attribute_on_a_constructor(self) -> None:
        self.assertRefused("datatype Color = Red {:x} | Green", METHOD, CERT)

    def test_a_member_body(self) -> None:
        self.assertRefused("datatype Color = Red | Green {", "  function F(): int { 0 }", "}", METHOD, CERT)

    def test_a_real_field(self) -> None:
        self.assertRefused("datatype P = P(x: real)", METHOD, CERT)

    def test_a_field_of_another_datatype(self) -> None:
        self.assertRefused("datatype P = P(c: Color)", METHOD, CERT)

    def test_a_ghost_modifier(self) -> None:
        self.assertRefused("ghost datatype Color = Red | Green", METHOD, CERT)

    def test_a_codatatype(self) -> None:
        self.assertRefused("codatatype Stream = Cons(h: int)", METHOD, CERT)

    def test_a_name_declared_twice(self) -> None:
        self.assertIn("declared twice", shape("datatype M = A | B", METHOD.replace("method M", "method M"), CERT) if False else shape("datatype Color = A | B", "datatype Color = C | D", METHOD, CERT))

    def test_an_axiom_lemma_beside_the_certificate(self) -> None:
        self.assertRefused("datatype Color = Red | Green", "lemma {:axiom} L()\n  ensures false", METHOD, CERT)

    def test_a_type_synonym_is_still_outside(self) -> None:
        self.assertRefused("type Small = x: int | 0 <= x < 10", METHOD, CERT)


if __name__ == "__main__":
    unittest.main()
