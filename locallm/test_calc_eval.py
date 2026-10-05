"""calc_eval.py: GSM8K's final number, what each arm shows from the kept replies, and the report (no server, no dataset)."""
from fractions import Fraction

from locallm import calc_eval as ev

Q = "Janet has 16 eggs. She eats three and bakes with four. She sells the rest for $2 each. How much does she make?"
ROWS = [
    {"id": 1, "question": Q, "answer": "16 - 3 - 4 = <<16-3-4=9>>9 eggs.\n9 * 2 = <<9*2=18>>18.\n#### 18",
     "prose": "She has 9 eggs left and sells them for $2 each.\n#### 18",
     "workings": ["left = 16 - 3 - 4\nanswer = left * 2\n", "answer = (16 - 3 - 4) * 2\n", "answer = 18\n"]},
    {"id": 2, "question": Q, "answer": "#### 18",
     "prose": "16 * 2 = 32, minus 7 is 25.\n#### 25",
     "workings": ["answer = 16 * 2 - 3 - 4\n", "answer = (16 - 3 - 4) * 2\n", "answer = oops\n"]},
    {"id": 3, "question": Q, "answer": "#### 1,000",
     "prose": "The answer is 1,000 dollars.",
     "workings": ["answer = 36\n", "answer = 36\n", "answer = 16 * 2 + 4\n"]},
]


def test_gsm8ks_final_number_and_the_number_a_prose_reply_ends_on():
    assert ev.gold(ROWS[0]["answer"]) == 18 and ev.gold(ROWS[2]["answer"]) == 1000
    assert ev.prose_number("so 9 * 2 = 18\n#### 18 dollars") == 18 and ev.prose_number("The answer is 1,000 dollars.") == 1000
    assert ev.prose_number("#### $1,250.50") == Fraction("1250.5") and ev.prose_number("no number here") is None


def test_each_arm_shows_what_its_rule_allows_from_the_same_replies():
    assert [ev.shown(arm, ROWS[0]) for arm in ev.ARMS] == [18, 18, 18, 18, 18, 18]
    # two workings compute and disagree: one shows the first, agree and calc refuse; prose's 25 has one working behind it
    assert [ev.shown(arm, ROWS[1]) for arm in ev.ARMS] == [25, 25, None, None, 25, None]
    # workings done in the head: agree shows 36, calc uses only the one whose numbers are the question's; no working gives prose's 1,000
    assert [ev.shown(arm, ROWS[2]) for arm in ev.ARMS] == [1000, 36, 36, None, None, None]


def test_the_measured_prompt_is_the_commands_own():
    from locallm import calc
    assert ev.PROSE_SYSTEM == calc.REASON_SYSTEM and ev.ask_prose is calc.ask_reasoned and ev.prose_number is calc.reasoned_number
    assert calc.REASON_SYSTEM == ("Work the problem out step by step. Then give the final number on a line of its own, after ####, "
                                  "with no units.")


def test_the_report_counts_shown_right_and_what_calc_does_where_prose_is_wrong():
    r = ev.report(ROWS)
    assert r["prose"] == {"questions": 3, "shown": 3, "right": 2, "right of shown": round(2 / 3, 4), "wrong shown": 1}
    assert r["one"]["right"] == 1 and r["agree"] == {"questions": 3, "shown": 2, "right": 1, "right of shown": 0.5, "wrong shown": 1}
    assert r["calc"] == {"questions": 3, "shown": 1, "right": 1, "right of shown": 1.0, "wrong shown": 0}
    assert r["settled"] == {"questions": 3, "shown": 2, "right": 1, "right of shown": 0.5, "wrong shown": 1} and r["settled2"]["shown"] == 1
    assert r["where prose is wrong"] == {"questions": 1, "calc shows a wrong answer": 0, "calc shows the right answer": 0, "calc refuses": 1,
                                         "settled shows a wrong answer": 1, "settled2 shows a wrong answer": 0}      # prose's wrong 25 has one working behind it
