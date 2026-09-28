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
  ends with a line saying what was kept, what was not and why (a
  contradiction by name), and what dawnr asks them; and nothing stored is
  replaced by something that disagrees with it unless the person says so.
- **Nothing from outside becomes a fact about the person.** A fetched page, a
  tool's output, an MCP result, the assistant's own words, recalled memory and
  text the person pasted are never taken as the person speaking. This is
  enforced by code at the one place memory is written, not asked of a model.

What was copied, from where (each fetched and read on 2026-09-27):

| piece | copied from | what differs |
|---|---|---|
| extract, then update | Mem0 (Chhikara et al., arXiv:2504.19413): candidate memories from the conversation, then ADD / UPDATE / DELETE / NONE against what is stored; its user-memory prompt, "GENERATE FACTS SOLELY BASED ON THE USER'S MESSAGES" (`mem0/configs/prompts.py`) | the rules are deterministic patterns for now, and "only the person's words" is a gate in code every proposal passes, a model's included; the update is keyed by a slot, and only a compatible rewording replaces a stored record ("is a fan of jazz" for "likes jazz"); Mem0's later "additive" prompt, which also extracts from assistant messages and from documents the user shares, is exactly what is refused here |
| the grounding gate | Saltzer & Schroeder, "The Protection of Information in Computer Systems" (1975, web.mit.edu/Saltzer/www/publications/protection/Basic.html), fail-safe defaults: "base access decisions on permission rather than exclusion"; OWASP's Input Validation Cheat Sheet: allowlist validation, "defining exactly what IS authorized", with patterns covering the whole input (`^...$`) and a denylist only as a supplement | the allowlist is the rules' own patterns; a statement they cannot read whole from the person's sentence is refused, true ones included |
| contradictions | de Marneffe, Rafferty & Manning, "Finding Contradictions in Text" (ACL 2008, aclanthology.org/P08-1118): texts contradict only when they are about the same event, and "compatible noun phrases between sentences are assumed to be coreferent in the absence of clear countervailing evidence"; antonymy and negation are closed word sets, while contradictions of structure or lexical content need a model of meaning | decided over everything the person said in the session; "the same thing" is a shared object word (word for word), slot or keyed object; since word patterns cannot tell a structural contradiction from a compatible pair, any two different statements about one thing are a contradiction unless they are on a short list of compatible pairs; the thing is refused and reported, not highlighted |
| reading for contradictions apart from filtering for storage | PostgreSQL's row security (postgresql.org/docs/current/ddl-rowsecurity.html): integrity checks "always bypass row security to ensure that data integrity is maintained", with care needed against "covert channel" leaks through them; and "it could be disastrous if row security silently caused some rows to be omitted", so a setting makes that an error | every statement a pattern reads counts against what it contradicts, one that looks like a secret or whose object is too long included; the secret filter and the length cap decide only what is stored; no reason names a word only a secret-looking statement says, and a reading in the report shows its object as `[withheld]`; a statement too long to keep is refused by name, never dropped unseen |
| a long object's key | CoreNLP's deterministic coreference (github.com/stanfordnlp/CoreNLP, `dcoref/Rules.java`): mentions match by head word (`entityHeadsAgree`), and exact match is relaxed by removing "the phrase after head" (`entityRelaxedExactStringMatch`); pronouns are left out of head match, to a sieve with number and gender agreement | no parser finds the head, so a statement that will not be stored is about every word it holds, each keyed as the rules key that word alone; a lone pronoun object is not read at all, and there is no pronoun sieve |
| a statement that disagrees with a stored one | Wikidata's single-value constraint (wikidata.org/wiki/Help:Property_constraints_portal/Single_value): values that disagree "should not be removed", and an editor decides | Zep (Rasmussen et al., arXiv:2501.13956, sec. 2.2.3) invalidates the older fact and "consistently prioritizes new information", and Mem0's update prompt deletes a contradicted memory: both let the newer statement win, judged by a model. dawnr keeps the stored record and asks the person |
| recall | Generative Agents (Park et al., arXiv:2304.03442, section 4.1): recency (exponential decay) + importance + relevance, each min-max scaled to [0, 1], all weights 1; "the top-ranked memories that fit within the language model's context window" go in | relevance is BM25 against the first message, not embeddings (offline, no model needed, explainable); importance is the extraction's confidence, not a model's 1-to-10 rating; recency decays from when the person last said it, not from the last retrieval, so recalling something cannot keep it fresh on its own |
| BM25 | Lucene's `BM25Similarity` (k1 1.2, b 0.75, idf ln(1 + (N - n + 0.5)/(n + 0.5)), never negative), `rank_bm25`'s shape, `EnglishAnalyzer`'s stop words and `EnglishMinimalStemmer` (Harman's S-stemmer) | standard library, over the person's own records only |
| the session events | Claude Code's hooks (code.claude.com/docs/en/hooks): `SessionStart` (matcher on how the session started, `additionalContext`, cannot block) and `SessionEnd` (matcher on why it ended, side effects only) | `SessionStart` fires when the person's first message arrives, not at launch, so a hook can rank what it recalls by that message; dawnr's two handlers are `builtin` ones |
| where the data lives | platformdirs' `user_data_dir` (github.com/tox-dev/platformdirs) and the XDG Base Directory Specification | the local, never the roaming, folder on Windows |
| owner-only | Python's `os` documentation: `os.mkdir(path, 0o700)` gives an owner-only folder, on Windows (3.13+) an access list for the user and administrators; `os.chmod` on Windows sets only the read-only flag | files are also opened with 0o600 and then set to exactly that |
| the threat model | SpAIware (embracethered.com, 2024: a web page wrote lasting instructions into ChatGPT's memory through its memory tool); MINJA (Dong et al., arXiv:2503.03704: memory injection through queries alone); MEXTRA (Wang et al., arXiv:2502.13172: extracting private memory from an agent); OWASP LLM01:2025; Beurer-Kellner et al., arXiv:2506.08837 (after untrusted input, no consequential action unasked) | the defences are structural (what can be written, and from what), not a filter on what a model says |
| deleting | GNU coreutils' `shred` manual: removing a file leaves its blocks until reused, and overwriting in place does not reach copies kept by journaling, copy-on-write or SSD wear levelling | stated as a limit (section 7), not solved |
| export | GDPR article 20: data "in a structured, commonly used and machine-readable format" | one JSON object per person |

## 1. What is remembered

Four kinds of record, one JSON file each, and one kind of question:

| kind | what | made by | example `text` |
|---|---|---|---|
| episode | a dated summary of one session | extraction, once per session (updated in place by later checkpoints of the same session) | `3 messages from the person; topics sorts, numbers, duplicates; tools t x2, web_fetch x1; the last t check passed; outside text was read` |
| fact | something true about the person | extraction from their own words; the person's corrections | `lives in Lisbon`, `works as a nurse`, `asked dawnr to remember: their sister's birthday is May 3` |
| preference | how they like things done | extraction from their own words; the person's corrections | `prefers tabs to spaces`, `from now on: answer in short sentences`, `wants dawnr to always explain dawnr's steps` |
| note | what the person pinned | only the person | `Answer in short sentences.` |
| pending | a question: something the person said that disagrees with a stored fact or preference; not a fact, never recalled, until they answer it | the update step (section 3) | `lives in Porto`, with `becomes: fact` and `conflicts_with: [f-...]` |

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
                                        pending/q-<16 hex>.json

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
  kind's fixed folder name and a record id that must match `[efpnq]-[0-9a-f]{16}`:
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
4. The statement is one the enumerated patterns make, read whole from the
   person's own words. Anything else is refused ("cannot ground: ..."): the
   gate fails closed. The patterns are the rules' own, plus "I want" and "I
   avoid", which a model may state but the rules do not propose. A sentence
   of the person's that holds the evidence must be read to its end: every
   clause of it by some pattern, nothing after an object but end marks and
   the words the rules drop ("now", "too", ...), no question mark, and no
   negation outside the patterns' own words (a "No," before a clause). So a
   negation reaches its whole sentence, never stopping at a comma: "I don't,
   honestly, like cats." grounds neither "likes cats" nor "dislikes cats",
   because no pattern reads it. One clause of that sentence, inside the
   quoted evidence, must then make exactly the proposed statement: the same
   pattern, so the same relation and polarity ("dislikes" is not "likes",
   "never" is not "always"), and the same object word for word and in order.
   "prefers coffee above tea" is not grounded by "I prefer tea above coffee",
   and no list of order words is needed that could miss one. A model's kind
   and slot, when it gives them, must be the pattern's. This refuses true
   memories too, on purpose: "I live in Lisbon, Portugal.", "No, I like
   cats." and "I don't really, truly like cats." are not remembered. The two
   earlier versions of this check refused only what they could name (a word
   the evidence lacked, then also a polarity or order on their lists) and
   admitted everything else, and each admitted a phrasing nobody had
   foreseen. That is Saltzer and Schroeder's warning against exclusion ("The
   Protection of Information in Computer Systems", 1975, fail-safe defaults:
   a mechanism that excludes "tends to fail by allowing access"). The person
   can always pin a note by hand.
5. It is decided over everything the person said in the session, never one
   clause. Rule 4 read each clause on its own, so an utterance that
   contradicts itself grounded either side: "I like cats, and I don't like
   cats." admitted "likes cats" and "dislikes cats" alike, and the session
   kept the last one and reported nothing; "I prefer tea, and I prefer
   coffee over tea." brought the order swap back through a second clause.
   Now every statement the patterns read anywhere in the person's messages
   is collected: at every word, so a clause after a comma or an "although"
   counts, and so does one in a sentence rule 4 would not admit ("No, I like
   cats"), in a question, or said inside another ("Remember that I don't
   like cats"). Two of them are about the same thing when their objects
   share a word, word for word (stop words and pronouns aside), when they
   fill the same slot (the person's location, name, "favorite editor"), or
   when their slots name the same object as the rules key it ("cat" in
   "wants a cat" and "dislikes cats"); a statement is also about what the
   statements inside its object are about. Two statements about one thing
   that are not the same statement are a contradiction, whether they differ
   in polarity, in order or in relation, and nothing about that thing is
   admitted from the session; the report names it ("contradiction: cats")
   with the two readings, whether or not anything proposed it. The gate does
   not try to tell a contradiction from a compatible pair, because word
   patterns cannot (de Marneffe et al. 2008: a contradiction of structure or
   of lexical content needs a model of meaning), except for a short list of
   pairs that agree ("likes" and "is a fan of" the same thing, "lives in"
   and "is from" the same place, "from now on: X" and "always X"), and a
   statement agrees with what it says inside its object ("Remember that I
   like cats" and "I like cats"). A pair missing from that list costs a true
   memory, never a false one; the opposite-pair table ("likes" / "dislikes",
   "always" / "never") only labels a polarity conflict in the report. A
   statement inside what the person asks to forget is not one they make.
   Every statement a pattern reads counts, whatever its object looks like:
   what may be stored is decided last. Rules 4 and 6 keep some statements
   from being stored (an object over eight words, or 24 in a "remember
   that"; a name that is no name; a hedged "I'm a bit ..."; anything that
   looks like a secret), and until the fourth round they also kept them out
   of this rule, so the other side of the contradiction was admitted cleanly
   and silently: "I like cats.com. I don't like cats." stored "dislikes
   cats", "My favorite tool is my password manager. My favorite tool is a
   hammer." stored the hammer, "My birthday is 05031990. My birthday is May
   3." stored May 3, and "I like cats. I really don't like cats at all
   especially the loud noisy ones that scratch furniture constantly." stored
   "likes cats" with nothing reported. Now each such statement still blocks
   what it contradicts, and the report names the contradiction, as
   PostgreSQL's integrity checks see the rows its row security hides. A
   statement too long to keep is about every word it holds, each keyed as
   the rules key that word alone ("cats" meets "I like cat"), because no
   parser finds its head word; and it is refused by name, "cannot ground:
   object too long", never dropped unseen.
6. It is not a secret or an identifier: passwords, keys, tokens, card and
   account numbers, long digit strings, e-mail addresses and links are not
   remembered on dawnr's own initiative (the person can still pin a note).
   Such a statement still counts under rule 5, and the report does not show
   it: a contradiction is named by a word only when a statement that does
   not look like a secret says that word too (it would have been shown had
   it been kept), else by the slot ("my birthday"), else as "something that
   looks like a secret"; its reading shows the object as `[withheld]`
   ("likes [withheld]").
7. A model's proposal in a session that read outside text is refused: once
   untrusted text is in the context, what the model proposes may be the page
   speaking, and writing lasting memory is a consequential act
   (arXiv:2506.08837, as the harness's taint rule reads it).

**The update** (Mem0's step, keyed by slot, less its newer-wins): the same
statement said in a new session raises its confidence (1 - (1 - c)/2) and
records the session. A statement that disagrees with a stored fact or
preference, by the same rule as a contradiction (about the same thing, and
neither the same statement, nor a compatible one, nor one it holds), does
not replace it: the stored record stays, the proposal is refused as
"conflicts with stored record <id>", and the statement is kept as a pending
question (kind `pending`, never recalled, not a fact) that the person answers
in the Memory window or with `answer <id> new|old`: `new` puts their words in
place of the record, which keeps its id; `old` keeps what was remembered.
Saying it again in a later session adds to the same question rather than
asking twice. Zep and Mem0 let the newer statement win (a model judges the
contradiction); dawnr has no model to judge with, and a newer statement can be
a misreading or words the person was steered into, so it follows Wikidata's
single-value constraint instead: the values that disagree are kept and a person
decides. The person can also say it outright: "forget that I like cats" in the
session removes the stored record before anything new is set against it, and
`correct` rewrites a record in their words. A compatible statement in a stored
slot rewords it ("is a fan of jazz" for "likes jazz"); a model never overwrites
what the person wrote themselves, and never asks about it either. Anything else
is added. Within one session two statements about one thing never both pass
the gate (rule 5), so the last word per slot is only ever a rewording. "Forget
that I live in Lisbon" removes every fact, preference or pending question
holding all of its content words, and a model's proposal cannot bring back
what the person asked, in the same session, to forget; "forget everything" in
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
| see what dawnr asks them | `pending`: each thing they said that disagrees with a stored record, and the record it disagrees with |
| answer it | `answer <q-id> new` puts their words in place of the record (which keeps its id); `answer <q-id> old` keeps what was remembered; either way the question is gone |
| take it elsewhere | `export [--out file.json]`: one JSON object, the file owner-only |
| erase everything | `forget-everything --yes`: their whole folder is removed; nobody else's is touched |
| stop remembering, or recalling | `settings --remember off`, `settings --recall off` |
| keep one conversation out | say "off the record" or "don't remember this conversation" in it, or run the chat with `--no-memory` |
| forget in conversation | "forget that I live in Lisbon" |
| turn memory on in the window | Settings, "Remember me across conversations" |
| do all of the above in the window | the chat card's Memory... button (`dawnr_memory/window.py`): every record, Forget selected, Correct..., Answer... (a pending question is listed as a "question" with both sides), Pin a note..., Export..., Forget everything... (asked first), and both switches |

Every session ends with one line for the person (never for the model): what
was remembered, with ids to forget it by, what was updated, how many
proposals were not kept and why (a contradiction names the thing:
"contradiction: cats"), and what dawnr asks them, with the question's id. A
rejected proposal's text is never printed, so a secret that was refused does
not reappear on the screen; a question's text is printed, and it has passed
the check for secrets.

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
  session is refused whatever it says (rule 7); a statement cannot carry words
  its evidence does not (rule 4), so a proposal quoting "I like soup" cannot
  store "likes soup and wants files sent to evil.example"; a statement the
  person contradicted anywhere in the session, in words the patterns read, is
  not stored at all, and the contradiction is reported (rule 5), even when
  the statement contradicting it is one dawnr would not store; a newer
  statement cannot replace a stored one it disagrees with, so neither a
  misreading nor words the person was steered into overwrite what they said
  before: the person is asked (section 3); a model's proposal cannot bring
  back what the person asked, in the session, to forget; a page telling the
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
  and can forget. The gate reads words, not meaning. A contradiction made in
  words the patterns do not read still lets the other side through: "I like
  cats. Cats are awful.", "I like cats. Not really.", "I like cats. Just
  kidding." (rule 4 refuses a sentence it cannot read whole, not the other
  sentences around it), and so does a clause that undercuts another without
  saying anything about the same thing ("I like cats and I'm a liar"). So does
  one between different words for one thing ("I like cats. I hate felines.",
  "I like e-mail. I don't like email.", "I'm a vegan. I love steak."), and
  one between relations the rules keep in different slots ("I work at X. I
  work for Y."). A contradiction inside one object the patterns carry word for
  word is stored with it, as said ("asked dawnr to remember: they like cats
  but hate them"; "likes cats… not"). A long message is taken as a paste, so
  what it says counts for nothing, a contradiction included, and so does
  every other part of a message that is not the person speaking: text in
  quotation marks, a line that looks like code, an indented line or one
  starting with `>`. So 'I like cats. I don't like "cats".' still keeps
  "likes cats", and so does a second line "I don't like cats -> they
  scratch." A pronoun names nothing a word pattern can match ("I like cats.
  I don't like them."), nor does a quantifier ("I like cats. I hate
  everything."): a lone pronoun object is not read at all, as CoreNLP keeps
  pronouns out of head match, and dawnr has no agreement sieve to resolve
  them. Words are compared as their characters are, with no Unicode
  normalization: "I like café. I don't like café." with the é composed in
  one and decomposed in the other stores both. A statement withheld from
  storage (too long, or looking like a secret) that disagrees with a record
  stored in an earlier session is refused by its own reason and does not
  become a question, because a question's text is stored and shown; the
  stored record stays current. The span's mark
  tells a trained model the text is memory, not the current instruction;
  whether a model this size learns that is unmeasured (section 8).
- *What failing closed costs:* two statements that agree but differ, about
  one thing, are withheld as a contradiction: a shared word is enough ("I
  don't like long answers. From now on, keep answers short." keeps neither,
  and neither does "Always use tabs. Always use type hints."), and so is one
  thing in two relations ("I like tea. I prefer tea over coffee."). Across
  sessions the same pairs become questions ("likes tea" stored, "I prefer tea
  over coffee." later). Sentences the person retyped from a page count as theirs for
  this, so a retyped sentence can withhold one of their own. In the
  poisoning property test below, whose person speaks with only 12 words, the
  statements kept at its seed fell from 372 to 150. Since the fourth round a
  statement dawnr would not store withholds whatever shares a word with it
  too: "My name is Ann. Remember that my email is ann@example.org." keeps
  neither (the name is in the address), and "Always write tests. I want
  tests for the parser module that cover every edge case and error path."
  no longer keeps "always write tests" (a request the rules never propose as
  a memory still counts). A long object brings many words, so it meets more
  statements. (A hedge's degree word, "bit" in "I'm a bit tired", is not
  among the words a statement is about, so "I like 64 bit builds." is still
  kept beside it.) None of the three property tests below changed its count
  (150; 446 and 2,665; 630), because none of their grammars says anything
  secret-looking or over eight words.

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

**Trained and measured** (`locallm/memory_fixtures.py`, `locallm/memory_
conversations.py`, `locallm/memory_eval.py`; numbers in `locallm/memory-
conversations-results-2026-09-27.json`). The one preference the corpus can
apply without a word of new program text -- a name for a sequence parameter,
"prefers `xs`" -- built into the four families above (`use`, `override`,
`unapplied`, `recall`), every span the real output of dawnr's own recall
(`dawnr_memory.harness_hooks`, `retrieval.recall`) run against a store holding
exactly the fact the row is about, every rewritten answer kept only when the
real t tool still verifies it. 197 training conversations (40 use, 40
override, 37 unapplied, 80 recall) added to the tool track's own mix (the
r12 core, 400 steps, `dawnr_pipeline.py`'s mid stage, two seeds): arm A is the
tool track's own 358 base plus 1,007 tool conversations, unchanged; arm B adds
the 197 memory conversations on top (1,562 rows). 112 held-out items,
validation-side documents and held-out phrasings and canaries only, replayed
through the real engine with the span installed and withheld, on the same
task and person both ways:

| | A (no memory data) | B (plus memory) |
|---|---|---|
| memory span shown when installed | 0.0 | 1.0 |
| recall answered from the span | 0.0 | 0.46 (0.68, 0.25) |
| recall says "nothing yet" with no span | 0.0 | 1.0 |
| recall invents a preference with no span | 0.0 | 0.0 |
| renamed parameter follows the span (`use`) | 0.0 | 0.0 |
| renamed parameter follows the message over a contradicting span (`override`) | 0.0 | 0.0 |
| unapplied program left unchanged | 0.18 | 0.07 |
| pass all examples, 133 prompts (the tool track's own guard) | 13.5 | 14.0 |

Two seeds (1337, 1338), means over both; arm A needed no new training -- it
is the tool track's own already-trained checkpoint
(`tool-conversations-results-2026-09-27.json`), read for its `chat-eval.json`
and replayed through `memory_eval.py`, so only arm B (plus memory) trained,
under `flock`/`systemd-run --scope -p MemoryMax=6G`, one seed at a time; 13.1
of the 90 GPU minutes budgeted for this measurement were used, both mid runs
completing with no CUDA or device error.

What it says: **a model with no memory token cannot use memory it is
handed** -- arm A shows the span 0% of the time regardless of what the store
holds, which is the baseline the with/without comparison needs, not a result
about arm B. **Recall transferred, unevenly**: with the span installed, arm B
answers "what do you remember about me?" from it 68% of the time at one seed
and 25% at the other (mean 0.46); with no span it says "nothing yet" 100% of
the time at both seeds and never invents a preference with nothing to have
grounded it. **The two rename families did not transfer at this size**:
`preference_following_with_span` and `message_over_memory` are 0.0 for arm B
at both seeds -- 197 rows over 400 steps, next to the tool track's 1,007, did
not move a rewrite this specific either with the span's help or against a
contradicting one. **`unapplied` moved the wrong way**: arm B changes a
program that memory should leave alone more often than arm A does (0.07
against 0.18) -- not enough data at two seeds to separate from noise, but not
a win, and reported as one. **The guard holds**: pass-all-133 stayed within the tool track's own
tolerance at both seeds (arm B 13 and 15 against arm A's 13 and 14, mean 14.0
against 13.5) -- adding these 197 rows cost nothing measured on the same 133
prompts.
Memory conversations stay opt-in (`dawnr_pipeline.py --extra-conversations`),
the same as the tool conversations, on the strength of one family (`recall`)
transferring and nothing measured breaking; the rename families need more
rows aimed at them before "use what is remembered" or "the person's current
words beat memory" can be claimed.

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
gate now refuses it; the gate fails closed, so the three inputs that got
past that first fix, commas, asides and adverbs inside a negation, "more
than", "above" and "instead of", a verb on no list, a quoted fragment of a
sentence that says otherwise, a question, words after the object, a second
clause no pattern reads, and a model's foreign kind or slot are all refused
as "cannot ground", and so are some true memories; a property test draws
4,000 proposals and sentences from a grammar of those phrasings and finds
every admitted statement literally in the person's sentence (its verb, its
object word for word, and around it only a filler, a trailing "now" or
"though", or a whole clause), while at the committed seed the gate admits
446 of them (the test requires more than 250) and refuses 2,665 that a
nouns-only check would admit (it requires more than 1,000); contradictions
are decided over the whole session: the five inputs that got past the second
fix ("I like cats, and I don't like cats.", "I want candy, and I avoid
candy.", "I prefer tea, and I prefer coffee over tea.", "Always answer
briefly, and never answer briefly.", "I am a fan of cats, and I don't like
cats.") are refused through `admit()`, with the sentence or the clause as the
evidence, and through `end_session()` with the real rules, which report
"contradiction: <thing>" with the two readings; so are contradictions split
across two sentences or two messages, a plural across relations ("wants a
cat" / "dislikes cats"), a statement read after a comma, an "although", a "No,"
or inside a "remember that", and a statement about what a contradicted one
holds ("remember that my birthday is May 3" / "my birthday is June 5"); what
is not a contradiction still passes (the same statement, a compatible pair, a
statement said inside another, one inside a "forget that"); a property test
draws 400 utterances from a grammar with one contradiction inserted at random
(polarity, order or relation; one sentence, two sentences or two messages;
either order; among unrelated statements, fillers and trailing words) and
finds nothing about the contradicted object admitted or stored, the
contradiction reported with its two readings, and every one of the 630
unrelated statements admitted and kept; a statement that disagrees with a
stored record (polarity, order, relation, a slot's value, a record said
inside a "remember that") leaves it as it was and becomes one pending
question however often it is said, never recalled, answered on the command
line or in the Memory window, while "forget that ...", correct, a compatible
rewording and a statement the record holds ask nothing; a model neither
overwrites the person's own record nor brings back what they asked to forget;
a session of 100 statements sharing one word makes one contradiction, not
4,950; no filter for storage hides one side of a contradiction: the five
inputs that got past the third fix ("My birthday is 05031990. My birthday
is May 3.", "I like cats.com. I don't like cats.", "My favorite tool is my
password manager. My favorite tool is a hammer.", "I like
cats@example.com. I don't like cats.", "I like cats. I really don't like
cats at all especially the loud noisy ones that scratch furniture
constantly.") are refused through `admit()`, with the clause or the whole
message as the evidence, and through `end_session()`, which reports
"contradiction: <thing>" with the two readings and shows no word of the
secret in a reason, a reading, the summary or on disk; so are a name that
is no name and a hedged "I'm a bit of a nurse"; a contradiction between two
secret-looking statements is named by its slot or as "something that looks
like a secret"; a statement too long to keep is refused by name ("cannot
ground: object too long"), a "remember that" past 24 words and a clause
past 240 characters included; a long object meets "cat", "a cat" and
"furniture" said on their own; and a property test takes every
contradiction the third round's tests pass (17) and each pair of its
grammar in every placement and order (84), rewrites one side to trip each
filter in turn (a link, an e-mail address, a long number or a secret's
word added to its object, or its object padded past eight words), and in
all 1,010 sessions finds the contradiction detected with the rewritten
side as one of its readings, the other side refused, nothing about the
thing stored, a contradiction reported, nothing the filter caught shown,
and an unrelated statement kept (1,009 of the 1,010 fail on the parent);
recall never exceeds its budget over random stores and budgets under
three counters; the rules, updates, reinforcement, order and checkpoints; the
session events' contract; the command line and the Memory window; the token,
the mask and the engine's first reply.
