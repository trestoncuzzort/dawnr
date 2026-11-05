#!/usr/bin/env python3
"""Bounded local tests for the selected built amalgamation, not upstream testfixture."""
from pathlib import Path
import re
import subprocess


def run(sql):
    return subprocess.run(["./sqlite3", "-batch", ":memory:"], input=".bail on\n" + sql + "\n",
                          text=True, capture_output=True, timeout=30)


def main():
    selftest = run("CREATE TABLE a(x PRIMARY KEY); INSERT INTO a VALUES(1),(2);\n.selftest --init")
    if selftest.returncode or not re.search(r"^0 errors out of [1-9][0-9]* tests$", selftest.stdout, re.M):
        raise ValueError("shipped SQLite .selftest did not pass")
    Path("native-sqlite-selftest.log").write_text(selftest.stdout + selftest.stderr, encoding="utf-8")
    checks = {
        "transaction-rollback": ("CREATE TABLE a(x); BEGIN; INSERT INTO a VALUES(9); ROLLBACK; SELECT count(*) FROM a;", "0"),
        "recursive-query": ("WITH RECURSIVE a(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM a WHERE x<1000) SELECT sum(x) FROM a;", "500500"),
        "json": ("SELECT json_extract('{\"x\":[1,2,3]}', '$.x[1]');", "2"),
        "fts4": ("CREATE VIRTUAL TABLE f USING fts4(body); INSERT INTO f VALUES('native regression'); SELECT count(*) FROM f WHERE f MATCH 'native';", "1"),
        "fts5": ("CREATE VIRTUAL TABLE f USING fts5(body); INSERT INTO f VALUES('native regression'); SELECT count(*) FROM f WHERE f MATCH 'regression';", "1"),
        "integrity": ("CREATE TABLE a(x PRIMARY KEY); INSERT INTO a VALUES(1),(2); PRAGMA integrity_check;", "ok"),
    }
    passed = ["shipped-shell-selftest"]
    for name, (sql, expected) in checks.items():
        result = run(sql)
        if result.returncode or result.stdout.strip() != expected:
            raise ValueError(f"SQLite {name} failed: {result.stdout} {result.stderr}")
        passed.append(name)
    for name, sql, diagnostic in (
        ("unique-enforcement", "CREATE TABLE a(x UNIQUE); INSERT INTO a VALUES(1),(1);", "UNIQUE constraint failed"),
        ("foreign-key-enforcement", "PRAGMA foreign_keys=ON; CREATE TABLE p(x PRIMARY KEY); CREATE TABLE c(x REFERENCES p); INSERT INTO c VALUES(1);", "FOREIGN KEY constraint failed"),
    ):
        result = run(sql)
        if result.returncode == 0 or diagnostic not in result.stderr:
            raise ValueError(f"SQLite {name} failed to reject the invalid write")
        passed.append(name)
    with Path("native-sqlite.trs").open("x", encoding="utf-8") as stream:
        for name in passed:
            stream.write(f":test-result: PASS\n:test-name: {name}\n")


if __name__ == "__main__":
    main()
