#!/usr/bin/env python3
"""Require real passing cases and no errors/failures in CPython's JUnit output."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def judge(path):
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    if not cases or any(case.find("failure") is not None or case.find("error") is not None for case in cases):
        raise ValueError("Python suite has missing cases, failures, or errors")
    passed = sum(case.find("skipped") is None for case in cases)
    if not passed:
        raise ValueError("an entirely skipped Python suite cannot satisfy the gate")
    for suite in root.iter("testsuite"):
        if int(suite.get("errors", "0")) or int(suite.get("failures", "0")):
            raise ValueError("Python suite summary reports an error or failure")
    return passed, len(cases) - passed


if __name__ == "__main__":
    passed, skipped = judge(Path(sys.argv[1]))
    with Path(sys.argv[2]).open("x", encoding="utf-8") as stream:
        stream.write(f":test-result: PASS\n:test-name: python-full-suite\n:passed-cases: {passed}\n:skipped-cases: {skipped}\n")
