"""Encoding a corpus is a pure function of the text and the tokenizer.

Measured 2026-09-20: the frozen source corpus costs about 77 seconds to encode
at every training start, and a six-arm study pays it twelve times for text that
never changes. These tests cover the cache that stops that, and the property
that makes it safe: a hit is only possible for the exact (text, tokenizer) pair
that produced it.
"""
import os
import tempfile
import unittest

from data import CharTokenizer, cached_encode, TOKEN_CACHE_ENV

TEXT = "t 1\ntask f(x: int) returns (r: int)\n  ensures r == x\n{\n  r := x;\n}\n"


class TokenCacheTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = CharTokenizer.from_text(TEXT + "0123456789")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(os.environ.pop, TOKEN_CACHE_ENV, None)

    def test_off_by_default_and_identical_when_on(self):
        os.environ.pop(TOKEN_CACHE_ENV, None)
        plain = cached_encode(self.tokenizer, TEXT)
        os.environ[TOKEN_CACHE_ENV] = self.directory.name
        self.assertEqual(cached_encode(self.tokenizer, TEXT), plain)      # cold, writes
        self.assertEqual(cached_encode(self.tokenizer, TEXT), plain)      # warm, reads
        self.assertEqual(self.tokenizer.decode(plain), TEXT)

    def test_a_hit_requires_the_same_text(self):
        os.environ[TOKEN_CACHE_ENV] = self.directory.name
        first = cached_encode(self.tokenizer, TEXT)
        other = cached_encode(self.tokenizer, TEXT + "\n")
        self.assertNotEqual(first, other)
        self.assertEqual(self.tokenizer.decode(other), TEXT + "\n")

    def test_a_hit_requires_the_same_tokenizer(self):
        os.environ[TOKEN_CACHE_ENV] = self.directory.name
        mine = cached_encode(self.tokenizer, TEXT)
        theirs = cached_encode(CharTokenizer.from_text(TEXT[::-1] + "zq"), TEXT)
        self.assertNotEqual(mine, theirs)

    def test_an_unwritable_cache_directory_is_not_a_failure(self):
        os.environ[TOKEN_CACHE_ENV] = "/proc/nonexistent-cache-directory"
        self.assertEqual(cached_encode(self.tokenizer, TEXT),
                         self.tokenizer.encode(TEXT))

    def test_a_corrupt_entry_is_a_miss_not_an_error(self):
        os.environ[TOKEN_CACHE_ENV] = self.directory.name
        expected = cached_encode(self.tokenizer, TEXT)
        for entry in os.listdir(self.directory.name):
            with open(os.path.join(self.directory.name, entry), "wb") as handle:
                handle.write(b"\x00\x01\x02")          # not a whole int32 stream
        self.assertEqual(cached_encode(self.tokenizer, TEXT), expected)


if __name__ == "__main__":
    unittest.main()
