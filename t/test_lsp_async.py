"""Deterministic delayed workers test document/request identity without kernels."""
import copy
import hashlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import lsp


URI = "file:///project/probe.t"
SOURCE = "t 1 task probe(x: int) returns (r: int) ensures r == x { r := x; }"
CHANGED = SOURCE.replace("r := x;", "r := x + 1;")


class AsyncVerdictTests(unittest.TestCase):
    def setUp(self):
        self.server = lsp.Server(io.BytesIO(), io.BytesIO(), kernels=["dafny"])
        self.notifications = []
        self.server.notify = lambda method, params: self.notifications.append((method, copy.deepcopy(params)))
        self.jobs = []
        thread = patch("lsp.threading.Thread", side_effect=lambda *, target, daemon:
                       SimpleNamespace(start=lambda: self.jobs.append(target)))
        thread.start()
        self.addCleanup(thread.stop)
        self.calls = []

        def verify(task, kernels):
            self.calls.append(tuple(kernels))
            return {kernel: {"real": "verified", "twin": "refuted", "provisional": False}
                    for kernel in kernels}

        backend = patch("lsp.tlib.verify", side_effect=verify)
        backend.start()
        self.addCleanup(backend.stop)
        self.open()

    def open(self, text=SOURCE, version=1):
        self.server.handle_did_open({"params": {"textDocument":
                                    {"uri": URI, "text": text, "version": version}}})

    def change(self, text, version):
        self.server.handle_did_change({"params": {"textDocument": {"uri": URI, "version": version},
                                                  "contentChanges": [{"text": text}]}})

    def verdicts(self):
        return [params for method, params in self.notifications if method == "t/verdicts"]

    def request(self, kernels=None):
        params = {"uri": URI}
        if kernels is not None:
            params["kernels"] = kernels
        self.server.handle_verify({"id": 1, "params": params})

    def test_requested_kernels_are_captured_before_worker_runs(self):
        self.request(["lean"])
        self.jobs[0]()
        self.assertEqual(self.calls, [("lean",)])
        self.assertEqual(self.server.kernels, ["dafny"])

    def test_changed_document_drops_old_result(self):
        self.request()
        self.change(CHANGED, 2)
        self.jobs[0]()
        self.assertEqual(self.verdicts(), [])

    def test_edit_while_kernel_runs_drops_completed_result(self):
        self.request()

        def verify(task, kernels):
            self.change(CHANGED, 2)
            return {"dafny": {"real": "verified", "twin": "refuted", "provisional": False}}

        with patch("lsp.tlib.verify", side_effect=verify):
            self.jobs[0]()
        self.assertEqual(self.verdicts(), [])

    def test_edit_and_revert_does_not_revive_old_request(self):
        self.request()
        self.change(CHANGED, 2)
        self.change(SOURCE, 3)
        self.jobs[0]()
        self.assertEqual(self.verdicts(), [])

    def test_close_and_reopen_does_not_revive_old_request(self):
        self.request()
        self.server.dispatch({"method": "textDocument/didClose", "params": {"textDocument": {"uri": URI}}})
        self.open()
        self.jobs[0]()
        self.assertEqual(self.verdicts(), [])

    def test_latest_request_wins_when_workers_finish_out_of_order(self):
        self.request(["dafny"])
        self.request(["lean"])
        self.jobs[1]()
        self.jobs[0]()
        self.assertEqual(len(self.verdicts()), 1)
        self.assertEqual(list(self.verdicts()[0]["kernels"]), ["lean"])

    def test_current_result_carries_document_identity(self):
        self.request()
        self.jobs[0]()
        payload = self.verdicts()[0]
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["document_sha256"], hashlib.sha256(SOURCE.encode()).hexdigest())


if __name__ == "__main__":
    unittest.main()
