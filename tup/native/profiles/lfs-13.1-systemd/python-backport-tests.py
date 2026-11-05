#!/usr/bin/env python3
"""Exercise the selected POP3 method and actual backported C function.

No network, package installation, or kernel changes. The C harness substitutes
the allocator/encoding/realpath boundary so a path longer than MAXPATHLEN can be
tested deterministically, including both error paths and allocation ownership.
The complete final Python suite remains an independent required gate.
https://github.com/python/cpython/tree/5e58eaad7c58df58dfa8ea549c87996e01dd1077
"""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import tempfile


def test_pop3(source):
    spec = importlib.util.spec_from_file_location("tup_selected_poplib", source / "Lib/poplib.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Socket:
        def __init__(self):
            self.sent = []

        def sendall(self, data):
            self.sent.append(data)

    client = module.POP3.__new__(module.POP3)
    client.encoding, client._debugging, client.sock = "utf-8", 0, Socket()
    for text in ("STAT", "USER ordinary-name", "PASS nonascii-\u00e9"):
        client._putcmd(text)
        assert client.sock.sent[-1] == text.encode("utf-8") + b"\r\n"
    for code in (*range(32), 127):
        before = list(client.sock.sent)
        try:
            client._putcmd("USER left" + chr(code) + "right")
        except ValueError:
            pass
        else:
            raise AssertionError(f"POP3 accepted forbidden control character {code}")
        assert client.sock.sent == before, "rejected command reached socket"


C_PREFIX = r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#undef assert
#define assert(condition) do { if (!(condition)) exit(97); } while (0)
#define MAXPATHLEN 256
static int mode, realpath_frees;
static void *realpath_allocation;
static char *_Py_EncodeLocaleRaw(const wchar_t *p, void *unused) {
    (void)p; (void)unused;
    return mode == 3 ? NULL : strdup("fixture");
}
static char *native_realpath(const char *p, char *buffer) {
    (void)p;
    /* The vulnerable implementation supplies a fixed stack buffer. */
    assert(buffer == NULL);
    if (mode == 1) { errno = ENOENT; return NULL; }
    char *result = malloc(8193);
    assert(result != NULL);
    memset(result, 'x', 8192); result[8192] = 0;
    realpath_allocation = result;
    return result;
}
static wchar_t *Py_DecodeLocale(const char *p, size_t *length) {
    if (mode == 2) return NULL;
    *length = strlen(p);
    wchar_t *result = malloc((*length + 1) * sizeof(wchar_t));
    assert(result != NULL);
    for (size_t i = 0; i <= *length; ++i) result[i] = (unsigned char)p[i];
    return result;
}
static void native_free(void *p) {
    if (p == realpath_allocation && p != NULL) {
        ++realpath_frees; realpath_allocation = NULL;
    }
    free(p);
}
#define realpath native_realpath
#define free native_free
#define PyMem_RawFree native_free
'''
C_SUFFIX = r'''
int main(void) {
    wchar_t result[9000];
    mode = 0;
    assert(_Py_wrealpath(L"fixture", result, 9000) == result);
    assert(wcslen(result) == 8192 && result[0] == L'x');
    assert(realpath_frees == 1 && realpath_allocation == NULL);
    errno = 0;
    assert(_Py_wrealpath(L"fixture", result, 12) == NULL && errno == EINVAL);
    assert(realpath_frees == 2 && realpath_allocation == NULL);
    mode = 1; errno = 0;
    assert(_Py_wrealpath(L"fixture", result, 9000) == NULL && errno == ENOENT);
    assert(realpath_frees == 2 && realpath_allocation == NULL);
    mode = 2; errno = 0;
    assert(_Py_wrealpath(L"fixture", result, 9000) == NULL && errno == EINVAL);
    assert(realpath_frees == 3 && realpath_allocation == NULL);
    mode = 3; errno = 0;
    assert(_Py_wrealpath(L"fixture", result, 9000) == NULL && errno == EINVAL);
    assert(realpath_frees == 3 && realpath_allocation == NULL);
    return 0;
}
'''


def test_wrealpath(source, compiler="gcc"):
    text = (source / "Python/fileutils.c").read_text(encoding="utf-8")
    start = text.index("wchar_t*\n_Py_wrealpath(")
    end = text.index("\n}\n#endif", start) + 2
    function = text[start:end]
    with tempfile.TemporaryDirectory(prefix="tup-python-regression-") as temporary:
        directory = Path(temporary)
        cfile, binary = directory / "regression.c", directory / "regression"
        cfile.write_text(C_PREFIX + function + C_SUFFIX, encoding="utf-8")
        subprocess.run([compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(cfile), "-o", str(binary)], check=True, timeout=60)
        subprocess.run([str(binary)], check=True, timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    test_pop3(args.source)
    test_wrealpath(args.source)
    # Written only after both executable regressions pass; retained by suite gate.
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(":test-result: PASS\n:test-name: pop3-all-control-characters\n")
        stream.write(":test-result: PASS\n:test-name: wrealpath-allocation-and-errors\n")


if __name__ == "__main__":
    main()
