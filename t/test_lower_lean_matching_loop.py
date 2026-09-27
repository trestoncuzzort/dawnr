#!/usr/bin/env python3
"""test_lower_lean_matching_loop.py: pins the 2026-09-26 lean fixes for the
six-of-seven corpus (lean was the one missing kernel on 35 documents).

Each fix has a SOURCE-SHAPE test (no lean binary needed) and a SEEDED-FAULT
kernel test: the real program of that shape reads VERIFIED and a wrong
program of the same shape -- the harness's own measured twin, a mutation
with a concrete input that separates it from the real -- still reads
REFUTED, never VERIFIED and never TIMEOUT. The kernel tests are skipped by
name, never silently passed, when no lean binary is on PATH.

The fixtures are six-of-seven documents from the 2026-09-26 corpus, lifted
by t/lift_vericoding.py and friends; embedded so the test does not depend
on the gitignored t/out tree.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness  # noqa: E402
import lower_lean  # noqa: E402

FIXTURES = json.loads(r'''{"getEven":{"body":[{"assign":["s_out",{"var":"s"}]},{"var":{"init":{"int":0},"name":"i_v","type":"int"}},{"while":{"body":[{"if":{"cond":{"args":[{"args":[{"args":[{"var":"s_out"},{"var":"i_v"}],"op":"at"},{"int":2}],"op":"mod"},{"int":1}],"op":"=="},"else":[],"then":[{"assign":["s_out",{"args":[{"var":"s_out"},{"var":"i_v"},{"args":[{"args":[{"var":"s_out"},{"var":"i_v"}],"op":"at"},{"int":1}],"op":"+"}],"op":"update"}]}]}},{"assign":["i_v",{"args":[{"var":"i_v"},{"int":1}],"op":"+"}]}],"cond":{"args":[{"var":"i_v"},{"args":[{"var":"s_out"}],"op":"len"}],"op":"<"},"decreases":{"args":[{"args":[{"var":"s_out"}],"op":"len"},{"var":"i_v"}],"op":"-"},"invariants":[{"args":[{"args":[{"var":"s_out"}],"op":"len"},{"args":[{"var":"s"}],"op":"len"}],"op":"=="},{"args":[{"args":[{"int":0},{"var":"i_v"}],"op":"<="},{"args":[{"var":"i_v"},{"args":[{"var":"s_out"}],"op":"len"}],"op":"<="}],"op":"and"},{"forall":{"body":{"ite":{"cond":{"args":[{"args":[{"args":[{"var":"s"},{"var":"j"}],"op":"at"},{"int":2}],"op":"mod"},{"int":1}],"op":"=="},"else":{"args":[{"args":[{"var":"s_out"},{"var":"j"}],"op":"at"},{"args":[{"var":"s"},{"var":"j"}],"op":"at"}],"op":"=="},"then":{"args":[{"args":[{"var":"s_out"},{"var":"j"}],"op":"at"},{"args":[{"args":[{"var":"s"},{"var":"j"}],"op":"at"},{"int":1}],"op":"+"}],"op":"=="}}},"hi":{"var":"i_v"},"lo":{"int":0},"var":"j"}},{"forall":{"body":{"args":[{"args":[{"var":"s_out"},{"var":"j_v"}],"op":"at"},{"args":[{"var":"s"},{"var":"j_v"}],"op":"at"}],"op":"=="},"hi":{"args":[{"var":"s_out"}],"op":"len"},"lo":{"var":"i_v"},"var":"j_v"}}]}}],"ensures":[{"args":[{"args":[{"var":"s_out"}],"op":"len"},{"args":[{"var":"s"}],"op":"len"}],"op":"=="},{"forall":{"body":{"ite":{"cond":{"args":[{"args":[{"args":[{"var":"s"},{"var":"i"}],"op":"at"},{"int":2}],"op":"mod"},{"int":1}],"op":"=="},"else":{"args":[{"args":[{"var":"s_out"},{"var":"i"}],"op":"at"},{"args":[{"var":"s"},{"var":"i"}],"op":"at"}],"op":"=="},"then":{"args":[{"args":[{"var":"s_out"},{"var":"i"}],"op":"at"},{"args":[{"args":[{"var":"s"},{"var":"i"}],"op":"at"},{"int":1}],"op":"+"}],"op":"=="}}},"hi":{"args":[{"var":"s_out"}],"op":"len"},"lo":{"int":0},"var":"i"}}],"name":"vericoding_dd0586__getEven","params":[{"name":"s","type":"seq"}],"requires":[{"forall":{"body":{"args":[{"args":[{"var":"s"},{"var":"k"}],"op":"at"},{"int":0}],"op":">="},"hi":{"args":[{"var":"s"}],"op":"len"},"lo":{"int":0},"var":"k"}}],"returns":[{"name":"s_out","type":"seq"}],"t":1},"find":{"body":[{"assign":["index",{"int":0}]},{"while":{"body":[{"assign":["index",{"args":[{"var":"index"},{"int":1}],"op":"+"}]}],"cond":{"args":[{"args":[{"var":"index"},{"args":[{"var":"a"}],"op":"len"}],"op":"<"},{"args":[{"args":[{"var":"a"},{"var":"index"}],"op":"at"},{"var":"key"}],"op":"!="}],"op":"and"},"decreases":{"args":[{"args":[{"var":"a"}],"op":"len"},{"var":"index"}],"op":"-"},"invariants":[{"args":[{"args":[{"int":0},{"var":"index"}],"op":"<="},{"args":[{"var":"index"},{"args":[{"var":"a"}],"op":"len"}],"op":"<="}],"op":"and"},{"forall":{"body":{"args":[{"args":[{"var":"a"},{"var":"x"}],"op":"at"},{"var":"key"}],"op":"!="},"hi":{"var":"index"},"lo":{"int":0},"var":"x"}}]}}],"ensures":[{"args":[{"int":0},{"var":"index"}],"op":"<="},{"args":[{"var":"index"},{"args":[{"var":"a"}],"op":"len"}],"op":"<="},{"args":[{"args":[{"var":"index"},{"args":[{"var":"a"}],"op":"len"}],"op":"<"},{"args":[{"args":[{"var":"a"},{"var":"index"}],"op":"at"},{"var":"key"}],"op":"=="}],"op":"implies"}],"name":"mfes_2021_tmp_tmpuljn8zd9_fcul_exercises_10_find__find","params":[{"name":"a","type":"seq"},{"name":"key","type":"int"}],"requires":[{"args":[{"args":[{"var":"a"}],"op":"len"},{"int":0}],"op":">"}],"returns":[{"name":"index","type":"int"}],"t":1},"solution":{"body":[{"var":{"init":{"int":0},"name":"sum","type":"int"}},{"var":{"init":{"int":0},"name":"i_v2","type":"int"}},{"while":{"body":[{"assign":["sum",{"args":[{"var":"sum"},{"args":[{"var":"nums"},{"var":"i_v2"}],"op":"at"}],"op":"+"}]},{"assign":["i_v2",{"args":[{"var":"i_v2"},{"int":1}],"op":"+"}]}],"cond":{"args":[{"var":"i_v2"},{"args":[{"var":"nums"}],"op":"len"}],"op":"<"},"decreases":{"args":[{"args":[{"var":"nums"}],"op":"len"},{"var":"i_v2"}],"op":"-"},"invariants":[{"args":[{"args":[{"int":0},{"var":"i_v2"}],"op":"<="},{"args":[{"var":"i_v2"},{"args":[{"var":"nums"}],"op":"len"}],"op":"<="}],"op":"and"},{"args":[{"var":"sum"},{"args":[{"call":{"args":[{"var":"nums"},{"int":0}],"fun":"sumArray"}},{"call":{"args":[{"var":"nums"},{"var":"i_v2"}],"fun":"sumArray"}}],"op":"-"}],"op":"=="},{"args":[{"var":"sum"},{"int":0}],"op":">="}]}},{"assign":["result",{"var":"sum"}]}],"ensures":[{"args":[{"var":"result"},{"int":0}],"op":">="}],"name":"vericoding_dv0073__solution","params":[{"name":"nums","type":"seq"}],"requires":[{"args":[{"int":1},{"args":[{"var":"nums"}],"op":"len"}],"op":"<="},{"args":[{"args":[{"var":"nums"}],"op":"len"},{"int":100}],"op":"<="},{"forall":{"body":{"args":[{"args":[{"args":[{"var":"nums"},{"var":"i_v"}],"op":"at"},{"int":1}],"op":">="},{"args":[{"args":[{"var":"nums"},{"var":"i_v"}],"op":"at"},{"int":100}],"op":"<="}],"op":"and"},"hi":{"args":[{"var":"nums"}],"op":"len"},"lo":{"int":0},"var":"i_v"}}],"returns":[{"name":"result","type":"int"}],"spec_funs":[{"body":{"ite":{"cond":{"args":[{"args":[{"int":0},{"var":"i"}],"op":"<="},{"args":[{"var":"i"},{"args":[{"var":"nums_v"}],"op":"len"}],"op":"<="}],"op":"and"},"else":{"int":0},"then":{"ite":{"cond":{"args":[{"var":"i"},{"args":[{"var":"nums_v"}],"op":"len"}],"op":"=="},"else":{"args":[{"args":[{"var":"nums_v"},{"var":"i"}],"op":"at"},{"call":{"args":[{"var":"nums_v"},{"args":[{"var":"i"},{"int":1}],"op":"+"}],"fun":"sumArray"}}],"op":"+"},"then":{"int":0}}}}},"decreases":{"args":[{"args":[{"var":"nums_v"}],"op":"len"},{"var":"i"}],"op":"-"},"name":"sumArray","params":[{"name":"nums_v","type":"seq"},{"name":"i","type":"int"}],"result":"int"}],"t":1},"implies":{"body":[{"var":{"init":{"args":[{"args":[{"int":6},{"var":"a"}],"op":"-"},{"var":"b"}],"op":"-"},"name":"res","type":"int"}},{"if":{"cond":{"args":[{"var":"a"},{"int":1}],"op":"=="},"else":[{"if":{"cond":{"args":[{"var":"a"},{"int":2}],"op":"=="},"else":[{"if":{"cond":{"args":[{"var":"b"},{"int":1}],"op":"=="},"else":[{"if":{"cond":{"args":[{"var":"b"},{"int":2}],"op":"=="},"else":[],"then":[]}}],"then":[]}}],"then":[{"if":{"cond":{"args":[{"var":"b"},{"int":1}],"op":"=="},"else":[{"if":{"cond":{"args":[{"var":"b"},{"int":3}],"op":"=="},"else":[],"then":[]}}],"then":[]}}]}}],"then":[{"if":{"cond":{"args":[{"var":"b"},{"int":2}],"op":"=="},"else":[{"if":{"cond":{"args":[{"var":"b"},{"int":3}],"op":"=="},"else":[],"then":[]}}],"then":[]}}]}},{"assign":["result",{"var":"res"}]}],"ensures":[{"call":{"args":[{"var":"a"},{"var":"b"},{"var":"result"}],"fun":"is_valid_result"}},{"args":[{"var":"result"},{"call":{"args":[{"var":"a"},{"var":"b"}],"fun":"late_brother"}}],"op":"=="}],"name":"vericoding_va0399__solve","params":[{"name":"a","type":"int"},{"name":"b","type":"int"}],"requires":[{"call":{"args":[{"var":"a"},{"var":"b"}],"fun":"valid_brother_numbers"}}],"returns":[{"name":"result","type":"int"}],"spec_funs":[{"body":{"args":[{"args":[{"args":[{"int":1},{"var":"a_v"}],"op":"<="},{"args":[{"var":"a_v"},{"int":3}],"op":"<="}],"op":"and"},{"args":[{"args":[{"int":1},{"var":"b_v"}],"op":"<="},{"args":[{"var":"b_v"},{"int":3}],"op":"<="}],"op":"and"},{"args":[{"var":"a_v"},{"var":"b_v"}],"op":"!="}],"op":"and"},"decreases":{"int":0},"name":"valid_brother_numbers","params":[{"name":"a_v","type":"int"},{"name":"b_v","type":"int"}],"result":"bool"},{"body":{"args":[{"args":[{"int":6},{"var":"a_v2"}],"op":"-"},{"var":"b_v2"}],"op":"-"},"decreases":{"int":0},"name":"late_brother","params":[{"name":"a_v2","type":"int"},{"name":"b_v2","type":"int"}],"result":"int"},{"body":{"args":[{"call":{"args":[{"var":"a_v3"},{"var":"b_v3"}],"fun":"valid_brother_numbers"}},{"args":[{"args":[{"args":[{"int":1},{"var":"result_v"}],"op":"<="},{"args":[{"var":"result_v"},{"int":3}],"op":"<="}],"op":"and"},{"args":[{"var":"result_v"},{"var":"a_v3"}],"op":"!="},{"args":[{"var":"result_v"},{"var":"b_v3"}],"op":"!="}],"op":"and"}],"op":"implies"},"decreases":{"int":0},"name":"is_valid_result","params":[{"name":"a_v3","type":"int"},{"name":"b_v3","type":"int"},{"name":"result_v","type":"int"}],"result":"bool"}],"t":1},"branch_div":{"body":[{"var":{"init":{"args":[{"var":"n"},{"int":1}],"op":"-"},"name":"req","type":"int"}},{"if":{"cond":{"args":[{"var":"req"},{"var":"v"}],"op":"<="},"else":[{"var":{"init":{"args":[{"var":"req"},{"var":"v"}],"op":"-"},"name":"remaining","type":"int"}},{"assign":["result",{"args":[{"var":"v"},{"args":[{"args":[{"var":"remaining"},{"args":[{"var":"remaining"},{"int":3}],"op":"+"}],"op":"*"},{"int":2}],"op":"div"}],"op":"+"}]}],"then":[{"assign":["result",{"var":"req"}]}]}}],"ensures":[{"args":[{"var":"result"},{"call":{"args":[{"var":"n"},{"var":"v"}],"fun":"minCost"}}],"op":"=="}],"name":"vericoding_da0203__solve","params":[{"name":"n","type":"int"},{"name":"v","type":"int"}],"requires":[{"call":{"args":[{"var":"n"},{"var":"v"}],"fun":"validInput"}}],"returns":[{"name":"result","type":"int"}],"spec_funs":[{"body":{"args":[{"args":[{"args":[{"int":2},{"var":"n_v"}],"op":"<="},{"args":[{"var":"n_v"},{"int":100}],"op":"<="}],"op":"and"},{"args":[{"args":[{"int":1},{"var":"v_v"}],"op":"<="},{"args":[{"var":"v_v"},{"int":100}],"op":"<="}],"op":"and"}],"op":"and"},"decreases":{"int":0},"name":"validInput","params":[{"name":"n_v","type":"int"},{"name":"v_v","type":"int"}],"result":"bool"},{"body":{"ite":{"cond":{"call":{"args":[{"var":"n_v2"},{"var":"v_v2"}],"fun":"validInput"}},"else":{"int":0},"then":{"ite":{"cond":{"args":[{"args":[{"var":"n_v2"},{"int":1}],"op":"-"},{"var":"v_v2"}],"op":"<="},"else":{"args":[{"var":"v_v2"},{"args":[{"args":[{"args":[{"args":[{"var":"n_v2"},{"int":1}],"op":"-"},{"var":"v_v2"}],"op":"-"},{"args":[{"args":[{"args":[{"var":"n_v2"},{"int":1}],"op":"-"},{"var":"v_v2"}],"op":"-"},{"int":3}],"op":"+"}],"op":"*"},{"int":2}],"op":"div"}],"op":"+"},"then":{"args":[{"var":"n_v2"},{"int":1}],"op":"-"}}}}},"decreases":{"int":0},"name":"minCost","params":[{"name":"n_v2","type":"int"},{"name":"v_v2","type":"int"}],"result":"int"}],"t":1},"helper_sfun":{"body":[{"var":{"init":{"int":0},"name":"i","type":"int"}},{"var":{"init":{"int":0},"name":"consecutiveX_v","type":"int"}},{"assign":["result",{"int":0}]},{"while":{"body":[{"var":{"init":{"var":"result"},"name":"oldResult","type":"int"}},{"var":{"init":{"var":"consecutiveX_v"},"name":"oldConsecutiveX","type":"int"}},{"if":{"cond":{"args":[{"args":[{"var":"s"},{"var":"i"}],"op":"at"},{"int":120}],"op":"=="},"else":[{"assign":["consecutiveX_v",{"int":0}]}],"then":[{"assign":["consecutiveX_v",{"args":[{"var":"consecutiveX_v"},{"int":1}],"op":"+"}]},{"if":{"cond":{"args":[{"var":"consecutiveX_v"},{"int":2}],"op":">"},"else":[],"then":[{"assign":["result",{"args":[{"var":"result"},{"int":1}],"op":"+"}]}]}}]}},{"assign":["i",{"args":[{"var":"i"},{"int":1}],"op":"+"}]}],"cond":{"args":[{"var":"i"},{"args":[{"var":"s"}],"op":"len"}],"op":"<"},"decreases":{"args":[{"args":[{"var":"s"}],"op":"len"},{"var":"i"}],"op":"-"},"invariants":[{"args":[{"args":[{"int":0},{"var":"i"}],"op":"<="},{"args":[{"var":"i"},{"args":[{"var":"s"}],"op":"len"}],"op":"<="}],"op":"and"},{"args":[{"var":"consecutiveX_v"},{"int":0}],"op":">="},{"args":[{"var":"result"},{"int":0}],"op":">="},{"args":[{"args":[{"var":"result"},{"call":{"args":[{"var":"s"},{"var":"i"},{"var":"consecutiveX_v"}],"fun":"countExcessivePositionsHelper"}}],"op":"+"},{"call":{"args":[{"var":"s"}],"fun":"countExcessivePositions"}}],"op":"=="},{"args":[{"var":"result"},{"var":"i"}],"op":"<="}]}}],"ensures":[{"args":[{"var":"result"},{"int":0}],"op":">="},{"args":[{"var":"result"},{"args":[{"var":"s"}],"op":"len"}],"op":"<="},{"args":[{"var":"result"},{"call":{"args":[{"var":"s"}],"fun":"countExcessivePositions"}}],"op":"=="}],"name":"vericoding_da0508__solve","params":[{"name":"s","type":"seq"}],"requires":[{"forall":{"body":{"args":[{"args":[{"args":[{"var":"s"},{"var":"k"}],"op":"at"},{"int":0}],"op":">="},{"args":[{"args":[{"var":"s"},{"var":"k"}],"op":"at"},{"int":1114111}],"op":"<="}],"op":"and"},"hi":{"args":[{"var":"s"}],"op":"len"},"lo":{"int":0},"var":"k"}},{"call":{"args":[{"var":"s"}],"fun":"validInput"}}],"returns":[{"name":"result","type":"int"}],"spec_funs":[{"body":{"ite":{"cond":{"args":[{"args":[{"args":[{"int":0},{"var":"pos"}],"op":"<="},{"args":[{"var":"pos"},{"args":[{"var":"s_v"}],"op":"len"}],"op":"<="}],"op":"and"},{"args":[{"var":"consecutiveX"},{"int":0}],"op":">="}],"op":"and"},"else":{"int":0},"then":{"ite":{"cond":{"args":[{"var":"pos"},{"args":[{"var":"s_v"}],"op":"len"}],"op":">="},"else":{"args":[{"ite":{"cond":{"args":[{"ite":{"cond":{"args":[{"args":[{"var":"s_v"},{"var":"pos"}],"op":"at"},{"int":120}],"op":"=="},"else":{"int":0},"then":{"args":[{"var":"consecutiveX"},{"int":1}],"op":"+"}}},{"int":2}],"op":">"},"else":{"int":0},"then":{"int":1}}},{"call":{"args":[{"var":"s_v"},{"args":[{"var":"pos"},{"int":1}],"op":"+"},{"ite":{"cond":{"args":[{"args":[{"var":"s_v"},{"var":"pos"}],"op":"at"},{"int":120}],"op":"=="},"else":{"int":0},"then":{"args":[{"var":"consecutiveX"},{"int":1}],"op":"+"}}}],"fun":"countExcessivePositionsHelper"}}],"op":"+"},"then":{"int":0}}}}},"decreases":{"args":[{"args":[{"var":"s_v"}],"op":"len"},{"var":"pos"}],"op":"-"},"name":"countExcessivePositionsHelper","params":[{"name":"s_v","type":"seq"},{"name":"pos","type":"int"},{"name":"consecutiveX","type":"int"}],"result":"int"},{"body":{"call":{"args":[{"var":"s_v2"},{"int":0},{"int":0}],"fun":"countExcessivePositionsHelper"}},"decreases":{"int":0},"name":"countExcessivePositions","params":[{"name":"s_v2","type":"seq"}],"result":"int"},{"body":{"args":[{"args":[{"var":"s_v3"}],"op":"len"},{"int":3}],"op":">="},"decreases":{"int":0},"name":"validInput","params":[{"name":"s_v3","type":"seq"}],"result":"bool"}],"t":1},"cumSum":{"body":[{"assign":["result",{"args":[{"args":[{"var":"a"}],"op":"len"},{"int":0}],"op":"fill"}]},{"assign":["result",{"args":[{"var":"result"},{"int":0},{"args":[{"var":"a"},{"int":0}],"op":"at"}],"op":"update"}]},{"var":{"init":{"int":1},"name":"i_v","type":"int"}},{"while":{"body":[{"assign":["result",{"args":[{"var":"result"},{"var":"i_v"},{"args":[{"args":[{"var":"result"},{"args":[{"var":"i_v"},{"int":1}],"op":"-"}],"op":"at"},{"args":[{"var":"a"},{"var":"i_v"}],"op":"at"}],"op":"+"}],"op":"update"}]},{"assign":["i_v",{"args":[{"var":"i_v"},{"int":1}],"op":"+"}]}],"cond":{"args":[{"var":"i_v"},{"args":[{"var":"a"}],"op":"len"}],"op":"<"},"decreases":{"args":[{"args":[{"var":"a"}],"op":"len"},{"var":"i_v"}],"op":"-"},"invariants":[{"args":[{"args":[{"var":"result"}],"op":"len"},{"args":[{"var":"a"}],"op":"len"}],"op":"=="},{"args":[{"args":[{"int":1},{"var":"i_v"}],"op":"<="},{"args":[{"var":"i_v"},{"args":[{"var":"a"}],"op":"len"}],"op":"<="}],"op":"and"},{"args":[{"args":[{"var":"result"},{"int":0}],"op":"at"},{"args":[{"var":"a"},{"int":0}],"op":"at"}],"op":"=="},{"forall":{"body":{"args":[{"args":[{"var":"result"},{"var":"j"}],"op":"at"},{"args":[{"args":[{"var":"result"},{"args":[{"var":"j"},{"int":1}],"op":"-"}],"op":"at"},{"args":[{"var":"a"},{"var":"j"}],"op":"at"}],"op":"+"}],"op":"=="},"hi":{"var":"i_v"},"lo":{"int":1},"var":"j"}}]}}],"ensures":[{"args":[{"args":[{"var":"result"}],"op":"len"},{"args":[{"var":"a"}],"op":"len"}],"op":"=="},{"args":[{"args":[{"var":"result"}],"op":"len"},{"args":[{"var":"a"}],"op":"len"}],"op":"=="},{"args":[{"args":[{"var":"result"},{"int":0}],"op":"at"},{"args":[{"var":"a"},{"int":0}],"op":"at"}],"op":"=="},{"forall":{"body":{"args":[{"args":[{"var":"result"},{"var":"i"}],"op":"at"},{"args":[{"args":[{"var":"result"},{"args":[{"var":"i"},{"int":1}],"op":"-"}],"op":"at"},{"args":[{"var":"a"},{"var":"i"}],"op":"at"}],"op":"+"}],"op":"=="},"hi":{"args":[{"var":"a"}],"op":"len"},"lo":{"int":1},"var":"i"}}],"name":"vericoding_ds0016__cumSum","params":[{"name":"a","type":"seq"}],"requires":[{"args":[{"args":[{"var":"a"}],"op":"len"},{"int":0}],"op":">"}],"returns":[{"name":"result","type":"seq"}],"t":1},"reverse_append":{"body":[{"assign":["rev",{"args":[],"op":"seq"}]},{"var":{"init":{"int":0},"name":"i","type":"int"}},{"while":{"body":[{"assign":["rev",{"args":[{"var":"rev"},{"args":[{"args":[{"var":"s"},{"args":[{"args":[{"args":[{"var":"s"}],"op":"len"},{"var":"i"}],"op":"-"},{"int":1}],"op":"-"}],"op":"at"}],"op":"seq"}],"op":"+"}]},{"assign":["i",{"args":[{"var":"i"},{"int":1}],"op":"+"}]}],"cond":{"args":[{"var":"i"},{"args":[{"var":"s"}],"op":"len"}],"op":"<"},"decreases":{"args":[{"args":[{"var":"s"}],"op":"len"},{"var":"i"}],"op":"-"},"invariants":[{"args":[{"args":[{"var":"i"},{"int":0}],"op":">="},{"args":[{"var":"i"},{"args":[{"var":"s"}],"op":"len"}],"op":"<="}],"op":"and"},{"args":[{"args":[{"var":"rev"}],"op":"len"},{"var":"i"}],"op":"=="},{"forall":{"body":{"args":[{"args":[{"var":"rev"},{"var":"k_v"}],"op":"at"},{"args":[{"var":"s"},{"args":[{"args":[{"args":[{"var":"s"}],"op":"len"},{"int":1}],"op":"-"},{"var":"k_v"}],"op":"-"}],"op":"at"}],"op":"=="},"hi":{"var":"i"},"lo":{"int":0},"var":"k_v"}}]}}],"ensures":[{"args":[{"args":[{"var":"rev"}],"op":"len"},{"args":[{"var":"s"}],"op":"len"}],"op":"=="},{"forall":{"body":{"args":[{"args":[{"var":"rev"},{"var":"k"}],"op":"at"},{"args":[{"var":"s"},{"args":[{"args":[{"args":[{"var":"s"}],"op":"len"},{"int":1}],"op":"-"},{"var":"k"}],"op":"-"}],"op":"at"}],"op":"=="},"hi":{"args":[{"var":"s"}],"op":"len"},"lo":{"int":0},"var":"k"}}],"name":"humaneval_dafny_088_sort_array__reverse","params":[{"name":"s","type":"seq"}],"requires":[],"returns":[{"name":"rev","type":"seq"}],"t":1},"no_quant_loop":{"body":[{"var":{"init":{"var":"m"},"name":"m1","type":"int"}},{"var":{"init":{"var":"n"},"name":"n1","type":"int"}},{"while":{"body":[{"if":{"cond":{"args":[{"var":"m1"},{"var":"n1"}],"op":">"},"else":[{"assign":["n1",{"args":[{"var":"n1"},{"var":"m1"}],"op":"-"}]}],"then":[{"assign":["m1",{"args":[{"var":"m1"},{"var":"n1"}],"op":"-"}]}]}}],"cond":{"args":[{"var":"m1"},{"var":"n1"}],"op":"!="},"decreases":{"args":[{"var":"m1"},{"var":"n1"}],"op":"+"},"invariants":[{"args":[{"args":[{"int":0},{"var":"m1"}],"op":"<"},{"args":[{"var":"m1"},{"var":"m"}],"op":"<="}],"op":"and"},{"args":[{"args":[{"int":0},{"var":"n1"}],"op":"<"},{"args":[{"var":"n1"},{"var":"n"}],"op":"<="}],"op":"and"},{"args":[{"call":{"args":[{"var":"m"},{"var":"n"}],"fun":"gcd"}},{"call":{"args":[{"var":"m1"},{"var":"n1"}],"fun":"gcd"}}],"op":"=="},{"args":[{"var":"m1"},{"int":0}],"op":">="},{"args":[{"var":"n1"},{"int":0}],"op":">="}]}},{"assign":["res",{"var":"n1"}]}],"ensures":[{"args":[{"var":"res"},{"int":0}],"op":">="},{"args":[{"var":"res"},{"call":{"args":[{"var":"m"},{"var":"n"}],"fun":"gcd"}}],"op":"=="}],"name":"dafny_tmp_tmpmvs2dmry_examples2__gcdCalc","params":[{"name":"m","type":"int"},{"name":"n","type":"int"}],"requires":[{"args":[{"var":"m"},{"int":0}],"op":">="},{"args":[{"var":"n"},{"int":0}],"op":">="},{"args":[{"var":"m"},{"int":0}],"op":">"},{"args":[{"var":"n"},{"int":0}],"op":">"}],"returns":[{"name":"res","type":"int"}],"spec_funs":[{"body":{"ite":{"cond":{"args":[{"args":[{"var":"m_v"},{"int":0}],"op":">="},{"args":[{"var":"n_v"},{"int":0}],"op":">="},{"args":[{"args":[{"var":"m_v"},{"int":0}],"op":">"},{"args":[{"var":"n_v"},{"int":0}],"op":">"}],"op":"and"}],"op":"and"},"else":{"int":0},"then":{"ite":{"cond":{"args":[{"var":"m_v"},{"var":"n_v"}],"op":"=="},"else":{"ite":{"cond":{"args":[{"var":"m_v"},{"var":"n_v"}],"op":">"},"else":{"call":{"args":[{"var":"m_v"},{"args":[{"var":"n_v"},{"var":"m_v"}],"op":"-"}],"fun":"gcd"}},"then":{"call":{"args":[{"args":[{"var":"m_v"},{"var":"n_v"}],"op":"-"},{"var":"n_v"}],"fun":"gcd"}}}},"then":{"var":"n_v"}}}}},"decreases":{"args":[{"var":"m_v"},{"var":"n_v"}],"op":"+"},"name":"gcd","params":[{"name":"m_v","type":"int"},{"name":"n_v","type":"int"}],"result":"int"}],"t":1}}''')


def _lean():
    try:
        from verifiers import lean as lean_backend
    except Exception as e:                              # noqa: BLE001
        return None, f"verifiers.lean import failed: {e}"
    if not getattr(lean_backend, "LEAN", None):
        return None, "no lean binary on PATH"
    return lean_backend, ""


def _verify(backend, name: str, src: str):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / f"{name}.lean"
        p.write_text(src, encoding="utf-8")
        return backend.verify(p)


class SourceShapeTest(unittest.TestCase):
    """No lean binary needed."""

    def test_ground_instantiation_script_on_quantified_invariants(self):
        # getEven: a range requires and a `% 2` invariant, the matching
        # loop's own shape: the script instantiates and CLEARS them
        task = FIXTURES["getEven"]
        src = lower_lean.lower(task, task["body"])
        spec = src.split("_t_loop_spec", 1)[1].split("theorem ", 1)[0]
        self.assertIn("(try clear hpre)", spec)
        self.assertIn("(try clear hinv3)", spec)
        self.assertIn("grind (instances := 100)", spec)
        for banned in ("sorry", "admit", "axiom ", "set_option"):
            self.assertNotIn(banned, src)

    def test_no_script_without_a_quantified_hypothesis(self):
        # gcdCalc's loop has no quantified requires or invariant
        task = FIXTURES["no_quant_loop"]
        src = lower_lean.lower(task, task["body"])
        self.assertNotIn("(try intro _x1)", src)

    def test_guard_undefined_twin_gets_a_certificate(self):
        # MFES find's compare-flip twin reads a[len(a)] in the GUARD
        task = FIXTURES["find"]
        twin, op, w = harness.twin_for(task)
        self.assertEqual(w.get("_kind"), "undefined")
        src = lower_lean.lower(task, twin, w)
        self.assertIn("t_refutation_certificate", src)

    def test_unassigned_return_does_not_block_the_loop_replay(self):
        task = FIXTURES["solution"]
        twin, op, w = harness.twin_for(task)
        src = lower_lean.lower(task, twin, w)
        self.assertIn("t_refutation_certificate", src)

    def test_implies_in_computational_position_lowers(self):
        task = FIXTURES["implies"]
        src = lower_lean.lower(task, task["body"])
        self.assertIn("decide", src)

    def test_branch_local_div_does_not_crash(self):
        task = FIXTURES["branch_div"]
        lower_lean.lower(task, task["body"])

    def test_spec_fun_wf_cites_only_declared_spec_funs(self):
        task = FIXTURES["helper_sfun"]
        src = lower_lean.lower(task, task["body"])
        first = task["spec_funs"][0]["name"] + "_s_wf"
        block = src.split(f"theorem {first}", 1)[1].split("\ndef ", 1)[0]
        for later in task["spec_funs"][1:]:
            self.assertNotIn(later["name"] + "_s", block)


class SeededFaultKernelTest(unittest.TestCase):
    """real VERIFIED, the measured twin REFUTED (not TIMEOUT)."""

    @classmethod
    def setUpClass(cls):
        cls.backend, cls.why = _lean()

    def _pair(self, key: str):
        if self.backend is None:
            self.skipTest(self.why)
        from verifiers import Outcome
        task = FIXTURES[key]
        r = _verify(self.backend, key, lower_lean.lower(task, task["body"]))
        self.assertEqual(r.outcome, Outcome.VERIFIED, f"{key} real: {r.error}")
        twin, op, w = harness.twin_for(task)
        self.assertIsNotNone(twin, f"{key}: no twin")
        t = _verify(self.backend, key + "_twin", lower_lean.lower(task, twin, w))
        self.assertEqual(t.outcome, Outcome.REFUTED,
                         f"{key} twin ({op}): {t.outcome} {t.error}")

    def test_getEven_matching_loop(self):
        self._pair("getEven")

    def test_find_guard_undefined(self):
        self._pair("find")

    def test_solution_unassigned_return(self):
        self._pair("solution")

    def test_implies(self):
        self._pair("implies")

    def test_branch_local_div(self):
        self._pair("branch_div")

    def test_helper_spec_fun(self):
        self._pair("helper_sfun")

    def test_literal_index_read_after_update(self):
        self._pair("cumSum")

    def test_append_length(self):
        self._pair("reverse_append")


if __name__ == "__main__":
    unittest.main(verbosity=2)
