# boot_verdict.sh — the one definition of "tup booted", shared by both witnesses.
#
# SOURCED, never run: `. "$HERE/boot_verdict.sh"`. It sets two patterns and
# defines four functions, and does nothing else.
#
# WHY THIS IS A FILE AND NOT A BLOCK IN EACH SCRIPT. "The witness banked BOOTED
# when the machine did not boot" has now been found three times, in two files:
#
#   1. A panic sat in the transcript and the prompt was tested first, so the
#      loop broke on the prompt and the panic was never read (boot_witness.sh).
#   2. The settle window under-ran by one poll — the countdown started on the
#      pass that SAW the prompt — so a panic arriving inside the window the
#      script said it was watching reached nobody (release.sh).
#   3. QEMU exited during the settle window and both scripts still banked
#      BOOTED, because the only liveness test lived in the branch that runs
#      BEFORE the prompt is seen: once the prompt was seen, nothing ever asked
#      again whether the guest was still there (both, measured 2026-09-02 —
#      the guest exited six seconds in and release.sh wrote SHA256SUMS and a
#      RELEASE.md saying "tup login: within 10s").
#
# Each was fixed where it was found, in the file it was found in, and the other
# file kept its own copy of the rules. Twice the copies were reconciled by
# reading one script while editing the other; release.sh still carries a
# comment recording that it went and checked boot_witness.sh by hand. Two
# copies that must agree are the mechanism that produced this class, so there
# is one copy. A duplicated block marked "keep these identical" is an
# instruction to a person; a sourced file is a fact about the program.
#
# WHAT THE VERDICT IS. Not "the loop broke, and where it broke names the
# result" — that is what all three defects had in common: the verdict was a
# side effect of control flow, so every new way of leaving the loop was a new
# way of banking BOOTED. BOOTED is a POSITIVE CONJUNCTION now, computed once,
# at the moment of banking, from state the loop only gathers. Every clause must
# hold. Any one failing names its own verdict, and the name says which.
#
# HOW THE CLAUSES WERE DERIVED. A witness of this shape has exactly three
# channels of observation, and the clauses are what can be asked of them:
#
#   the transcript QEMU writes  -> does a pattern appear in it        (A, B)
#   the guest process it started -> is that pid still there            (D)
#   its own clock, in polls      -> how long has it actually watched   (C, E)
#
# There is no fourth channel: this witness never logs in, never reads guest
# memory, never opens a QEMU monitor socket. Asking each channel both of its
# questions — what it affirms, and what it denies — gives the whole set:
#
#   A. NO PANIC anywhere in the transcript, re-read at banking time. Not "no
#      panic before the prompt", and not "no panic as of the last poll". A
#      panic outranks a prompt; that is defect 1.
#   B. A LOGIN PROMPT THAT IS A LINE, present in the transcript at banking
#      time. This is the positive evidence that userspace came up, and it is
#      anchored to the start of the line because a sentence mentioning the
#      prompt is not the prompt.
#   C. THAT PROMPT WAS SEEN DURING THE RUN, not merely found at the end. The
#      settle window is measured from the sighting, so a prompt nobody watched
#      has no window behind it and cannot be banked.
#   D. THE GUEST WAS STILL ALIVE at the moment of banking. That is defect 3,
#      and it is the clause that has to be asked LAST rather than once, early,
#      in one branch of a loop.
#   E. THE SETTLE WINDOW ACTUALLY ELAPSED, counted in polls that really
#      happened rather than inferred from the loop having exited. That is
#      defect 2, turned from a loop invariant into a checked one.
#
# WHAT THIS DOES NOT COVER, said plainly, because a receipt is read by people
# who did not run it:
#   * A guest that is alive but wedged. `kill -0` answers "the process exists";
#     a kernel that stopped printing without panicking satisfies every clause.
#     Telling an idle login prompt from a hung one means logging in, and this
#     witness does not log in.
#   * A failure that does not use the words in TUP_PANIC_RE — an Oops that
#     never reaches "not syncing", a firmware-level reset, a silent hang, a
#     guest that reboots and prints the same prompt again.
#   * Anything after the settle window. The verdict is scoped to the prompt
#     plus TUP_SETTLE_SECS, and a system that dies a minute later was still
#     BOOTED by this measurement. That is why the window's length is in the
#     verdict string.
#   * Who printed the prompt. The console is guest-controlled; anything that
#     writes `tup login:` at the start of a line satisfies B. What is witnessed
#     is what the console said, not that getty is what said it.
#   * Whether the pid still means what it meant. `kill -0` answers for a
#     number; both callers pass the pid of a background job they started
#     themselves and have not waited on, which is what keeps that number
#     attached to this guest and no other.

# A panic outranks everything, and these are the ways a Linux guest says it on
# a serial console.
TUP_PANIC_RE='Kernel panic|Attempted to kill init|not syncing'

# The prompt must BE the line, not appear in it. The boundary this used to
# anchor on — (^|[^[:alnum:]_-]) — accepts a space, so
#     ERROR: never reached tup login: because getty failed
# scored BOOTED: the one sentence in a transcript that says it did not. The
# match starts the line, and the only things allowed in front of it are
# whitespace and the ANSI escape sequences a serial console really does emit
# (which the old boundary rejected outright, since \033[0m ends in an
# alphanumeric: a genuinely booted system could be filed QEMU EXITED for it).
tup_esc=$'\033'
TUP_PROMPT_RE="^[[:space:]]*($tup_esc\[[0-9;?]*[A-Za-z][[:space:]]*)*tup login:"

tup_saw_panic()   { grep -qE "$TUP_PANIC_RE"  "$1" 2>/dev/null; }
tup_saw_prompt()  { grep -qE "$TUP_PROMPT_RE" "$1" 2>/dev/null; }
tup_guest_alive() { kill -0 "$1" 2>/dev/null; }

# tup_boot_verdict <transcript> <guest-pid> <prompt-seen 0|1> \
#                  <settle-seconds-watched> <settle-seconds-required> <budget>
#
# Prints the verdict on stdout, and returns 0 for BOOTED and nonzero for every
# other one — so a caller may branch on the status or on the string, and the
# two cannot disagree about the same run.
tup_boot_verdict() {
  # Arity first, before the parameters are read: under `set -u` a missing
  # argument would kill the shell at the assignment below, and a caller that
  # drifts is exactly the thing this file exists to make impossible.
  if [ "$#" -ne 6 ]; then
    echo "INTERNAL: tup_boot_verdict needs 6 arguments, got $#"
    return 1
  fi
  local log=$1 pid=$2 prompt_seen=$3 watched=$4 required=$5 budget=$6
  local alive=0
  # Read once, here, and used by every clause below. Two clauses reading the
  # process at two different instants could name two different verdicts for one
  # run, and the receipt would carry whichever happened to be asked first.
  if tup_guest_alive "$pid"; then alive=1; fi

  if tup_saw_panic "$log"; then                                    # A
    echo "PANIC"
    return 1
  fi
  if ! tup_saw_prompt "$log"; then                                 # B
    if [ "$prompt_seen" -eq 1 ]; then
      echo "TRANSCRIPT LOST THE LOGIN PROMPT (seen during the run, gone at banking)"
    elif [ "$alive" -eq 1 ]; then
      echo "TIMEOUT (${budget}s, no login prompt)"
    else
      echo "QEMU EXITED BEFORE THE LOGIN PROMPT"
    fi
    return 1
  fi
  if [ "$prompt_seen" -ne 1 ]; then                                # C
    echo "LOGIN PROMPT ARRIVED TOO LATE TO WATCH (in the transcript, but after the last poll of the ${budget}s budget)"
    return 1
  fi
  if [ "$alive" -ne 1 ]; then                                      # D
    echo "QEMU EXITED DURING SETTLE (prompt seen, guest gone ${watched}s into the ${required}s window)"
    return 1
  fi
  if [ "$watched" -lt "$required" ]; then                          # E
    echo "SETTLE WINDOW DID NOT ELAPSE (${watched}s watched of the ${required}s required)"
    return 1
  fi
  echo "BOOTED"
  return 0
}
