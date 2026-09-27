# dawnr's memory

dawnr remembers each person across sessions: what happened in each
conversation (episodes), what is true about them (facts), how they like
things done (preferences), and what they pinned themselves (notes). At the
start of a conversation it recalls the part of that which fits a token
budget and is most relevant to the person's first message; at the end it
keeps what the person said about themselves. The code is
`locallm/dawnr_memory/`, standard-library Python 3.10+; it plugs into the
harness (`DAWNR-HARNESS.md`) through two hook events and into the chat format
through one token.

Two rules govern all of it, from `AMBITION.md`'s "dawnr grows with the person
using it":

- **The person controls what is remembered about them.** They can read every
  record, correct it, erase it, erase a whole session, export everything and
  erase everything; they can switch remembering and recalling off, and keep a
  single conversation off the record. Nothing is stored silently: each session
  ends with a line saying what was kept.
- **Nothing from outside becomes a fact about the person.** A fetched page, a
  tool's output, an MCP result, the assistant's own words, recalled memory and
  text the person pasted are never taken as the person speaking. This is
  enforced by code at the one place memory is written, not asked of a model.

What was copied, from where (each fetched and read on 2026-09-27):

| piece | copied from | what differs |
|---|---|---|
| extract, then update | Mem0 (Chhikara et al., arXiv:2504.19413): candidate memories from the conversation, then ADD / UPDATE / DELETE / NONE against what is stored; its user-memory prompt, "GENERATE FACTS SOLELY BASED ON THE USER'S MESSAGES" (`mem0/configs/prompts.py`) | the rules are deterministic patterns for now, and "only the person's words" is a gate in code every proposal passes, a model's included; the update is keyed by a slot (a newer statement in the same slot replaces the older); Mem0's later "additive" prompt, which also extracts from assistant messages and from documents the user shares, is exactly what is refused here |
| recall | Generative Agents (Park et al., arXiv:2304.03442, section 4.1): recency (exponential decay) + importance + relevance, each min-max scaled to [0, 1], all weights 1; "the top-ranked memories that fit within the language model's context window" go in | relevance is BM25 against the first message, not embeddings (offline, no model needed, explainable); importance is the extraction's confidence, not a model's 1-to-10 rating; recency decays from when the person last said it, not from the last retrieval, so recalling something cannot keep it fresh on its own |
| BM25 | Lucene's `BM25Similarity` (k1 1.2, b 0.75, idf ln(1 + (N - n + 0.5)/(n + 0.5)), never negative), `rank_bm25`'s shape, `EnglishAnalyzer`'s stop words and `EnglishMinimalStemmer` (Harman's S-stemmer) | standard library, over the person's own records only |
| the session events | Claude Code's hooks (code.claude.com/docs/en/hooks): `SessionStart` (matcher on how the session started, `additionalContext`, cannot block) and `SessionEnd` (matcher on why it ended, side effects only) | `SessionStart` fires when the person's first message arrives, not at launch, so a hook can rank what it recalls by that message; dawnr's two handlers are `builtin` ones |
| where the data lives | platformdirs' `user_data_dir` (github.com/tox-dev/platformdirs) and the XDG Base Directory Specification | the local, never the roaming, folder on Windows |
| owner-only | Python's `os` documentation: `os.mkdir(path, 0o700)` gives an owner-only folder, on Windows (3.13+) an access list for the user and administrators; `os.chmod` on Windows sets only the read-only flag | files are also opened with 0o600 and then set to exactly that |
| the threat model | SpAIware (embracethered.com, 2024: a web page wrote lasting instructions into ChatGPT's memory through its memory tool); MINJA (Dong et al., arXiv:2503.03704: memory injection through queries alone); MEXTRA (Wang et al., arXiv:2502.13172: extracting private memory from an agent); OWASP LLM01:2025; Beurer-Kellner et al., arXiv:2506.08837 (after untrusted input, no consequential action unasked) | the defences are structural (what can be written, and from what), not a filter on what a model says |
| deleting | GNU coreutils' `shred` manual: removing a file leaves its blocks until reused, and overwriting in place does not reach copies kept by journaling, copy-on-write or SSD wear levelling | stated as a limit (section 7), not solved |
| export | GDPR article 20: data "in a structured, commonly used and machine-readable format" | one JSON object per person |

## 1. What is remembered

Four kinds of record, one JSON file each:

| kind | what | made by | example `text` |
|---|---|---|---|
| episode | a dated summary of one session | extraction, once per session (updated in place by later checkpoints of the same session) | `3 messages from the person; topics sorts, numbers, duplicates; tools t x2, web_fetch x1; the last t check passed; outside text was read` |
| fact | something true about the person | extraction from their own words; the person's corrections | `lives in Lisbon`, `works as a nurse`, `asked dawnr to remember: their sister's birthday is May 3` |
| preference | how they like things done | extraction from their own words; the person's corrections | `prefers tabs to spaces`, `from now on: answer in short sentences`, `wants dawnr to always explain dawnr's steps` |
| note | what the person pinned | only the person | `Answer in short sentences.` |

A fact or preference carries the words that established it (`evidence`,
verbatim from the person's message), the session that established it
(`source_session`) and every session that repeated it (`sessions`, the last
20), a `confidence` (0 to 1), its `origin` (`rules`, `model` or `person`),
a `slot` (what it is about: `location`, `name`, `like jazz`, ...), and when it
was created, last said and last changed. A statement is about the person in
the third person with no subject ("lives in Lisbon"), because it is read back
to dawnr later, where "I" would be dawnr.

## 2. Where it lives, and who can read it

    <data folder>/dawnr/memory/<person>/settings.json
                                        episodes/e-<16 hex>.json
                                        facts/f-<16 hex>.json
                                        preferences/p-<16 hex>.json
                                        notes/n-<16 hex>.json

The data folder is `$XDG_DATA_HOME` (if absolute) or `~/.local/share` on Linux
and other Unix, `~/Library/Application Support` on macOS, `%LOCALAPPDATA%` on
Windows; `DAWNR_DATA_DIR` replaces it, and the harness configuration can name
another memory folder. A person id is 1 to 64 of `a-z 0-9 _ -`, lowercased (so
"Ann" and "ann" are one folder on every file system), never a name Windows
reserves.

- **Owner-only.** Every folder is mode 0700 and every file 0600 where the OS
  has modes, set exactly (a person's folders found looser are tightened; a
  memory folder the operator pointed at, which dawnr did not make, keeps its
  own permissions); a folder owned by another account is refused.
- **One person per store.** A `MemoryStore` is bound to one person when it is
  made. Every path it touches is built from that person's validated id, a
  kind's fixed folder name and a record id that must match `[efpn]-[0-9a-f]{16}`:
  nothing from a record, a transcript or a caller becomes a path unchecked. An
  id from another person's memory names a file that does not exist in this
  one, so show, correct and forget cannot reach across; a symbolic link where a
  person's folder, a kind's folder or a record file should be is refused, not
  followed.
- **Plain files.** A person can read their memory with any text editor. Writes
  are atomic (an owner-only temporary file, synced, renamed over the record);
  a temporary file a crash left behind is removed after an hour, or at once
  when its record is forgotten.

## 3. How a session becomes memory

At the end of a session (and, in a window with no reliable end, after every
reply, as a checkpoint: the same session is never counted twice), the
transcript goes through three steps (`extract.end_session`).

**Who is speaking.** The person's messages are split into the part that is
them speaking and the part that is not: fenced blocks, quoted lines (`>`),
indented lines, t programs, `Example:` lines, lines that look like code, text
in quotation marks, and any message over 2,000 characters (a paste) are not
the person speaking, and join the "outside" text. So does everything else in
the transcript: every part of every assistant turn (its words, its tool calls,
every tool and harness output, trusted or not, recalled memory) and the tool
index the harness put at the head of the first message.

**Proposals.** The rules (`RuleProposer`) read the person's speaking parts,
clause by clause, for a small set of first-person patterns: "my name is",
"call me", "I live in", "I'm from", "I work as/at/on", "I'm a ...", "I'm
learning", "I'm working on", "I like / love / don't like / hate", "I prefer",
"I'd rather", "my favorite X is", "my timezone / editor / pronouns / ... is",
"from now on ...", "please always / never ...", "remember that ...", and
"forget that ...". Anything else can propose too: a model later, through
`propose(view)`, or `proposals_from_json()` over a model's
`{"memories": [{"kind", "text", "evidence", "slot"?, "confidence"?}]}` (Mem0's
`{"facts": [...]}` with the evidence each must quote).

**The gate** (`admit`), for every proposal from any source:

1. It is a fact or a preference (episodes and notes are not proposed).
2. Its evidence is the person's own words, verbatim (case and spacing aside),
   in the speaking part of a message they typed this session.
3. In at least one message where they said it, nothing from outside had said
   it before. A sentence the person copied from a page, or typed because the
   assistant told them to, is the page's sentence; an assistant repeating the
   person afterwards changes nothing.
4. The statement says nothing the evidence does not: every content word of it
   is a word of the evidence or one of the fixed template words the rules
   phrase statements with ("lives", "likes", "their", "wants dawnr to", ...).
   Shared nouns alone are not enough, though: "dislikes cats" and "I like
   cats." share every noun once "dislikes"/"likes" drop out as the rules' own
   phrasing, so when the statement asserts a relation the rules can name
   (like/dislike, want/avoid, an ordered "A over B"), the evidence must carry
   that same polarity and order too, a negation's reach running to the next
   punctuation mark as in Pang, Lee & Vaithyanathan's negation tagging for
   sentiment words (arXiv:cs/0205070, sec. 6.1). A relation the rules cannot
   confirm this way is refused, never admitted.
5. It is not a secret or an identifier: passwords, keys, tokens, card and
   account numbers, long digit strings, e-mail addresses and links are not
   remembered on dawnr's own initiative (the person can still pin a note).
6. A model's proposal in a session that read outside text is refused: once
   untrusted text is in the context, what the model proposes may be the page
   speaking, and writing lasting memory is a consequential act
   (arXiv:2506.08837, as the harness's taint rule reads it).

**The update** (Mem0's step, keyed by slot): the same statement said in a new
session raises its confidence (1 - (1 - c)/2) and records the session; a new
statement in a stored slot replaces the old one, evidence included (the
person's newer words win; a model never overwrites what the person wrote
themselves); anything else is added. Within one session only the person's
last word per slot counts. "Forget that I live in Lisbon" removes every fact or
preference holding all of its content words; "forget everything" in
conversation removes nothing (the explicit control does that).

**The episode** is built from counts and a fixed vocabulary plus up to eight
keywords, the person's most used content words (letters only, so no codes or
numbers; clauses the rules made facts of, clauses that look like a secret, and
clauses outside text said first, as when the person retypes a page, are not
counted). No sentence of anyone's reaches it: tool outputs cannot, nor
the assistant's words, nor a tool name the model made up (only names in the
harness's registry are kept; any other call is "another tool").

## 4. How memory comes back

When the person's first message of a conversation arrives, the recall
(`retrieval.recall`):

- takes the pinned notes first, in the order written;
- ranks everything else by recency (a 30-day half-life from when the person
  last said it) + importance (the confidence) + relevance (BM25 of the record
  against the first message), each min-max scaled over the person's records;
- packs first fit in that order into the budget (default 256 tokens), the
  header and the span's three chat tokens included; a record that does not fit
  is skipped and smaller ones after it may still enter;
- renders one line per record, each starting with `- ` (so no line can begin
  like an `Example:` line the t tool reads), each one line by construction
  (whitespace collapsed, control, format and private-use characters dropped).

The text opens the reply as a span of forced tokens, the way a tool's answer
is forced:

    <|assistant_start|><|output_start|><|memory|>dawnr remembers from earlier sessions with this person:
    - note: Answer in short sentences.
    - preference (2026-09-26): prefers tabs to spaces
    - fact (2026-09-20): lives in Lisbon
    - session 2026-09-25: 3 messages from the person; topics sorts, numbers; tools t x2; the last t check passed<|output_end|>...

`<|memory|>` is one new chat token, appended after the harness's tokens past
the vocabulary end (`chat.with_memory_tokens`), so no text can produce it: a
page cannot open or close a memory span. The span is mask 0 in training (read,
never supervised, like every output span), and under the engine's grammar (off
by default) the model can never sample the token. The engine counts the budget
again with the model's own tokenizer and keeps whole lines (`span.py`; the
hook, which does not know the tokenizer, counts UTF-8 bytes, which are never
fewer than the tokens of a byte-level BPE or a character tokenizer). A model
without the token (every checkpoint trained so far) is shown nothing: the
recall is withheld and the person is told why, as untrusted text is withheld
from a model without `<|untrusted|>`. A caller that keeps the reply keeps the
span in it, so later turns see the same memory without recalling again.

## 5. What the person controls

| they want to | how |
|---|---|
| see everything remembered | `python locallm/dawnr_memory --person ann list` (or `--kind fact`), `show <id>`, or the files themselves |
| see what dawnr would be told | `python locallm/dawnr_memory --person ann recall "first message"` |
| correct a record | `correct <id> "lives in Porto"`: their words replace it, the old evidence goes with the old text, the record becomes theirs (forgetting its session no longer takes it), and a model never overwrites it |
| pin something | `pin "Answer in short sentences."`: recalled first, never changed by extraction |
| erase a record | `forget <id> [<id> ...]`: the file is removed, and any temporary copy of it |
| erase what one session added | `forget-session <episode id or session id>`: its episode and every fact it established |
| take it elsewhere | `export [--out file.json]`: one JSON object, the file owner-only |
| erase everything | `forget-everything --yes`: their whole folder is removed; nobody else's is touched |
| stop remembering, or recalling | `settings --remember off`, `settings --recall off` |
| keep one conversation out | say "off the record" or "don't remember this conversation" in it, or run the chat with `--no-memory` |
| forget in conversation | "forget that I live in Lisbon" |
| turn memory on in the window | Settings, "Remember me across conversations" |
| do all of the above in the window | the chat card's Memory... button (`dawnr_memory/window.py`): every record, Forget selected, Correct..., Pin a note..., Export..., Forget everything... (asked first), and both switches |

Every session ends with one line for the person (never for the model): what
was remembered, with ids to forget it by, what was updated, and how many
proposals were not kept and why. A rejected proposal's text is never printed,
so a secret that was refused does not reappear on the screen.

## 6. Wiring

The harness configuration (`DAWNR-HARNESS.md` section 9) takes a `"memory"`
key; without it nothing is recalled and nothing is written, as before:

    {"offline": true,
     "memory": {"person": "ann", "root": "memory", "budget": 256, "half_life_days": 30}}

every key optional (the person defaults to `default`, the root to the data
folder, relative roots resolve from the configuration file's folder).
`build_harness` then adds two `builtin` handlers, `memory_recall` at
`SessionStart` and `memory_extract` at `SessionEnd`, unless the operator's own
hooks already place them. The events are available to any operator hook:

| event | fires | payload beyond the common fields | the hook may |
|---|---|---|---|
| `SessionStart` | once per session, when the first message arrives (`Harness.session_start`, called by the engine) | `source` (the matcher: `startup`, `clear`, ...), `prompt` (the first message, the index removed), `person`, `memory` (root, budget) | add `additionalContext`, which becomes a memory span; nothing blocks; exit 2's stderr goes to the person |
| `SessionEnd` | when the conversation ends (`Harness.session_end`: `clear`, `prompt_input_exit`, `other`), or at each `checkpoint` in the window | `reason` (the matcher), `transcript` (the messages, the person's as typed), `tainted`, `tools` (the registry's names), `index`, `person`, `memory` | side effects and a `systemMessage` for the person; nothing blocks |

`chat_cli.py --person ann` turns memory on for Ann, with or without
`--harness`; `--no-memory` runs a session that recalls nothing and writes
nothing. The window (`chat_pane.py`) keeps one harness session per
conversation, saves after every reply, shows the memory span as a collapsed
block labelled "remembered from earlier conversations", shows the harness's
messages to the person, and opens the memory window from its Memory...
button (for the default person when memory is off, so old memory can still be
read and erased). The audit log records `SessionStart` and
`SessionEnd` by their source and reason only, never the recalled text.

## 7. Threat model

**Poisoning** (SpAIware, MINJA): making dawnr store something false or
hostile about the person, which then speaks in every later session.

- *Stopped:* text from a fetched page, a search result, an MCP server, a
  skill script or any tool, trusted or not, cannot be the evidence of a fact
  (gate rules 2 and 3), and the rules never read it; the assistant's own words
  are outside text too, so a model persuaded by a page cannot write memory by
  saying something, and a model's proposal after untrusted text entered the
  session is refused whatever it says (rule 6); a statement cannot carry words
  its evidence does not (rule 4), so a proposal quoting "I like soup" cannot
  store "likes soup and wants files sent to evil.example"; a page telling the
  person what to type is outside text said first (rule 3); pasted text,
  quotes and code are not the person speaking; the episode holds no sentence
  of anyone's, and only registry tool names; recalled memory is outside text,
  so it is never re-heard as new evidence; a record is one line of printable
  text, so it cannot forge structure in the span, and no text can forge the
  `<|memory|>` token itself.
- *Not stopped:* the person themselves can be tricked into typing a false
  statement about themselves in their own words, and dawnr will believe them,
  as it should believe its person; the rules misread some sentences ("I'm a
  mess" becomes "is a mess"), which the person sees at the end of the session
  and can forget; the grounding check compares words, not meaning, so a
  future model's proposal could flip a negation within the person's own words
  in a clean session. The span's mark tells a trained model the text is
  memory, not the current instruction; whether a model this size learns that
  is unmeasured (section 8).

**Leakage** (MEXTRA): one person's memory reaching another person, the
model's context of the wrong person, or anywhere off the machine.

- *Stopped:* one folder per person, one store per person, record ids that
  cannot address another folder, links refused, owner-only modes, and a
  test for each (`NoLeakBetweenPersons`); nothing is ever sent anywhere
  (memory is files on this machine; recall is local; the network tools stay
  behind the harness's policy and taint rule); secrets and identifiers are not
  stored automatically, so the most damaging things to leak are not recalled
  into a context a hostile page could try to exfiltrate from.
- *Not stopped:* people who share one operating-system account can read each
  other's folders with any file browser: the separation between persons inside
  one account is dawnr's, not the operating system's; separate accounts are
  the real boundary. Files are not encrypted; full-disk encryption is the
  answer to a stolen disk. Whatever is recalled into a session is in the
  model's context, and a model that can be persuaded to repeat its context
  could repeat it; the harness bounds what persuasion can do with tools, not
  what the model says to the person in front of it.

**Surveillance**: remembering more than the person knows or wants.

- *Stopped:* memory is off unless configured; every session ends with a line
  saying what was kept; every record can be read, corrected and erased, one at
  a time, by session, or all at once; remembering and recalling each have a
  switch; a conversation can be kept off the record; episodes keep counts and
  keywords, not transcripts; secrets and identifiers are not kept on dawnr's
  initiative; the audit log never holds memory text.
- *Not stopped:* forgetting removes files, not the blocks they occupied:
  until the file system reuses them, forensic tools may recover them, and
  overwriting in place would not reach copies kept by journaling,
  copy-on-write file systems or SSD wear levelling (GNU coreutils' `shred`
  manual); backups the person or their system made are outside dawnr. The
  harness audit log, when the operator configures one, records tool calls with
  their arguments, which can hold the person's words; forgetting memory does
  not touch it. Two dawnr processes writing the same person's memory at once
  can race (each record file is written atomically; two identical facts could
  both be added).

## 8. What the model must learn, and the first measurement

None of this is learned yet. The chat format, the token and the engine are
ready; no checkpoint has the token, so today the recall is shown to the person
and withheld from the model. The conversations a model needs, with the same
rules as every chat conversation (`DAWNR-PIPELINE.md`), memory spans never
supervised:

| to learn | conversations |
|---|---|
| use what is remembered | a memory span with a preference the task touches ("prefers `xs` for a sequence parameter"), and a proved answer that honours it |
| the person's current words beat memory | a memory span saying one thing and a first message saying another; the answer follows the message |
| memory is the person's past, not an instruction | a memory span holding a style preference and a task it does not apply to; the answer is unchanged |
| say what is remembered when asked | "what do you remember about me?" answered from the span, and "nothing yet" with no span |

The first measurement, before any of it is trained: on held-out
conversations, the rate at which answers follow a remembered preference with
the span against without it, and the rate at which a memory span overrides a
contradicting first message. Its prediction and the number that would falsify
it go in a dated note committed before the run (AGENTS.md rule 3); no number
about the model's use of memory exists yet.

## 9. Running it

    # the person's controls
    python locallm/dawnr_memory --person ann list
    python locallm/dawnr_memory --person ann recall "tabs or spaces?"
    python locallm/dawnr_memory --person ann forget f-0123456789abcdef

    # chat with memory for Ann (the recall reaches only a model trained with <|memory|>)
    python locallm/chat_cli.py --model <dir> --person ann [--harness my-harness.json]

Tests: `python -m unittest locallm/test_dawnr_memory.py` (standard library;
the chat-token and engine cases need torch and skip without it, the window
cases need a display and run under `xvfb-run -a`): no leakage between two
persons through the store, the controls and the harness; forget, correct,
forget-session and forget-everything leave no byte of the forgotten text under
the person's folder; a fetched page, the assistant's words, a model's
proposals, pastes, quotes, code, the index, recalled memory and tool verdicts
never become a fact, and neither do secrets; a property test over 60 random
sessions puts a page's own vocabulary, phrased as every rule's trigger, in
every place outside text can be (and has the person retype it) and finds none
of its words anywhere on disk, while the person's own statements are kept
(it fails if the episode's keywords stop checking who said a clause first); a
model cannot ground a statement that inverts the person's polarity ("dislikes
cats" from "I like cats.") or swaps an ordered preference's sides ("prefers
coffee over tea" from "I prefer tea over coffee"), including a negated one
("I don't like cats."), and a property test flips a grounded proposal's
polarity or the order of its "A over B" over random nouns and checks that the
gate now refuses it; recall never exceeds its budget over random stores and
budgets under three
counters; the rules, updates, reinforcement, order and checkpoints; the
session events' contract; the command line and the Memory window; the token,
the mask and the engine's first reply.
