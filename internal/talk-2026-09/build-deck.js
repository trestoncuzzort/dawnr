// The deck is set like the repository's own tables: paper, ink, hairline rules, and the
// verdict words in the two colours the project's tables use. Times New Roman for what is
// said aloud (the manuscript's face); Courier New for anything quoted from the repository.
const pptxgen = require("pptxgenjs");
const fs = require("fs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.author = "Treston Cuzzort";
pres.title = "t and tup";

const INK = "141414", RULE = "B8B8B8", CODEBG = "F4F4F4";
const VER = "1E7B34", VERBG = "E3F1E6", REF = "B2261C", REFBG = "F6E2DF", ABS = "6A6A6A", ABSBG = "ECECEC";
const SERIF = "Times New Roman", MONO = "Courier New";
const TOTAL = 27;
let n = 0;
const scriptOut = [];

function slide(title, notesText) {
  n += 1;
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  if (title) s.addText(title, { x: 0.6, y: 0.35, w: 8.8, h: 0.75, fontFace: SERIF, fontSize: 28, bold: true, color: INK, valign: "middle", margin: 0 });
  s.addText(`${n} / ${TOTAL}`, { x: 8.4, y: 5.2, w: 1.0, h: 0.3, fontFace: MONO, fontSize: 9, color: INK, align: "right", margin: 0 });
  s.addNotes(notesText);
  scriptOut.push({ n, title: title || "t and tup (title slide)", notes: notesText });
  return s;
}
function T(s, str, o) { s.addText(str, Object.assign({ fontFace: SERIF, fontSize: 16, color: INK, margin: 0, valign: "top" }, o)); }
function M(s, str, o) { s.addText(str, Object.assign({ fontFace: MONO, fontSize: 12, color: INK, margin: 0, valign: "top" }, o)); }
function code(s, str, o) {
  s.addShape(pres.shapes.RECTANGLE, { x: o.x, y: o.y, w: o.w, h: o.h, fill: { color: CODEBG }, line: { color: RULE, width: 0.5 } });
  s.addText(str, { x: o.x + 0.15, y: o.y + 0.1, w: o.w - 0.3, h: o.h - 0.2, fontFace: MONO, fontSize: o.fontSize || 12, color: INK, margin: 0, valign: "top" });
}
function rule(s, x, y, w) { s.addShape(pres.shapes.LINE, { x, y, w, h: 0.01, line: { color: RULE, width: 0.75 } }); }
function vrule(s, x, y, h) { s.addShape(pres.shapes.LINE, { x, y, w: 0.01, h, line: { color: RULE, width: 0.75 } }); }
function arrow(s, x1, y1, x2, y2) {
  s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.01, h: Math.abs(y2 - y1) || 0.01,
    line: { color: INK, width: 1, endArrowType: "triangle" }, flipH: x2 < x1, flipV: y2 < y1 });
}
function box(s, x, y, w, h, label, fs) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: "FFFFFF" }, line: { color: INK, width: 0.75 } });
  T(s, label, { x: x + 0.1, y, w: w - 0.2, h, fontSize: fs || 14, align: "center", valign: "middle" });
}
// a verdict pair as the repository prints it, coloured per word
function verdictRuns(real, twin) {
  const col = (w) => (w === "verified" || w === "refuted" ? (w === "verified" ? VER : REF) : ABS);
  return [{ text: real, options: { color: col(real), bold: real === "verified" } }, { text: " / ", options: { color: INK } }, { text: twin, options: { color: col(twin), bold: twin === "refuted" } }];
}
const cell = (t, extra) => ({ text: t, options: Object.assign({ fontFace: SERIF, fontSize: 14, color: INK }, extra || {}) });
const mcell = (t, extra) => ({ text: t, options: Object.assign({ fontFace: MONO, fontSize: 12, color: INK }, extra || {}) });
const head = (t, extra) => ({ text: t, options: Object.assign({ fontFace: SERIF, fontSize: 14, color: INK, bold: true }, extra || {}) });
const vcell = (real, twin) => {
  const ok = real === "verified" && twin === "refuted";
  const runs = ok
    ? [{ text: "v", options: { color: VER, bold: true } }, { text: " / ", options: { color: INK } }, { text: "r", options: { color: REF, bold: true } }]
    : [{ text: real, options: { color: real === "verified" ? VER : ABS, bold: real === "verified" } }, { text: " / ", options: { color: INK } }, { text: twin, options: { color: twin === "refuted" ? REF : ABS, bold: twin === "refuted" } }];
  return { text: runs.map((r) => ({ text: r.text, options: Object.assign({ fontFace: MONO, fontSize: ok ? 10 : 7 }, r.options) })), options: { fill: { color: ok ? VERBG : ABSBG }, align: "center", valign: "middle" } };
};
const TBL = { border: { type: "solid", pt: 0.5, color: RULE }, margin: 0.06, valign: "middle" };
const ASK = "\n\nIF SOMEONE ASKS\n";

// ---------- 1 ----------
{
  const s = slide(null,
`Thanks for having me. I'm going to show you what I've been building since late July. It's one repository with a few parts, but there is one question behind all of it, and I'll keep coming back to that question.

Since I first put this talk together, the project stopped being a plan and started running, and its purpose got sharp. The AI industry's bet is quantity: more data, more parameters, more compute, and clean the data well enough. I'm betting the opposite way: extreme data quality over quantity. Every single example a model learns from has to be proven correct by seven independent proof systems. locallm builds the models from scratch, and t is the filter that decides what they may learn from. I'll show why each part exists, what it measured this week, where it falls short, and how it stacks up against the industry.

The plan: the problem, the tool I built for it, the numbers it produces today, the filter running, and how it stacks up. About thirty minutes, then questions.` + ASK +
`"What does t stand for?" Nothing. It's the letter t, the name of the language. tup is the name of the Linux distribution; the two names are the two halves of the repository.`);
  T(s, "t and tup", { x: 0.6, y: 1.4, w: 8.8, h: 1.1, fontSize: 60, bold: true });
  T(s, "Extreme data quality over quantity: AI models built only\nfrom data that seven proof systems agree is correct", { x: 0.6, y: 2.55, w: 8.8, h: 1.1, fontSize: 22 });
  rule(s, 0.6, 3.95, 8.8);
  T(s, "Treston Cuzzort", { x: 0.6, y: 4.1, w: 6, h: 0.4, fontSize: 16 });
  M(s, "September 2026, updated 2026-09-17", { x: 0.6, y: 4.5, w: 6, h: 0.4, fontSize: 12 });
}

// ---------- 1b thesis ----------
{
  const s = slide("The industry bets on quantity. This project bets on proof.",
`Here is the whole talk on one slide.

The industry's recipe for better AI is scale. Meta trained Llama 3 on more than 15 trillion tokens. The data is cleaned, carefully, but at that size cleaning has to be cheap: rules of thumb, removing duplicates, and other AI models scoring what looks like good text. Mistakes are expected, and the bet is that sheer volume washes them out.

I'm doing the opposite. Not trillions of examples, thousands. And every one of them is proven: seven independent proof systems must agree the program keeps its promise, a deliberately broken copy must be caught, the problem's tests must pass, and it can't be a copy of something already in the pool. Nothing gets in on a judge's opinion.

The models are small on purpose. locallm builds them from nothing on an ordinary computer, so the clean data is the only thing they ever learned. The question the project exists to answer: per parameter, does proven data beat piles of data? The first measurement says yes, at small scale, and I'll show it, including where it doesn't hold yet.` + ASK +
`"Isn't this what Phi already did?" Phi moved in this direction, with filtered and synthetic textbook-quality data, and it worked. But it still decides quality with an AI's judgment, over billions of tokens. This goes to the extreme: no judge at all, only proof.

"Why would less data ever win?" Because a model spends its parameters learning whatever is in the data, including the mistakes. If nothing wrong is in the data, no parameters are spent on wrong things.`);
  T(s, "The industry", { x: 0.6, y: 1.35, w: 4.2, h: 0.4, fontSize: 18, bold: true });
  T(s, "Trillions of tokens (Llama 3: over 15 trillion).\n\nCleaned by rules of thumb, deduplication, and AI models judging quality.\n\nErrors are expected; volume is meant to wash them out.\n\nHundreds of billions of parameters, huge clusters.", { x: 0.6, y: 1.8, w: 4.2, h: 2.4, fontSize: 14 });
  vrule(s, 5.0, 1.35, 2.85);
  T(s, "This project", { x: 5.2, y: 1.35, w: 4.2, h: 0.4, fontSize: 18, bold: true });
  T(s, "Thousands of examples.\n\nEvery one proven by seven independent proof systems, its broken twin caught, its tests passed, never a copy.\n\nNo judge's opinion; nothing wrong gets in.\n\nSmall models built from nothing on an ordinary computer.", { x: 5.2, y: 1.8, w: 4.2, h: 2.4, fontSize: 14 });
  rule(s, 0.6, 4.35, 8.8);
  T(s, [{ text: "The question: ", options: { bold: true } }, { text: "per parameter, does proven data beat piles of data?" }], { x: 0.6, y: 4.5, w: 8.8, h: 0.5, fontSize: 17 });
}

// ---------- 2 ----------
{
  const s = slide("When a program says it is correct, how would you know?",
`This is the question behind everything I'll show you.

Say you have a program and someone claims it is correct. There are three ways to check that claim. You can run it once and see. You can test it on a bunch of inputs. Or you can prove it, meaning show that it does the right thing for every input, not just the ones you tried.

Here is why it matters more now than it did two years ago. A lot of code is now written by AI. It gets written fast, and the slow part is checking it. So the checker is the thing worth building, and the checker has to be trustworthy, because if the checker is wrong, every number that comes out of it is wrong.

That is how I got here. The first two months of this project were a training pipeline where a checker graded an AI's code. About half of the improvement I measured turned out to come from a bug in the checker, not from the model. I'll show that near the end. The rest of the project is what I built so that can't happen again.` + ASK +
`"Isn't testing enough in practice?" Testing catches the inputs you thought of. Proofs cover the ones you didn't. For most software, tests are fine. For a checker that is grading an AI, and whose verdicts become training data, a wrong verdict poisons everything downstream, so I wanted the strongest check available.`);
  const rows = [
    [head("How you check"), head("What you learn")],
    [cell("Run it once"), cell("It worked on that input, today.")],
    [cell("Test it on some inputs"), cell("It worked on the inputs someone thought of.")],
    [cell("Prove it for every input"), cell("It does what the specification says, for every input there is.")],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.45, w: 8.8, colW: [3.0, 5.8], rowH: 0.62 }, TBL));
  T(s, "Today the program may have been written by an AI, faster than anyone can review it.", { x: 0.6, y: 4.3, w: 8.8, h: 0.6, fontSize: 17 });
}

// ---------- 3 ----------
{
  const s = slide("A test checks one input. A proof checks all of them.",
`Let me make "prove" concrete, because this is the word the whole talk rests on.

On the left is a test. It says: when I call max with 3 and 5, I should get 5. That checks one input.

On the right is a specification. It says: for any x and y, the result is at least x, at least y, and is one of them. A proof shows that the code meets that statement for every possible x and y. Not by running them all, which is impossible, but by reasoning about the code the way you'd reason through a math proof.

The tools that check these proofs exist and have for a long time. Dafny from Microsoft Research, Lean and Rocq from the math community, SPARK for Ada and Frama-C for C in safety-critical industry, Verus for Rust, F Star from Microsoft and Inria. The catch: each has its own language, its own rules, and its own quirks. You write your program in their language, and they tell you "proved" or "not proved."` + ASK +
`"How does the tool prove it without running every input?" It turns the code and the specification into logical formulas and hands them to a solver, or in Lean and Rocq's case checks a proof term step by step. If the formulas hold for all values, the program is proved. If the tool can't tell, it says so; that's called "unproved," and it is not the same as "wrong."`);
  T(s, "A test", { x: 0.6, y: 1.4, w: 4.2, h: 0.4, fontSize: 18, bold: true });
  code(s, "assert max(3, 5) == 5", { x: 0.6, y: 1.9, w: 4.2, h: 0.6, fontSize: 14 });
  T(s, "One input. It passed, on that input.", { x: 0.6, y: 2.65, w: 4.2, h: 0.5, fontSize: 15 });
  vrule(s, 5.0, 1.4, 2.4);
  T(s, "A specification, then a proof", { x: 5.2, y: 1.4, w: 4.2, h: 0.4, fontSize: 18, bold: true });
  code(s, "for all x, y:\n  max(x, y) >= x\n  max(x, y) >= y\n  max(x, y) is x or y", { x: 5.2, y: 1.9, w: 4.2, h: 1.15, fontSize: 13 });
  T(s, "Every input. Checked by reasoning, not by running.", { x: 5.2, y: 3.2, w: 4.2, h: 0.6, fontSize: 15 });
  rule(s, 0.6, 4.05, 8.8);
  T(s, "Tools that check such proofs: Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq, F*. Each has its own language and its own rules.", { x: 0.6, y: 4.2, w: 8.8, h: 0.9, fontSize: 16 });
}

// ---------- 3b why each part ----------
{
  const s = slide("The parts, and why each one exists",
`Before the details, here is every part of the repository with the reason it exists, because each one was built to fix a specific problem the part before it exposed.

Every part serves one goal: data so clean that a small model built from it does not learn anything wrong. Quality over quantity only works if the quality is real, so most of the parts are there to make the filter impossible to fool. Models learn from data, so the data has to be clean. To call data clean, you need a check you trust. One proof system can be wrong, so there are seven, and they have to agree. A proof of a vague promise proves nothing, so every program gets a broken twin that the promise must catch. Seven proof systems each have their own language, so t is one language that translates into all seven. A filter nobody can rerun is just a claim, so every number sits in a file with the commit that made it, and tup exists so even the machine has receipts.

I'll come back to this table at the end with what each part measured.` + ASK +
`"Why not just use tests as the filter?" Tests cover inputs someone thought of. This week showed both are needed: proofs catch what tests miss, and tests catch a proof of the wrong problem. The filter uses both.

"Isn't seven overkill?" Each proof system has had soundness bugs. Seven independent teams, seven different logics: a wrong answer has to fool all seven at once.`);
  const rows = [
    [head("Part"), head("What it is"), head("Why it exists")],
    [cell("seven verifiers"), cell("Dafny, Verus, SPARK, Frama-C, Lean, Rocq, F*"), cell("any one checker can be wrong; a wrong verdict has to fool all seven")],
    [cell("twins"), cell("a deliberately broken copy of each program"), cell("a proof of an empty promise proves nothing; the promise must catch the twin")],
    [cell("t"), cell("one small language translated into all seven"), cell("write a program once, get seven independent verdicts")],
    [cell("lifter and sweeps"), cell("Dafny programs translated into t, regraded in bulk"), cell("to test t on programs nobody wrote for it")],
    [cell("locallm"), cell("builds AI models from random numbers, on any computer"), cell("a model whose training data we control completely")],
    [cell("the filter loop"), cell("models write, t keeps what is proven, models rebuild"), cell("the point: extreme quality over quantity, models learn only from what is proven")],
    [cell("tup, receipts, lab app"), cell("a Linux with build receipts; a live view of every check"), cell("so anyone can rerun and watch every claim")],
  ];
  s.addTable(rows.map((r) => r.map((c) => ({ text: c.text, options: Object.assign({}, c.options, { fontSize: 11 }) }))), Object.assign({ x: 0.6, y: 1.25, w: 8.8, colW: [1.75, 3.35, 3.7], rowH: 0.4 }, TBL));
}

// ---------- 4 ----------
{
  const s = slide("Why one verifier is not enough",
`So why not pick one of those tools and be done? Because a single "proved" can be wrong in three ways that the tool itself will never tell you about.

First, mistranslation. You have to write your program in the tool's language. If you translate it wrong, the tool proves a different program than the one you meant. It says "proved," and it is right, about the wrong thing.

Second, an empty specification. If the statement you asked it to prove is so weak that anything satisfies it, "proved" means nothing. The extreme case is "ensures true." Every program satisfies that. Less extreme cases are much harder to spot by eye.

Third, the quiet give-up. Tools time out, or run out of memory, or hit a case they can't handle. If whatever is wrapping the tool reports that as a pass, you get a green light that means nothing. This is the shape of the bug that bit my earlier pipeline: a component kept producing well-formed output after it had stopped measuring anything.

None of these are the verifier being unsound. They are all the human, or the script around the verifier, getting it wrong. So I wanted a setup where each of these would show up as a disagreement.` + ASK +
`"Are the verifiers themselves ever wrong?" Rarely, and it's a big deal when they are. Lean and Rocq check every proof in a tiny trusted kernel, which is the strongest guarantee available. The others rely on a solver. My setup also has a way to catch a verifier bug: if a program that is known to be wrong gets "proved," that cell is flagged as unsound. It hasn't happened on the committed tasks.`);
  const rows = [
    [head("How it fails"), head("What happened"), head("What the tool said")],
    [cell("Mistranslation", { bold: true }), cell("You wrote the wrong program into the tool's language."), cell("proved (the wrong program)")],
    [cell("An empty specification", { bold: true }), cell("The statement is so weak that any program satisfies it."), cell("proved (nothing)")],
    [cell("The quiet give-up", { bold: true }), cell("The tool timed out or gave up, and the script around it reported a pass."), cell("nothing, and the script said proved")],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.45, w: 8.8, colW: [2.4, 3.8, 2.6], rowH: 0.7 }, TBL));
  T(s, "None of the three is the verifier being wrong. All three are invisible to the one tool that produced the verdict.", { x: 0.6, y: 4.45, w: 8.8, h: 0.7, fontSize: 16 });
}

// ---------- 5 ----------
{
  const s = slide("One small program, seven independent verdicts",
`This is t. It's a small language I designed for one job: state what a function must do, and let seven verifiers check it.

Here is a real task from the repository. Read it top to bottom. "task max" takes two integers and returns one. The three "ensures" lines are the promises: the result is at least x, at least y, and is one of them. Then the body, which is ordinary code.

That one file is translated by a script into all seven verifiers' languages. Same program, seven translations. Each verifier checks its own translation and says proved or not. t itself proves nothing. Every verdict comes from a verifier with a long public track record.

Why seven? Go back to the three failure modes. If I mistranslated into one tool, the other six disagree. If the specification is empty, the next slide's trick catches it. If one tool quietly gave up, six others didn't. Seven verdicts on one program catch what one cannot.

One honest caveat: four of the seven use the same solver underneath, called Z3, so they are not seven fully independent opinions. But they are seven different translations and seven different front ends, and Lean and Rocq don't use Z3 at all.` + ASK +
`"Why not just write directly in Dafny or Lean?" Then you have one verifier and all three failure modes. Also, t is much smaller than any of them, which matters for the AI part later: a small language is easier for a model to write and easier to check that it wrote it right.

"How big is t?" Integers, booleans, sequences, pairs, strings, loops with invariants, recursive helper functions, early return. No heap, no floats, no concurrency. Small on purpose.`);
  code(s, `t 0
task max(x: int, y: int) returns (r: int)
  ensures r >= x
  ensures r >= y
  ensures r == x or r == y
{
  if x >= y {
    r := x;
  } else {
    r := y;
  }
}`, { x: 0.6, y: 1.35, w: 4.9, h: 3.05, fontSize: 12 });
  M(s, "t/tasks/max.t", { x: 0.6, y: 4.5, w: 4.9, h: 0.3, fontSize: 10 });
  T(s, "the signature", { x: 5.7, y: 1.62, w: 1.6, h: 0.3, fontSize: 12 });
  T(s, "the promises", { x: 5.7, y: 1.83, w: 1.6, h: 0.3, fontSize: 12 });
  T(s, "the body", { x: 5.7, y: 2.62, w: 1.6, h: 0.3, fontSize: 12 });
  vrule(s, 7.4, 1.35, 3.05);
  T(s, "One file, translated by a script into", { x: 7.6, y: 1.35, w: 1.9, h: 0.6, fontSize: 13 });
  M(s, "Dafny\nVerus\nSPARK\nFrama-C\nLean 4\nRocq\nF*", { x: 7.6, y: 2.0, w: 1.9, h: 1.7, fontSize: 12 });
  T(s, "t itself proves nothing.", { x: 7.6, y: 3.8, w: 1.9, h: 0.6, fontSize: 13 });
}

// ---------- 6 ----------
{
  const s = slide("Every task gets a twin, a deliberately broken copy",
`This is the answer to the empty specification problem.

Every task gets a twin. The twin is the same task with the body deliberately broken by a fixed rule. For max, the rule collapsed the if statement: the twin always returns x. The specification is untouched. Only the code is broken.

Then the rule is: a task counts only if two things are both true. The real program is proved in a verifier, and the twin is refuted in that same verifier. Refuted means the verifier accepted a proof that the specification fails at a specific input. Here that input is x equals 0, y equals 1: the real program gives 1, the twin gives 0, and 0 is less than y, so the promise breaks.

Why does this catch empty specifications? If a specification can't tell the real program from a broken one, it isn't saying anything. So a twin that gets proved is a red flag, and the task is rejected as vacuous.

Two details that took real work. First, the input that breaks the twin, called the witness, is found by running both programs in an interpreter before any verifier sees them. When I measured this, about nine percent of randomly generated twins behaved identically to the real program, so without the witness the whole test would be luck. Second, "refuted" is only ever minted from a verifier proving the failure. A verifier failing to prove the twin is not a refutation. That distinction cost me eleven rows on a table later, and I'll show it.` + ASK +
`"Who picks how to break it?" Nobody. It's a fixed ladder of mutation rules applied the same way to every task, and the first rule that produces a behavior change with a witness is used. That way "the twin failed" always means the same thing.

"What does the verifier do with the witness?" The witness is turned into a small proof: at this input, the specification is false. The verifier checks that proof. That's what makes a refutation positive evidence, not the absence of a proof.`);
  T(s, "the real program", { x: 0.6, y: 1.3, w: 4.2, h: 0.3, fontSize: 13 });
  code(s, `task max(x: int, y: int) returns (r: int)
  ensures r >= x
  ensures r >= y
  ensures r == x or r == y
{
  if x >= y { r := x; }
  else      { r := y; }
}`, { x: 0.6, y: 1.6, w: 4.2, h: 1.85, fontSize: 11 });
  s.addText(verdictRuns("verified", "verified").slice(0, 1), { x: 0.6, y: 3.55, w: 4.2, h: 0.3, fontFace: MONO, fontSize: 13, margin: 0 });
  T(s, "the twin, same specification, broken body", { x: 5.2, y: 1.3, w: 4.2, h: 0.3, fontSize: 13 });
  code(s, `task max(x: int, y: int) returns (r: int)
  ensures r >= x
  ensures r >= y
  ensures r == x or r == y
{
  r := x;
}`, { x: 5.2, y: 1.6, w: 4.2, h: 1.85, fontSize: 11 });
  s.addText([{ text: "refuted", options: { color: REF, bold: true } }, { text: "  witness x = 0, y = 1: real 1, twin 0", options: { color: INK } }], { x: 5.2, y: 3.55, w: 4.2, h: 0.3, fontFace: MONO, fontSize: 11, margin: 0 });
  rule(s, 0.6, 4.05, 8.8);
  T(s, [
    { text: "A task counts only when the real program is verified and the twin is refuted at a concrete input. ", options: { bold: true } },
    { text: "The verifier checks a proof that the promise fails at the witness. A failure to prove is never counted as a refutation." },
  ], { x: 0.6, y: 4.15, w: 8.8, h: 0.95, fontSize: 14 });
}

// ---------- 7 ----------
{
  const s = slide("The seven verifiers",
`Here are the seven, with the versions I'm running and what each is built on. You don't need to know these tools. Three things are worth saying out loud.

They come from different communities. Dafny and F Star from Microsoft Research, Verus from the Rust world, SPARK from the Ada industry, Frama-C from the C safety world, Lean and Rocq from mathematics.

Four of them use the same solver underneath, Z3. Frama-C uses a different solver, Alt-Ergo. Lean and Rocq don't use a solver at all: they check a proof term in a small trusted kernel, which is the strongest kind of check there is.

All seven are installed without administrator rights, on Linux and macOS. Five run natively on Windows, all seven under the Windows Subsystem for Linux. There are install pages for each operating system in the repository, and the macOS and Windows ones were measured on real machines.` + ASK +
`"Why these seven?" They are the mature, actively maintained, freely available program verifiers with a public record. If an eighth appears, the design lets me add a translation for it.

"Does everyone have to install all seven?" No. The tools run with whatever verifiers are present and refuse to give a verdict with fewer than two.`);
  const rows = [
    [head("Verifier"), head("Version"), head("Built on")],
    [cell("Dafny"), mcell("4.11.0"), cell(".NET, Z3 solver")],
    [cell("Verus"), mcell("0.2026.08.30"), cell("Rust, Z3 solver")],
    [cell("SPARK (GNATprove)"), mcell("FSF 16.1.0"), cell("Ada, Why3, Z3 solver")],
    [cell("Frama-C"), mcell("33.0"), cell("C with ACSL, Alt-Ergo solver")],
    [cell("Lean 4"), mcell("4.33.1"), cell("kernel-checked proof terms")],
    [cell("Rocq"), mcell("9.2"), cell("kernel-checked proof terms")],
    [cell("F*"), mcell("2026.08.30"), cell("Z3 solver")],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.35, w: 8.8, colW: [2.6, 2.2, 4.0], rowH: 0.38 }, TBL));
  T(s, "All seven run without root on Linux and macOS; five natively on Windows, all seven under WSL2.", { x: 0.6, y: 4.6, w: 8.8, h: 0.5, fontSize: 14 });
}

// ---------- 8 ----------
{
  const s = slide("What agreement looks like",
`This is the table the whole project produces. One row per task, one column per verifier. Each cell has two verdicts: the real program, then the twin. Green means the real is verified and the twin is refuted. That's the only reading that counts.

Today the repository holds 34 hand-written tasks. 30 of them are green in all seven columns. The other four are blocked by named cells, and you can see two of them here. min_max times out in Rocq. split_join times out in SPARK, Frama-C abstains, and F Star can't prove it. Those are not failures of the program. They are a verifier not finishing, and the table says so instead of hiding it.

The second number is the conformance suite. Those are 66 probe tasks where I declared in advance what each verifier should say, including probes designed to be refuted, to be vacuous, or to be rejected. That suite tests my instrument, not the programs. It reads 457 of 462 cells right. The five open cells are all Frama-C, and each has a reason written down.

Every number in the repository is produced by a script and written to a file with a date on it.` + ASK +
`"What does abstain mean?" The verifier declined to give a verdict, usually because the translation uses something it doesn't handle. It is recorded as abstain rather than as a pass or a fail.

"Is 30 of 34 good?" The four are known blockers with the verifier named. The table isn't the point; the point is that the table is honest and anyone can regenerate it.`);
  const H = (t) => ({ text: t, options: { fontFace: MONO, fontSize: 9, bold: true, align: "center" } });
  const nm = (t) => ({ text: t, options: { fontFace: MONO, fontSize: 9 } });
  const v = () => vcell("verified", "refuted");
  const rows = [
    [H("task"), H("dafny"), H("verus"), H("spark"), H("framac"), H("lean"), H("rocq"), H("fstar")],
    [nm("abs"), v(), v(), v(), v(), v(), v(), v()],
    [nm("max"), v(), v(), v(), v(), v(), v(), v()],
    [nm("gcd"), v(), v(), v(), v(), v(), v(), v()],
    [nm("is_prime"), v(), v(), v(), v(), v(), v(), v()],
    [nm("min_max"), v(), v(), v(), v(), v(), vcell("timeout", "refuted"), v()],
    [nm("split_join"), v(), v(), vcell("timeout", "refuted"), vcell("abstain", "abstain"), v(), v(), vcell("unproved", "refuted")],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.35, w: 6.0, colW: [1.0, 0.72, 0.72, 0.72, 0.72, 0.7, 0.7, 0.72], rowH: 0.36 }, TBL, { margin: 0.02 }));
  T(s, "Six of the 34 rows. Each cell reads real / twin; v / r is verified / refuted.", { x: 0.6, y: 4.05, w: 6.0, h: 0.35, fontSize: 12 });
  M(s, "t/AGREEMENT.md, t/CONFORMANCE.md, 2026-09-15", { x: 0.6, y: 4.75, w: 6.0, h: 0.3, fontSize: 10 });
  vrule(s, 6.9, 1.35, 3.6);
  M(s, "30 of 34", { x: 7.1, y: 1.35, w: 2.4, h: 0.6, fontSize: 26, bold: true });
  T(s, "hand-written tasks verified with the twin refuted in all seven verifiers", { x: 7.1, y: 1.95, w: 2.4, h: 1.0, fontSize: 13 });
  M(s, "457 of 462", { x: 7.1, y: 3.1, w: 2.4, h: 0.6, fontSize: 26, bold: true });
  T(s, "conformance cells: probes with a declared expected verdict per verifier", { x: 7.1, y: 3.7, w: 2.4, h: 1.0, fontSize: 13 });
}

// ---------- 9 ----------
{
  const s = slide("Programs nobody wrote for t",
`Thirty-four tasks I wrote myself is a demo, not evidence. So the next step was programs nobody wrote for t.

DafnyBench is a public benchmark: 785 programs written in Dafny, one of the seven verifiers, with specifications. I built a translator, called the lifter, that reads a Dafny program and writes the t version. Every translation is checked two ways: a lemma that the verifier proves, and a differential run, meaning both programs are executed on the same inputs and must agree. Thirty-five semantic decisions the lifter had to make are written down, each with its reason.

The flow: 785 Dafny programs go in. 326 come out as t tasks; the rest use features t doesn't have yet, and the reason each was refused is recorded by name. Those 326 go through all seven verifiers with their twins. 182 of them read verified and refuted in all seven columns.

By a separate count, 334 of the 643 DafnyBench programs that can be graded fall inside t's current language. The gap between those numbers is lifter rules I still have to write.` + ASK +
`"What's a lemma here?" A small statement the verifier proves that says the t translation and the original Dafny program compute the same thing. It's the verifier checking my translator.

"Why DafnyBench first and not Python?" Because Dafny programs already carry specifications. From Python you'd have to invent the specification, which is the AI part, later in the talk.`);
  const st = [["785", "Dafny programs in DafnyBench", 0.6], ["326", "t tasks after the lifter", 3.85], ["182", "verified with the twin refuted in all seven", 7.1]];
  st.forEach((b) => {
    M(s, b[0], { x: b[2], y: 1.4, w: 2.3, h: 0.7, fontSize: 34, bold: true });
    T(s, b[1], { x: b[2], y: 2.15, w: 2.3, h: 0.8, fontSize: 14 });
  });
  arrow(s, 3.0, 1.75, 3.75, 1.75); arrow(s, 6.25, 1.75, 7.0, 1.75);
  T(s, "lifter", { x: 3.0, y: 1.35, w: 0.75, h: 0.3, fontSize: 12, align: "center" });
  T(s, "7 verifiers", { x: 6.15, y: 1.35, w: 0.95, h: 0.3, fontSize: 12, align: "center" });
  rule(s, 0.6, 3.15, 8.8);
  T(s, "Every translation is checked twice: by a lemma the verifier proves, and by running both programs on the same inputs.\n\nThe 35 decisions the lifter makes are recorded with their reasons. A program it cannot translate is refused with the missing construct named.", { x: 0.6, y: 3.3, w: 8.8, h: 1.8, fontSize: 15 });
}

// ---------- 10 ----------
{
  const s = slide("57 of 164, and the bar is 82",
`Inside DafnyBench there is a subset of 164 programs that a language model wrote in Dafny, from problems in a public set called MBPP. Those 164 are the ones I care most about, because they are the shape of thing an AI writes: short functions from a one-sentence problem.

This chart is that number over the nine full sweeps since September 6. A sweep means: re-lift every program, re-run all seven verifiers on every task and every twin, and rewrite the table. It went 5, 34, 48, 53, 56, then down to 45, then 54, 56, 57.

Today: 99 of the 164 translate into t, and 57 of the 164 read verified and refuted in all seven verifiers. The bar I set for version 1.0 is 82, half of them, plus someone other than me reproducing the table from a clean checkout.

The drop from 56 to 45 is the next slide. It was on purpose.` + ASK +
`"Why is 82 the bar?" Half. It's a round line that says the language covers the common case of what an AI writes, without claiming everything.

"What blocks the other rows?" The roadmap names each one. The biggest: a loop invariant about membership in a growing sequence that three verifiers can't yet prove, a size bound Frama-C needs from a loop invariant, and a bound lemma Rocq needs for recursive helper functions. After that it's translator rules for features like sets and real numbers.`);
  s.addChart([
    { type: pres.charts.BAR, data: [{ name: "in all seven", labels: ["1", "2", "3", "4", "5", "6", "7", "8", "9"], values: [5, 34, 48, 53, 56, 45, 54, 56, 57] }],
      options: { chartColors: [INK], showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: INK, dataLabelFontFace: MONO, barGapWidthPct: 70 } },
    { type: pres.charts.LINE, data: [{ name: "the bar, 82", labels: ["1", "2", "3", "4", "5", "6", "7", "8", "9"], values: [82, 82, 82, 82, 82, 82, 82, 82, 82] }],
      options: { chartColors: [REF], lineSize: 1.5, lineDataSymbol: "none", showValue: false } },
  ], { x: 0.6, y: 1.3, w: 6.2, h: 3.8, showLegend: true, legendPos: "b", legendFontSize: 11, legendColor: INK, legendFontFace: SERIF,
    catAxisTitle: "sweep, September 6 to 15", showCatAxisTitle: true, catAxisTitleFontSize: 11, catAxisTitleColor: INK, catAxisTitleFontFace: SERIF,
    catAxisLabelColor: INK, catAxisLabelFontSize: 11, catAxisLabelFontFace: MONO, valAxisLabelColor: INK, valAxisLabelFontSize: 11, valAxisLabelFontFace: MONO,
    valAxisMinVal: 0, valAxisMaxVal: 100, valAxisMajorUnit: 20, valGridLine: { color: "E0E0E0", size: 0.5 }, catGridLine: { style: "none" },
    showTitle: false, chartArea: { fill: { color: "FFFFFF" } }, plotArea: { fill: { color: "FFFFFF" } } });
  vrule(s, 7.0, 1.35, 3.6);
  M(s, "57 of 164", { x: 7.2, y: 1.35, w: 2.3, h: 0.5, fontSize: 22, bold: true });
  T(s, "model-written programs verified with the twin refuted in all seven, today", { x: 7.2, y: 1.9, w: 2.3, h: 0.9, fontSize: 13 });
  M(s, "82", { x: 7.2, y: 2.9, w: 2.3, h: 0.5, fontSize: 22, bold: true });
  T(s, "the bar for 1.0, with a second person reproducing the table", { x: 7.2, y: 3.45, w: 2.3, h: 0.8, fontSize: 13 });
  M(s, "99 of 164 lift into t", { x: 7.2, y: 4.35, w: 2.3, h: 0.3, fontSize: 10 });
  M(s, "t/COVERAGE-mbpp-dfy-lifter.md", { x: 7.2, y: 4.6, w: 2.3, h: 0.5, fontSize: 9 });
}

// ---------- 11 ----------
{
  const s = slide("Why the count went down once, on purpose",
`This one is about what a number is allowed to mean.

Until September 12, five of the seven verifier wrappers had a shortcut. If the verifier failed to prove the twin, the wrapper counted that as "refuted." It feels reasonable: the broken program didn't prove, so it's broken. But "I couldn't prove it" and "I proved it's wrong" are different claims. A timeout would count as a refutation. Incompleteness was being sold as evidence.

So I purged it. Now every verifier has exactly one door to "refuted": it must accept a proof that the specification fails at the witness input. Positive evidence only.

The cost was immediate: 56 of 164 dropped to 45. Eleven rows had been counting on the shortcut. Over the next three days I earned them back properly, by building the certificates the verifiers needed, and the count is now 57, above where it was, with every refutation meaning the same thing.

That is the rule the whole repository runs on. A count that rises because the rule got weaker is not progress.` + ASK +
`"How did you find it?" Three adversarial audits of my own instruments after the first version went public. Each one was a session where the only goal was to break my own claims. The write-ups are in the repository as witness files with dates.`);
  const rows = [
    [head("Before September 12"), head("Since September 12")],
    [cell("In five of seven verifiers, a twin the verifier could not prove was counted as refuted. A timeout counted as evidence that the program was wrong."),
     cell("One door to refuted, in every verifier: it must accept a proof that the specification fails at the witness input. A failure to prove is recorded as unproved and counts for nothing.")],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.45, w: 8.8, colW: [4.4, 4.4], rowH: [0.4, 1.3] }, TBL, { valign: "top" }));
  s.addText([
    { text: "56", options: { fontFace: MONO, bold: true, fontSize: 28 } }, { text: "  fell to  ", options: { fontSize: 16 } },
    { text: "45", options: { fontFace: MONO, bold: true, fontSize: 28 } }, { text: "  and was earned back to  ", options: { fontSize: 16 } },
    { text: "57", options: { fontFace: MONO, bold: true, fontSize: 28 } },
  ], { x: 0.6, y: 3.85, w: 8.8, h: 0.6, fontFace: SERIF, color: INK, margin: 0, valign: "middle" });
  T(s, "with every refutation meaning the same thing.", { x: 0.6, y: 4.5, w: 8.8, h: 0.5, fontSize: 16 });
}

// ---------- 12 ----------
{
  const s = slide("Auditing the instrument itself",
`If the checker is the product, the checker has to be attacked. Three things I did to my own tools.

First, fuzzing. I generated 1,009 random t tasks, ran all seven verifiers on each with their twins, 7,063 verdict cells, and looked for any error that all seven made together. None. Errors happen, but they don't line up, which is what seven independent checkers are for.

Second, the witness measurement from earlier. About nine percent of randomly generated twins behaved identically to the real program. That measurement is why every twin now has to carry a witness input before a verifier sees it.

Third, the audits found real holes. Frama-C's translation had a definedness gap, where an expression that is undefined in t was defined in C, fixed in the translation. And the refuted shortcut from the last slide. Both are written up as dated witness files.

Also in the repository: a conformance suite with declared expected verdicts, and a rule that when a verifier proves a twin that the interpreter says is wrong, that cell is flagged as unsound, the signal of a verifier bug. It has not fired on the committed tasks.` + ASK +
`"What's a definedness gap?" In t, dividing by zero has no value; the program is undefined there. In C it does something. If the translation doesn't carry "undefined" across, C could prove something t never claimed. The fix makes the C version refuse the same inputs t does.`);
  const rows = [
    [mcell("1,009", { fontSize: 20, bold: true }), cell("randomly generated t tasks, each with its twin")],
    [mcell("7,063", { fontSize: 20, bold: true }), cell("verdict cells across the seven verifiers")],
    [mcell("0", { fontSize: 20, bold: true }), cell("errors shared by all seven")],
    [mcell("9.2%", { fontSize: 20, bold: true }), cell("of generated twins behaved identically to their real program, so every twin now carries a witness input before any verifier runs")],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.4, w: 8.8, colW: [1.6, 7.2], rowH: 0.55 }, TBL));
  T(s, "Two holes the audits found and fixed: a definedness gap in the Frama-C translation, and the refuted shortcut. A verifier that proves a twin the interpreter refutes is flagged unsound; that has not happened on the committed tasks.", { x: 0.6, y: 3.9, w: 8.8, h: 1.2, fontSize: 15 });
}

// ---------- 13 ----------
{
  const s = slide("The corpus t is aimed at",
`Where is this going? At natural-language programming problems, the kind an AI is given every day: a sentence describing a function, and tests.

I collected 24,748 of them from four public sources, with their reference solutions and tests, checked byte for byte against a manifest. 4,239 of them are function-shaped; the rest read from standard input and need a signature extracted first.

Then I ran a census: for each problem, what would t need to express its solution, and which feature is the one thing blocking it. Today 772 of the 4,239 function-shaped problems fall inside t's language, about eighteen percent. The census also ranks the missing features by how many problems each one unblocks. Unbounded loops, imports of libraries, tuples of three or more, and nested sequences top the list.

That ranking decides what gets added next. Each new feature gets a meaning in every one of the seven verifiers, and then the census runs again. In the two weeks before this talk that was: integer division, early return, sequences as values, break, sequence literals and slices, strings, pairs, nested sequences, and a seventeen-function string library. Each one lowered into all seven.` + ASK +
`"Why not just support Python?" Every feature has to mean the same thing in seven verifiers, and I have to be able to check that it does. That's expensive per feature, so the census decides the order.

"Is eighteen percent low?" It's the honest number today, and there is a file that says exactly which feature moves it next.`);
  const rows = [
    [head("Source"), head("Problems", { align: "right" })],
    [cell("MBPP"), mcell("974", { align: "right" })], [cell("HumanEval"), mcell("164", { align: "right" })],
    [cell("APPS"), mcell("10,000", { align: "right" })], [cell("CodeContests"), mcell("13,610", { align: "right" })],
    [cell("Total", { bold: true }), mcell("24,748", { align: "right", bold: true })],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.4, w: 3.6, colW: [2.2, 1.4], rowH: 0.38 }, TBL));
  M(s, "nl/manifest.json", { x: 0.6, y: 3.75, w: 3.6, h: 0.3, fontSize: 10 });
  vrule(s, 4.6, 1.4, 3.6);
  M(s, "772 of 4,239", { x: 4.8, y: 1.4, w: 4.6, h: 0.5, fontSize: 22, bold: true });
  T(s, "function-shaped problems inside t's language today (18.2%)", { x: 4.8, y: 1.95, w: 4.6, h: 0.5, fontSize: 14 });
  T(s, "The census ranks what to add next by problems unblocked:", { x: 4.8, y: 2.65, w: 4.6, h: 0.4, fontSize: 14, bold: true });
  T(s, "unbounded loops (while true, continue)\nlibrary imports beyond math, sys and typing\ntuples of three or more, nested tuples\nsequences of sequences the reader cannot classify", { x: 4.8, y: 3.1, w: 4.6, h: 1.6, fontSize: 14, lineSpacingMultiple: 1.15 });
}

// ---------- 14 ----------
{
  const s = slide("The training loop",
`Now the AI part, which is where the project started and where it's going.

The loop: take a problem statement. A language model writes a t task for it: the signature, the promises, and the body. The seven verifiers grade that task, and the grader also runs the problem's own tests. Then the interesting move: the twin. If the model's task verifies and its twin is refuted, the refuted twin, with its witness input, is a concrete bug with a concrete counterexample. That pair, the good program and its broken sibling with the input that tells them apart, is the training data. The model trains on the bugs it can prove are bugs, and goes around again.

What makes this different from the usual "train on code that passes the tests" is the grader. Tests check inputs someone thought of. Seven verifiers plus a refuted twin check the specification for every input and check that the specification says something. The reward is much harder to fake.

The grader is one script, and it reproduces the whole agreement table cell for cell from the committed tasks, so the thing that grades the model is the same thing that produced every number in this talk.` + ASK +
`"Which model?" So far a small open one, Qwen 2.5 Coder at 1.5 billion parameters, and a 7 billion one for a first experiment. Both run on the lab machine.

"Why is the twin the training signal and not the verified program?" The verified program alone tells the model what right looks like. The twin with a witness tells it exactly where wrong begins. That's the information tests don't carry.`);
  const bx = [["a problem\nstatement", 0.6], ["a model writes\na t task", 2.9], ["seven verifiers\ngrade it, with tests", 5.2], ["a refuted twin\nwith its witness", 7.5]];
  bx.forEach((b) => box(s, b[1], 1.55, 1.9, 1.0, b[0], 13));
  arrow(s, 2.5, 2.05, 2.9, 2.05); arrow(s, 4.8, 2.05, 5.2, 2.05); arrow(s, 7.1, 2.05, 7.5, 2.05);
  s.addShape(pres.shapes.LINE, { x: 8.45, y: 2.55, w: 0.01, h: 0.65, line: { color: INK, width: 1 } });
  s.addShape(pres.shapes.LINE, { x: 3.85, y: 3.2, w: 4.6, h: 0.01, line: { color: INK, width: 1 } });
  s.addShape(pres.shapes.LINE, { x: 3.85, y: 2.55, w: 0.01, h: 0.65, line: { color: INK, width: 1, endArrowType: "triangle" }, flipV: true });
  T(s, "the bug and the input that proves it become training data; the model trains and goes around again", { x: 3.9, y: 3.3, w: 4.6, h: 0.5, fontSize: 12, align: "center" });
  rule(s, 0.6, 3.95, 8.8);
  T(s, "The reward is a specification proved for every input, with a twin proving the specification has content. Tests are checked too. The grader is one script and reproduces the agreement table cell for cell.", { x: 0.6, y: 4.1, w: 8.8, h: 1.0, fontSize: 15 });
}

// ---------- 15 ----------
{
  const s = slide("What the loop measured with a small model",
`I ran the loop twice with a 1.5 billion parameter model, which is small; it fits on one graphics card. Held-out means problems the model never trained on, 161 of them.

The number that moved: answers that verified with a refuted twin in at least one verifier went from 9 to 15 after two rounds. With three samples per problem, 12 to 16. So the model got better at writing tasks the verifiers accept.

Two numbers didn't move, and they matter more. Test passes stayed flat, so it got better at satisfying the grader without getting better at the problems. And parse failures didn't move at all: at the start, 227 of 368 replies weren't even valid t, and after training, the same share. The model can't read the parser's error, so it can't fix it. I'm calling that the parse wall.

So the loop works mechanically, and it's paused. The next step needs a model large enough to read a verifier's error message and repair its answer. The script for that is written; what's missing is API access to a large model.` + ASK +
`"Is 9 to 15 significant?" It's two rounds on a tiny model. It shows the pipeline works and that the twin signal moves the number the twins measure. I don't claim more than that, and the table with every stage is in the repository.

"Why not use a bigger open model on the lab machine?" The 7 billion one fits and was used for the first experiment. Larger ones don't fit alongside other people's jobs. The blocked step is a frontier-size model through an API.`);
  const rows = [
    [head("held-out, 161 problems"), head("before", { align: "center" }), head("after two rounds", { align: "center" })],
    [cell("verified with a refuted twin, some verifier"), mcell("9", { align: "center" }), mcell("15", { align: "center" })],
    [cell("same, three samples per problem"), mcell("12", { align: "center" }), mcell("16", { align: "center" })],
    [cell("passes the problem's tests"), cell("did not move", { align: "center" }), cell("did not move", { align: "center" })],
    [cell("replies that fail to parse as t"), mcell("61%", { align: "center" }), cell("did not move", { align: "center" })],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.4, w: 8.8, colW: [4.6, 2.1, 2.1], rowH: 0.42 }, TBL));
  M(s, "Qwen 2.5 Coder, 1.5B parameters, one lab GPU. t/LOOP-CURVE.md", { x: 0.6, y: 3.6, w: 8.8, h: 0.3, fontSize: 10 });
  rule(s, 0.6, 4.0, 8.8);
  T(s, [{ text: "The parse wall. ", options: { bold: true } }, { text: "A small model cannot read the parser's error, so it cannot fix it. What changed since: a 27B model on the lab GPUs writes valid t often enough (143 of 368 well-formed, 44 all seven with tests), so the loop now runs with a big model generating and t filtering." }], { x: 0.6, y: 4.15, w: 8.8, h: 1.0, fontSize: 14 });
}

// ---------- 16 ----------
{
  const s = slide("tup is a Linux built from source, with a receipt for every step",
`The second half of the repository. tup is a Linux distribution built from source by a script, where every step leaves a receipt.

The base is Linux From Scratch, the book that walks you through building a Linux system by hand from source code. tup runs that book automatically. Every command is the book's own text. Every source archive is hashed before it's used. Every page records how long it took, whether it succeeded, and the hash of its own log. Any deviation from the book is a separate file that says what it changes and why. At the end there is a bundle of receipts anyone can audit.

The result boots. tup 0.1 boots from its own disk to a login prompt under an emulator, with nothing but firmware and the disk, in 20 to 45 seconds depending on the host. It was witnessed on macOS, Ubuntu, and Windows by someone other than me, and what "booted" means is one written definition: a login prompt appears, no kernel panic anywhere, the guest is still alive, and the waiting period elapsed.

I want to say plainly what tup is not. It is witnessed, not verified. It proves what was built, from which bytes, in what order. It proves nothing about the kernel or the C library being correct.` + ASK +
`"Why build a Linux at all?" Next slide. Short version: the verifiers run on a machine, and a bug in the machine's software changed a verdict once.

"What architecture?" 64-bit ARM today. The x86 build is scripted and waits on a permission on the lab machine.`);
  code(s, `page: ch08/glibc
command bytes: the book's own <pre> block, verbatim
source: glibc-2.4x.tar.xz   sha256 8a3f...   checked before use
duration: 1h 12m   exit: 0   log sha256: 4c9e...
deviations: overrides/ch08/glibc.sh (states what it changes and why)`, { x: 0.6, y: 1.35, w: 8.8, h: 1.3, fontSize: 11 });
  M(s, "the shape of one receipt; the real ones are in tup/receipts/", { x: 0.6, y: 2.7, w: 8.8, h: 0.3, fontSize: 10 });
  T(s, "tup 0.1 boots", { x: 0.6, y: 3.2, w: 4.2, h: 0.4, fontSize: 17, bold: true });
  T(s, "From its own disk to a login prompt under QEMU, firmware and disk only, in 20 to 45 seconds. Witnessed on macOS, Ubuntu and Windows by someone other than the author.", { x: 0.6, y: 3.65, w: 4.2, h: 1.4, fontSize: 14 });
  vrule(s, 5.0, 3.2, 1.85);
  T(s, "Witnessed, not verified", { x: 5.2, y: 3.2, w: 4.2, h: 0.4, fontSize: 17, bold: true });
  T(s, "It records what was built, from which bytes, in what order, with what outcome. It proves nothing about the kernel or libc. That distinction is not softened anywhere.", { x: 5.2, y: 3.65, w: 4.2, h: 1.4, fontSize: 14 });
}

// ---------- 17 ----------
{
  const s = slide("Why the machine is part of the project",
`Here's the July and August story I promised, and it's why tup exists.

Before t, I built a training pipeline: an 8 billion parameter model, trained with a method called DPO, where instead of human judges the reward came from unit tests. Everything was preregistered, meaning I wrote down what I'd measure before running it. Result: the trained model did not beat its baseline. Plus half a point, p of 0.51. A clean null.

Then I retrained from the same code and data on a second machine, three times, and got plus 9 to 11 points every time. Same inputs, different answer. The difference turned out to be the verifier. On one machine it ran under Python 3.11, on the other 3.12, and the two versions treat one thing differently: a function that annotates its types without importing the typing module. One version fails that, the other doesn't. The retrained models had learned to emit that one import line, which appears in none of the 918 training examples, and that alone accounted for 48 to 58 percent of the gain.

So roughly half of a highly significant result was the measuring instrument, not the model. That became the paper, and it is the reason for the rest of the project. It's why t has seven verifiers instead of one, and it's why tup exists: if the verdict depends on the machine, then the machine has to be accounted for too, down to which bytes built it.` + ASK +
`"Was the other half real?" Yes: plus 3.7 to 5.6 points, still significant in every retrain, concentrated on two benchmark tasks. The paper says exactly that.

"Where's the paper?" It's in the repository under forge/docs, revision 15, with the full preregistration and every table regenerable from the run ledger.`);
  const rows = [
    [mcell("+0.55 pp", { fontSize: 18, bold: true }), cell("the trained model against its baseline, p = .51: a null")],
    [mcell("+8.8 to +10.9 pp", { fontSize: 18, bold: true }), cell("the same code and data retrained on a second machine, three times")],
    [mcell("48 to 58%", { fontSize: 18, bold: true }), cell("of that gain traced to the verifier's Python version")],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.4, w: 8.8, colW: [2.6, 6.2], rowH: 0.55 }, TBL));
  T(s, [
    { text: "What changed: ", options: { bold: true } },
    { text: "the verifier ran under Python 3.11.9 on one machine and 3.12.10 on the other. One fails a function that annotates types without importing typing; the other passes it. The retrained models learned to emit that one import line, which appears in none of the 918 training pairs.\n\n" },
    { text: "So: ", options: { bold: true } },
    { text: "seven verifiers instead of one, and a machine whose every build step has a receipt." },
  ], { x: 0.6, y: 3.3, w: 8.8, h: 1.8, fontSize: 14 });
}

// ---------- 18 ----------
{
  const s = slide("locallm builds the models; t decides what they learn from",
`locallm is not a model. It's a model maker: it builds a model from random numbers on whatever computer you have, from whatever data you give it. No downloaded weights, no account, nothing leaves the machine. A 3 million parameter model trains in under a minute.

Why that matters for this project: when you build the model from nothing, you control every byte it ever learned from. A downloaded model has already read the internet, good and bad, and you can't take that out. With locallm, the training data is the only thing the model knows, so filtering the data actually filters the model.

That is how the pieces fit. Think of a water filter. locallm is the source: it can learn from anything. t is the filter: only programs that seven proof systems accept, whose twin is caught, that aren't copies, pass through. What comes out the other side is a model built only from clean water. The next slides show that loop running.` + ASK +
`"Why not fine-tune an existing open model instead?" We do both. A small open model fine-tuned on the clean pool is the fast route to beating other small models. locallm is the route where nothing unfiltered was ever in the model at all.

"Can locallm learn things other than code?" Yes, logs, sensor data, records. For non-code data the plan is that t proves the validator, the program that decides what counts as clean for that data, so the filter itself is proven.`);
  box(s, 0.6, 1.6, 2.4, 1.1, "locallm\nbuilds a model from\nrandom numbers", 13);
  box(s, 3.8, 1.6, 2.4, 1.1, "the model writes\nprograms", 13);
  box(s, 7.0, 1.6, 2.4, 1.1, "t keeps only what\nseven verifiers prove", 13);
  arrow(s, 3.0, 2.15, 3.8, 2.15); arrow(s, 6.2, 2.15, 7.0, 2.15);
  s.addShape(pres.shapes.LINE, { x: 8.2, y: 2.7, w: 0.01, h: 0.55, line: { color: INK, width: 1 } });
  s.addShape(pres.shapes.LINE, { x: 1.8, y: 3.25, w: 6.4, h: 0.01, line: { color: INK, width: 1 } });
  s.addShape(pres.shapes.LINE, { x: 1.8, y: 2.7, w: 0.01, h: 0.55, line: { color: INK, width: 1, endArrowType: "triangle" }, flipV: true });
  T(s, "the next model is built only from what passed", { x: 2.2, y: 3.32, w: 5.6, h: 0.35, fontSize: 12, align: "center" });
  rule(s, 0.6, 3.95, 8.8);
  T(s, [{ text: "Why build from scratch: ", options: { bold: true } }, { text: "a downloaded model has already learned from unfiltered data. A model locallm builds knows only what we gave it, so filtering the data filters the model." }], { x: 0.6, y: 4.1, w: 8.8, h: 0.9, fontSize: 15 });
}

// ---------- 19 ----------
{
  const s = slide("Seven verdicts beside the code",
`For anyone to use t, it has to feel like a language, not a research script. So there's an editor story.

There's a language server, which is the standard way editors talk to a language: it gives errors at the exact token, hover text, go to definition, and formatting. It's written in plain Python with no dependencies. On top of it there's a VS Code extension. And the thing that makes it t rather than any other language: the seven verdicts, for the real task and its twin, appear beside the code, with the witness input when a twin is refuted.

An unchanged task costs no verifier run, because verdicts are cached by the hash of the file, so editing is fast.

Status, honestly: it's built, and the walk-through that a second person is supposed to follow from a fresh checkout is written, but no second person has run it yet. That's one of the two things the 1.0 bar requires. A Visual Studio version is planned and needs a Windows machine to build.` + ASK +
`"Does it need all seven verifiers installed?" No. Absent verifiers show as absent. The walk-through is measured with Dafny present and Verus deliberately absent, to show both.`);
  M(s, "max.t", { x: 0.6, y: 1.35, w: 4.4, h: 0.3, fontSize: 10 });
  code(s, `task max(x: int, y: int) returns (r: int)
  ensures r >= x
  ensures r >= y
  ensures r == x or r == y
{
  if x >= y { r := x; }
  else      { r := y; }
}`, { x: 0.6, y: 1.65, w: 4.4, h: 1.9, fontSize: 11 });
  M(s, "twin: collapse-if, witness x = 0, y = 1", { x: 0.6, y: 3.65, w: 4.4, h: 0.3, fontSize: 10 });
  const H = (t) => ({ text: t, options: { fontFace: MONO, fontSize: 9, bold: true, align: "center" } });
  const nm = (t) => ({ text: t, options: { fontFace: MONO, fontSize: 10 } });
  const rows = [[H("verifier"), H("real"), H("twin")]];
  ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"].forEach((k, i) => {
    if (i === 1) rows.push([nm(k), { text: "absent", options: { fontFace: MONO, fontSize: 9, color: ABS, fill: { color: ABSBG }, align: "center" } }, { text: "absent", options: { fontFace: MONO, fontSize: 9, color: ABS, fill: { color: ABSBG }, align: "center" } }]);
    else rows.push([nm(k), { text: "verified", options: { fontFace: MONO, fontSize: 9, color: VER, bold: true, fill: { color: VERBG }, align: "center" } }, { text: "refuted", options: { fontFace: MONO, fontSize: 9, color: REF, bold: true, fill: { color: REFBG }, align: "center" } }]);
  });
  s.addTable(rows, Object.assign({ x: 5.4, y: 1.35, w: 4.0, colW: [1.2, 1.4, 1.4], rowH: 0.31 }, TBL, { margin: 0.03 }));
  rule(s, 0.6, 4.15, 8.8);
  T(s, "Built: a language server, the VS Code extension, a verdict cache, the walk-through. Not yet run by a second person. A Visual Studio version is planned.", { x: 0.6, y: 4.3, w: 8.8, h: 0.8, fontSize: 14 });
}

// ---------- 20 ----------
{
  const s = slide("The bar for 1.0, and what blocks it",
`What does done look like? Two halves, and both have to hold before I tag a 1.0. There are no dates on the roadmap, on purpose. Every item has a finish line a third person can check.

Coverage: at least 82 of the 164 model-written programs lift into t and read all seven, and someone other than me reproduces the table from a clean checkout. Today 57 and 99 respectively.

Usability: a fresh checkout opens a t file in VS Code on Linux and Windows, and in Visual Studio on Windows, with the editor behaviors from the last slide and the seven verdicts, and a second person has repeated the walk-through. Today it's built for VS Code, nobody else has run it, and Visual Studio isn't built.

The blockers for the coverage half are named, not vague. A loop invariant about membership in a growing sequence that Verus, Lean, and F Star don't yet prove. A size bound Frama-C needs from a loop invariant. A bound lemma Rocq needs for recursive helper functions. Then translator rules for function contracts, real numbers, sets, and the remaining array shapes. Each sweep after each fix says the new number.` + ASK +
`"When?" I don't give dates on this project. I name the next hurdle and what it unblocks. The next hurdle is the membership invariant, and it unblocks the largest group of rows in three verifiers at once.`);
  const rows = [
    [head(""), head("The bar"), head("Today")],
    [cell("Coverage", { bold: true }), cell("82 of the 164 model-written programs read all seven, and a second person reproduces the table from a clean checkout."), cell("57 of 164 in all seven; 99 lift; no second person yet")],
    [cell("Usability", { bold: true }), cell("A fresh checkout opens a .t file in VS Code on Linux and Windows, and in Visual Studio, with the seven verdicts; a second person repeats the walk-through."), cell("built for VS Code; no second person yet; Visual Studio not built")],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.4, w: 8.8, colW: [1.4, 4.6, 2.8], rowH: [0.38, 0.95, 0.95] }, TBL, { valign: "top" }));
  T(s, "What blocks the coverage half, by name:", { x: 0.6, y: 3.85, w: 8.8, h: 0.35, fontSize: 14, bold: true });
  T(s, "a membership invariant over a growing sequence that Verus, Lean and F* do not yet prove; a Frama-C size bound that must come from a loop invariant; a Rocq bound lemma for recursive specification functions; then lifter rules for function contracts, real numbers, sets and the remaining array shapes.", { x: 0.6, y: 4.2, w: 8.8, h: 0.95, fontSize: 13 });
}

// ---------- 21 ----------
{
  const s = slide("Eight weeks, 785 commits",
`The whole thing, in order, so you can see how the parts connect.

July 25: first commit. A training pipeline with execution-verified pairs, and the same day, locallm, the from-scratch model. July 28: the verifier gets pinned into every dataset receipt, because a passing receipt should never certify a weakened checker. August: the preregistered null, the replication that wasn't, the paper. August 31: t goes live, with two verifiers in the morning and six by night, and tup 0.1 boots on three hosts the same day. Also the day the repository went public for the first time.

September 2 is the pivot. The training-first plan was set aside and the instrument came first. The refuted purge happened that day. From September 4 to 11, nine language features, each lowered into all seven verifiers, in the order the census ranked them, and the lifter. September 9, the loop measured at 1.5B. September 10, a survey of the field and seven moves chosen from it. September 12 to 15, nine sweeps, 5 to 57.

September 15 and 16, a 27B open model on the lab GPUs writes t for 649 problems, and the filter loop runs for the first time: locallm builds models, t keeps what is proven, locallm rebuilds. September 16 and 17, the whole thing moves to a MacBook, where all seven verifiers reproduce the table exactly, and that rerun catches a bug in my copy check that inflated the first result. I corrected it in the repository the same night.

Every one of those dates is a commit, and every number in this talk is in a file that says which commit produced it.` + ASK +
`"Why the pivot?" Because the July and August result said the grader was the problem. Training a model against a grader you don't trust is measuring noise. So the grader became the project.

"How much of this was AI-assisted?" A lot of the code and drafting, under my direction, and the paper says so in its disclosure. The design decisions, the audits, and every claim are mine, and the point of the whole repository is that you don't have to take anyone's word for a number.`);
  const rows = [
    [mcell("Jul 25"), cell("first commit: the training pipeline with execution-verified pairs, and locallm")],
    [mcell("Jul 28"), cell("the verifier is pinned into every dataset receipt")],
    [mcell("Aug"), cell("a preregistered null; a replication that did not reproduce; the paper")],
    [mcell("Aug 31"), cell("t goes live with six verifiers; tup 0.1 boots on three hosts; the repository goes public")],
    [mcell("Sep 2"), cell("the pivot: instrument first; the refuted purge")],
    [mcell("Sep 4 to 11"), cell("nine language features, each in all seven verifiers; the lifter")],
    [mcell("Sep 12 to 15"), cell("nine sweeps, 5 to 57 of 164; the loop measured at 1.5B")],
    [mcell("Sep 15 to 16"), cell("a 27B model writes t; the filter loop runs: locallm builds, t filters, locallm rebuilds")],
    [mcell("Sep 16 to 17"), cell("seven verifiers reproduce on a MacBook; a copy-check bug found there and corrected")],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.3, w: 8.8, colW: [1.6, 7.2], rowH: 0.34, fontSize: 13 }, TBL));
  T(s, "Every date is a commit. Every number in this talk is in a file that names the commit that produced it.", { x: 0.6, y: 4.75, w: 8.8, h: 0.4, fontSize: 14 });
}


// ---------- 22 filter result ----------
{
  const s = slide("Quality beat quantity: same model, filtered against raw",
`This is the first measurement of the idea, and I'll tell you how it went, including the part where I got it wrong.

The experiment. locallm builds two models with identical settings: 3.2 million parameters, the same training steps, the same seeds, and the same amount of training text, about 95 kilobytes each. The only difference is the water. One learns from raw output a 27B model wrote, right and wrong mixed together. The other learns only from programs t let through. Each model then writes 500 programs, and every program goes through the same filter: it has to parse, follow t's rules, not be a copy of anything the model trained on, and be proven by all seven verifiers with its broken twin caught.

The result: the model built from clean data wrote 29 new clean programs. The model built from raw data wrote 1. Then the loop: take the clean programs, add them to the pool, rebuild the model from scratch, write again. Round one reached 31.

Now the honest part. The first number I recorded was 46 against 3. When the loop was rerun on the MacBook, that run exposed a bug in my copy check: it compared a version line, so programs that were exact copies of training data, written with a different version line, counted as new. Recounted with the fix, 46 against 3 became 29 against 1. The direction held; the effect is about a third smaller. The correction is committed with the recount, next to the original numbers.

And quantity: a third model got ten times as much raw data, 925 kilobytes. It wrote 0 clean programs. One caveat, stated plainly: it trained for the same number of steps, so it saw each example less often. More raw data did not help at this size.

Why this matters: it's the smallest possible version of the thesis. Same model, and filtered data wrote 29 proven programs where the same amount of raw data wrote 1 and ten times the raw data wrote 0.` + ASK +
`"Isn't 29 of 500 tiny?" Yes, it's a 3 million parameter model that trained for under a minute on 95 KB. The comparison is what matters: same everything, 29 against 1.

"Are the 29 interesting programs?" Mostly short, loop-free, and close to something in the training set. That's what a model this small can do. It's why the held-out test on the next slide matters more.

"How do you know the copy check is right now?" It erases everything the verifiers ignore: the name, the version line and the gate. Then it compares the program exactly. Every round in the repository was recounted with it, and the recount is committed.`);
  const rows = [
    [head("each model wrote 500 programs"), head("raw, 925 KB (10x)", { align: "center" }), head("raw, 95 KB", { align: "center" }), head("t-filtered, 95 KB", { align: "center" })],
    [cell("parse as t"), mcell("19", { align: "center" }), mcell("97", { align: "center" }), mcell("375", { align: "center" })],
    [cell("follow t's rules"), mcell("4", { align: "center" }), mcell("7", { align: "center" }), mcell("180", { align: "center" })],
    [cell("clean: new, all seven, twin caught", { bold: true }), mcell("0", { align: "center", bold: true, color: REF }), mcell("1", { align: "center", bold: true, color: REF }), mcell("29", { align: "center", bold: true, color: VER })],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.3, w: 8.8, colW: [3.5, 1.75, 1.75, 1.8], rowH: 0.42 }, TBL));
  M(s, "3.2M parameters, same seeds, same 1,500 steps. t/runs/2026-09-16, recounted in t/runs/2026-09-17", { x: 0.6, y: 3.12, w: 8.8, h: 0.3, fontSize: 9 });
  T(s, [{ text: "Round 1: ", options: { bold: true } }, { text: "rebuild from the clean pool, write again: 31 clean. Rerun on a MacBook: 25." }], { x: 0.6, y: 3.45, w: 8.8, h: 0.4, fontSize: 14 });
  rule(s, 0.6, 3.95, 8.8);
  T(s, [{ text: "Corrected in public: ", options: { bold: true } }, { text: "first recorded as 46 against 3. The MacBook rerun exposed a copy check that let exact copies count as new. Recounted: 29 against 1. The direction held; the effect is a third smaller." }], { x: 0.6, y: 4.1, w: 8.8, h: 0.9, fontSize: 14 });
}

// ---------- 23 held out ----------
{
  const s = slide("What it does not do yet: problems it has never seen",
`The number that actually matters for competing with anyone: give a model a programming problem it never trained on, and see whether its answer is right and proven.

We hold out 232 problems. No training set ever contains them, and that split never changes.

The 27B open model gets 12 of the 232 fully clean: its program passes the problem's tests and is proven by all seven verifiers. It also gets 7 that are proven but wrong: all seven verifiers accept them and they fail the tests. That's a model writing a promise that matches its own wrong code, and the proof faithfully confirms the code keeps the wrong promise. It's exactly why the filter needs the tests too.

The model locallm built from the clean data scores 0. And it's instructive how it fails: 188 of its answers are proven by all seven verifiers, and 151 of them are exact copies of programs it trained on. It ignores the problem and recites something it knows is verified. The verifiers alone would have rewarded that, which is why "clean" means all three at once: tests pass, proven by all seven, and not a copy.

The reason it scores 0 is plain: the clean pool has only 47 worked problem examples. You can't learn to solve problems from 47 examples. So the next step is volume.` + ASK +
`"So does the idea work or not?" On the question it was built to answer first, yes: same size, same data, filtered data builds a model that writes far more proven programs. On solving new problems, not yet, and I'm not going to claim it does.

"What's the plan to get volume?" Many sampled answers per problem from an open model on a home RTX 4080, graded on the lab's CPUs, keeping only answers that pass their tests, are new, and are proven. Then a small open model trained on that pool, a locallm model built from it, and Phi-4-mini as the target, all scored on the same 232.`);
  const rows = [
    [head("232 held-out problems"), head("tests pass", { align: "center" }), head("clean: tests and all seven", { align: "center" }), head("proven but wrong", { align: "center" })],
    [cell("Qwen3.8-27B, open model"), mcell("81", { align: "center" }), mcell("12", { align: "center", bold: true, color: VER }), mcell("7", { align: "center", color: REF })],
    [cell("model locallm built from the clean pool"), mcell("0", { align: "center" }), mcell("0", { align: "center", bold: true, color: REF }), mcell("188", { align: "center", color: REF })],
  ];
  s.addTable(rows, Object.assign({ x: 0.6, y: 1.3, w: 8.8, colW: [3.4, 1.6, 2.2, 1.6], rowH: 0.42 }, TBL));
  M(s, "t/score_heldout.py over t/runs/2026-09-16/loop-data/split-v3.json", { x: 0.6, y: 2.72, w: 8.8, h: 0.3, fontSize: 9 });
  T(s, [{ text: "Why 0: ", options: { bold: true } }, { text: "the clean pool holds only 47 worked problems. The model recites verified programs it memorized (151 exact copies) instead of solving the problem. Verifiers alone would reward that; tests and the copy check do not." }], { x: 0.6, y: 3.05, w: 8.8, h: 0.8, fontSize: 14 });
  rule(s, 0.6, 3.95, 8.8);
  T(s, [{ text: "Next, in order: ", options: { bold: true } }, { text: "many answers per problem on a home RTX 4080, graded on the lab's CPUs; a clean pool in the thousands; then a small open model trained on it, a locallm model built from it, and Phi-4-mini, all scored on the same 232." }], { x: 0.6, y: 4.1, w: 8.8, h: 0.9, fontSize: 14 });
}

// ---------- 24 competing ----------
{
  const s = slide("The opposite of industry, set against its best work",
`The industry's default is quantity. Even the labs that moved toward quality still decide what's good cheaply, because at trillions of tokens it has to be cheap. Here is how the leading work decides what's good, and what changes when you go all the way to proof.

Microsoft's Phi models, starting with "Textbooks Are All You Need," showed small models trained on carefully filtered, textbook-quality data beat much larger ones. Their filter is a model's judgment: an AI grades the quality of the data. t replaces the judge with proofs. A judge can be fooled; seven proof systems agreeing, plus tests, are much harder to fool.

DeepSeek-R1 and reinforcement learning with verifiable rewards train on answers a program can check, for code usually tests. Tests cover the inputs someone thought of, and published work in 2026 shows models learn to game imperfect verifiers. t's reward is a promise proven for every input, with a twin that stops empty promises.

AlphaProof and DeepSeek-Prover use a real proof kernel, Lean, as the reward. That's the closest in spirit, but it's one kernel, and for math competition problems. t uses seven independent kernels, for ordinary programs.

AlphaVerus translates DafnyBench into Verus and filters with a model's critique. The Vericoding benchmark has 12,504 tasks across Dafny, Verus and Lean, but grades each task in one system. t requires the same program to be proven in all seven, and checks its own translator.

Where we're behind, honestly: scale. They train billions of parameters on trillions of words. t is a small language, and our held-out score is 0 today. The bet is that clean data is worth more per parameter, and the size-matched result is the first measurement of that bet.` + ASK +
`"Why would a lab care?" Because the thing they're all fighting is reward hacking and noisy data, and a filter that must fool seven independent proof systems at once is the strongest defense anyone has built for code.

"What would convince you it's wrong?" If a small model trained on the clean pool does no better per parameter on held-out problems than the same model trained on the same amount of test-filtered data. That comparison is planned and preregistered as the next result.`);
  const rows = [
    [head("Work"), head("How it decides what is good"), head("What t does differently")],
    [cell("Llama 3 (Meta), the scaling default"), cell("over 15 trillion tokens; rules of thumb, deduplication, model quality scores"), cell("thousands of examples, each proven")],
    [cell("Phi (Microsoft), \"Textbooks Are All You Need\""), cell("a model judges data quality; filtered and synthetic textbook data"), cell("proofs instead of a judge: seven verifiers plus tests")],
    [cell("DeepSeek-R1, RL with verifiable rewards"), cell("rewards from tests on some inputs; models learn to game weak checkers"), cell("a promise proven for every input; a twin blocks empty promises")],
    [cell("AlphaProof, DeepSeek-Prover"), cell("the Lean kernel accepts the proof; math problems"), cell("seven independent kernels, ordinary programs")],
    [cell("AlphaVerus; Vericoding benchmark"), cell("translated tasks, a model's critique; one system per task"), cell("one program proven in all seven; translator checked")],
  ];
  s.addTable(rows.map((r) => r.map((c) => ({ text: c.text, options: Object.assign({}, c.options, { fontSize: 10.5 }) }))), Object.assign({ x: 0.6, y: 1.2, w: 8.8, colW: [2.3, 3.5, 3.0], rowH: [0.28, 0.46, 0.46, 0.46, 0.4, 0.46], margin: 0.04 }, TBL));
  T(s, [{ text: "Behind on: ", options: { bold: true } }, { text: "scale, a small language, and a held-out score of 0 today. " }, { text: "The bet: ", options: { bold: true } }, { text: "proven data is worth more per parameter. Same model: filtered 29 proven programs, raw 1, ten times the raw data 0." }], { x: 0.6, y: 4.62, w: 8.8, h: 0.55, fontSize: 12 });
}

// ---------- 24 closing ----------
{
  const s = slide("Limits, then questions",
`Let me end with the limits, because the repository states them and I'd rather you hear them from me.

t is small on purpose. No heap, no floating point, no concurrency. Four of the seven translations aren't hardened against hostile input; the committed tasks don't exercise those holes, and the holes are listed rather than hidden. tup is witnessed, not verified, and it's ARM only today. The filter loop works at small scale, and on problems it has never seen the model locallm built still scores 0, because the clean pool is small. And no second person has yet reproduced the main table from a clean checkout, though a second machine has, which is half of what 1.0 means.

If you want to try it: install two or more of the verifiers, read the tutorial, run the two commands on the screen. The first regrades every task in every verifier it finds and rewrites the table. It refuses to give a verdict with fewer than two verifiers present.

The repository is private while its claims are moving, and it's licensed for research and education. If anyone here wants access, ask me. And if anyone wants to be the second person who reproduces the table, that would move the project more than anything I can do alone.

To close where I started: the industry makes AI better by adding more. I'm trying to make it better by letting in only what can be proven, and measuring whether that wins per parameter. So far, at small scale, it does. Questions.` + ASK +
`GLOSSARY, in case a term comes up:
- task: a t program: signature, requires, ensures, loop invariants, body.
- verifier / kernel: one of the seven proof systems. "Kernel" is the repository's word for the same thing.
- lowering: t's translation into one verifier's language.
- twin: the deliberately broken copy of a task; the specification is untouched.
- witness: the concrete input on which the real program and the twin differ.
- certificate: the small proof, built from the witness, that the specification fails at that input.
- verified / refuted: a cell that counts. Real proved, twin proved wrong.
- unproved: the verifier could not prove it. Not evidence either way.
- abstain: the verifier declined to give a verdict on this shape of program.
- vacuous / decorative: a specification that cannot tell the real from the twin.
- unsound: a verifier proved a twin the interpreter says is wrong; a verifier bug signal.
- matrix: the agreement table over the 34 committed tasks.
- sweep: the same table over the lifted DafnyBench tasks, regenerated from scratch.
- lifter: the translator from Dafny programs into t.
- DafnyBench: 785 public Dafny programs with specifications. MBPP-DFY: the 164 of them a language model wrote from MBPP problems.
- MBPP, HumanEval, APPS, CodeContests: public sets of programming problems with tests.
- fragment: the set of features t has today. census: a count of which programs of a corpus fit inside it.
- conformance suite: 66 probe tasks with a declared expected verdict per verifier; tests the instrument.
- receipt: tup's record of one build step: command bytes, source hash, duration, exit status, log hash.
- DPO: direct preference optimization, a way to train a model from pairs of better and worse answers.
- preregistered: what will be measured, and what counts as success, written down before the run.`);
  T(s, "t is small on purpose: no heap, no floats, no concurrency.\n\nFour translations are not hardened against hostile input; the holes are listed.\n\ntup is witnessed, not verified, and arm64 only today.\n\nThe filter works at small scale; on unseen problems it scores 0 so far.\n\nA second machine reproduced the table; a second person has not yet.", { x: 0.6, y: 1.3, w: 5.5, h: 3.0, fontSize: 13 });
  vrule(s, 6.3, 1.35, 2.2);
  T(s, "Try it", { x: 6.5, y: 1.35, w: 2.9, h: 0.35, fontSize: 15, bold: true });
  code(s, "cd t\npython3 run_par.py --jobs 8\nbash reproduce.sh --tests", { x: 6.5, y: 1.75, w: 2.9, h: 0.95, fontSize: 11 });
  T(s, "Private while the claims move. Research and education use. Ask me for access.", { x: 6.5, y: 2.8, w: 2.9, h: 0.8, fontSize: 12 });
  rule(s, 0.6, 4.4, 8.8);
  T(s, "Quality over quantity, proven. Questions?", { x: 0.6, y: 4.5, w: 8.8, h: 0.6, fontSize: 26, bold: true });
}

if (n !== TOTAL) throw new Error(`slide count ${n} != ${TOTAL}`);
const out = process.argv[2] || "t-and-tup-talk.pptx";
pres.writeFile({ fileName: out }).then(() => {
  fs.writeFileSync("script.json", JSON.stringify(scriptOut, null, 2));
  console.log("wrote", out, "slides:", n);
});
