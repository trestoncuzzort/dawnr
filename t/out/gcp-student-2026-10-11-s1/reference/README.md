# MBPP+ evaluation references

`mbppplus.jsonl` retains only `task_id` and `code` from the 378 rows of
[evalplus/mbppplus](https://huggingface.co/datasets/evalplus/mbppplus), revision
`b2d74c91837c3f2a20c1299ae98133cbe7cfa077`. The source is
`data/test-00000-of-00001-d5781c9c51e02795.parquet`; extraction uses PyArrow's
`read_table(...).to_pylist()` and serializes those two fields in source order.

The source dataset card declares Apache-2.0; [LICENSE](LICENSE) contains that licence.
Credit: the [EvalPlus project](https://github.com/evalplus/evalplus), which extends Google's MBPP benchmark.
These are evaluation references, not training rows. `spec_check.with_reference_plus` uses a corrected
solution only where it passes the original problem's tests.

SHA-256: `f2fd5d28f85e2911b185bbc720542efdd639bbdd6e43e226afed323fce32f020`.
