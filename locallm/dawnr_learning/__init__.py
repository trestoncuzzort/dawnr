"""dawnr's per-person learning: feedback kept per person, a small adapter per person, a sleep between sessions.

DAWNR-LEARNING.md is the account: what each piece does, what it was built
from, and what the measurement found. Imports here are light (standard library
only): adapters.py, sleep.py and measure.py load torch when used.
"""
from .feedback import (PersonStore, Recorder, content_text, default_root, extract_programs,  # noqa: F401
                       final_program, is_wrong_turn, person_id)
