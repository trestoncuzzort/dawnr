#!/usr/bin/env python3
"""Adapt only the shifted test context in the LFS OpenSSL patch for Python 3.14.10.

The source lock authenticates the original patch. This digest constrains the
reviewed transformation; it is not a substitute for source authentication.
Python 3.14.10 extends test_msg_callback before test_msg_callback_tls12. Keep
those security tests and insert the upstream exception test after them.
"""
import hashlib
from pathlib import Path
import sys


PIN = "707a0c457192ac2f3b5b8a51481bc5ebd12db22d57c1dbe0256138ee6e070792"
OLD = b'''@@ -5171,6 +5171,20 @@ def msg_cb(conn, direction, version, content_type, msg_type, data):
         with self.assertRaises(TypeError):
             client_context._msg_callback = object()
'''
NEW = b'''@@ -5580,6 +5580,20 @@ def test_msg_callback(self):
         # a failed deletion does not change the value
         self.assertIs(client_context._msg_callback, msg_cb)
'''


def adapt(data):
    if hashlib.sha256(data).hexdigest() != PIN or data.count(OLD) != 1:
        raise ValueError("unreviewed Python OpenSSL patch bytes")
    return data.replace(OLD, NEW, 1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("expected original patch and new adapted output")
    source, output = map(Path, sys.argv[1:])
    if source.is_symlink() or output.exists() or output.is_symlink():
        raise SystemExit("refusing redirected input or existing output")
    with output.open("xb") as stream:
        stream.write(adapt(source.read_bytes()))
