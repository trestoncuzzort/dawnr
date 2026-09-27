"""dawnr_retrieval: local search over the proved corpus, a person's knowledge folder and cached
fetched pages (DAWNR-RETRIEVAL.md, AMBITION.md's "to know things it was not trained on").

Standard library only unless the operator turns dense embeddings on (retrieval.dense): importing
this package, and running the BM25 path, never touches torch. `retrieval_tools` is what
dawnr_harness/runtime.py wires in under the `retrieval` configuration key.
"""
from .bm25 import BM25Index, tokenize                                            # noqa: F401
from .cache import append_fetched_page, load_fetched_cache                       # noqa: F401
from .harness_tool import retrieval_tools                                        # noqa: F401
from .index import KnowledgeIndex, build_index                                   # noqa: F401
from .sources import Passage, load_corpus, load_knowledge_folder                 # noqa: F401
