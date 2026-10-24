# Cohere Labs Catalyst Grant: milestone updates

Grant accepted 2026-10-22, $1000 API credit, account jonhhjackson@gmail.com, expires 2027-10-22.
Rule: one dated entry per milestone, numbers first, then a short draft the user sends to grants@cohere.com.
Cohere Labs gave written permission on 2026-10-24 to train dawnr on Cohere outputs that pass our checks. That is
the grant's main use: checked specifications and repair examples for the next dawnr model. The earlier entries
below describe the scope before that permission. Updates are due at every incremental release and at completion;
the generated text and training rows stay private.

## 2026-10-24 Milestone 0: credit live, first lane open

- Production key created, every call priced and logged, hard stop at $950.
- Lane 1 open: Cohere Rerank 3.5 over the dawnr paper library (5500 formal-methods and ML papers). One search reranks the top 100 full-text hits for $0.002.
- Spend so far: $0.004.

Draft to grants@cohere.com:

Hi Brittawnya. Thanks again for the grant. The credit is live and we opened the first lane today. We are using Rerank 3.5 over our library of about 5500 formal verification and ML papers so our local model finds the right prior work faster. Next we add Command A as a second judge beside our existing grader on verified-code repair tasks. We will send numbers as each piece lands.

## 2026-10-24 Milestone 1: dawnr 6.0 planned, scaffold on main

- The five model lines trained or prepared since dawnr v5 fold into one release, dawnr 6.0. A model enters it only by
  one protocol: two training seeds, three decodes each, read paired per problem on 240 development problems, with the
  specification gate's precision, the 33 given specifications and the 182 held-out problems read beside it.
- The 6.0 candidate trains on v5's rows plus specifications written by two open teachers and kept only after a strict
  check against each problem's reference solution, plus 525 repair traces.
- Cohere's part: Rerank 3.5 over the paper library for the research behind each step. No Cohere output is training data.
- Spend so far: under one cent.

Draft to grants@cohere.com:

Hi Brittawnya. Quick update on the grant. We planned dawnr 6.0 today and put the scaffold on main. Five model lines
we trained since our last release now fold into one release with one strict way in: two training seeds, three
decodes each, and a paired reading on 240 problems. Rerank is already in our research search over about 5500 papers.
Next update comes when the first candidate is read under that protocol.

## 2026-10-24: written permission to use Cohere outputs as training data

Asked by email whether Command outputs, kept only when our provers and reference checks pass, may become training
data for the open-source dawnr model. Cohere Labs replied the same day: yes, dawnr is not a model that competes with
Cohere's, on the condition that we send an update at every incremental release, and a report when the work is done.
The reply is kept in the grant email thread. Every Cohere-written row is labelled by source in the release's data
card, which cites this permission.

## 2026-10-24: release dawnr 6.0.0 (the first versioned release)

- dawnr is now released as dawnr MAJOR.MINOR.PATCH. 6.0.0 carries the October 5 model unchanged, with the application
  at its tag, versioned installs, and a public correction of how the October 22 readings were compared.
- The 6.1.0 candidate is training on the desktop: the October 5 model's own audited rows plus strictly checked
  specifications and repair examples (6,727 rows, two seeds).
- Cohere's part so far: Rerank 3.5 in the research search, and a head-to-head pilot of Command A Reasoning and
  Command A+ as teachers on 50 problems the model fails. The better one by checked specifications per dollar writes
  for the remaining failed problems, and the survivors go into the 6.2.0 candidate.
- Released 2026-10-24 21:15Z: https://github.com/trestoncuzzort/dawnr/releases/tag/v6.0.0 (the latest release; the
  installer takes it by default). The laptop check: every README command does its work; one bug it found (`dawnr do`
  stopping when a folder listing outgrew the model's context) is fixed in this release.
- Spend so far (the grant ledger, conservative prices): about $75, nearly all of it the teacher pilots.

Draft to Brittawnya (send when the release page is live):

Hi Brittawnya. Update on dawnr like you asked. We just put out dawnr 6.0.0, our first versioned release:
https://github.com/trestoncuzzort/dawnr/releases/tag/v6.0.0. It keeps the same model as before but cleans up the
installs, fixes a bug our laptop test found, and corrects a measurement mistake we found in our own records. The next
model is training now. We also started using Command A as a teacher. It writes specs for problems our model gets
wrong and our provers keep only the ones that check out. Next update comes with 6.1.0.

## 2026-10-24: release dawnr 6.0.1

- An application release on the same model: `dawnr ask` about twice as fast from a cold start on the laptop the release
  is checked on (the provers stop at an answer all seven prove), and all seven provers found however dawnr is started.
- The Cohere teacher moved to GitHub's machines: Cohere's model writes, our checks run around it in parallel jobs, each
  with its own budget on the grant ledger. Command A Reasoning and Command A+ turned out to be limited to 20 requests
  a minute and 1,000 calls a month, so the full run uses Command A.

Draft to Brittawnya (send when 6.0.1 is live):

Hi Brittawnya. Small update. dawnr 6.0.1 is out. Same model as 6.0.0 but asking it for a checked function is about
twice as fast now. We also moved our Command A runs to cloud machines so they run in parallel. One question if you know:
Command A Reasoning solved more of the pilot's problems, while Command A kept more per dollar. Reasoning is capped
at 20 requests a minute and 1,000 calls a month.
Is there a way to raise that for the grant?
