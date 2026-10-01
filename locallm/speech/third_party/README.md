# Third-party code

`whisper_normalizer/` is Whisper's text normaliser, copied unchanged from
github.com/openai/whisper (`whisper/normalizers/`, MIT licence, `whisper_normalizer/LICENSE`) on
2026-10-01, so that a word error rate here is computed the way the Whisper paper computes it
(arXiv:2212.04356, appendix D). It needs the `regex` and `more_itertools` packages.
