---
doc: checklist
status: approved
---

# Build Checklist

Build mode: fast

The commissioning brief asked for the finished proof of concept in one session, with tests and a browser check as the verification. Fast mode: implement and mechanically verify each slice, and use the done line (`pip install -e .`, wrap a command, see it on the dashboard) as the hands-on checkpoint.

## Slices

- [ ] **1. Wrap a command and read the ledger line back**
  Becomes usable: `runledger -- <command>` runs the command, keeps its exit code, stores the log tail and at least one GPU sample (measured or labeled demo), and `runledger list` shows the run.
  Why now: This is the kernel. The page and the webhook have nothing to show until a real wrap exists. Scaffolding (package, SQLite, sampler) lands inside this slice.
  PRD ref: `prd.md > Wrap a command`, `prd.md > Sample the GPU`, `prd.md > Terminal list and show`
  Spec ref: `spec.md > CLI`, `spec.md > Runner`, `spec.md > Sampler`, `spec.md > Store`
  Build: Package the console script. Add SQLite runs and samples. Stream the child, sample nvidia-smi or the demo sampler, finish the row, print the summary, return the child's exit code. `list` and `show` read it back.
  Verify (mechanical): `pytest tests/test_sampler.py tests/test_runner.py tests/test_cli.py` — short command exits 0 with its stdout in the tail and at least one sample; exit 2 is preserved; missing command is exit 127; nvidia CSV with `[N/A]` parses.
  Learner check: Run `runledger -- python -c "print('runledger-ok')"` and confirm the print, the summary line, and `runledger list`.
  Commit: `Record a wrapped command in the local ledger`

- [ ] **2. The local page shows the run and its curve**
  Becomes usable: `runledger serve` opens a localhost page that lists the wrapped run and charts its samples, with an empty state before any run exists.
  Why now: The video's "oh" moment is the curve on the page. It should land as soon as a run exists, before notifications.
  PRD ref: `prd.md > Local dashboard`, `prd.md > Look and Feel`
  Spec ref: `spec.md > Local page`, `spec.md > Look and Feel`
  Build: Stdlib server, one offline HTML file, list plus detail chart, poll while a run is in progress, hash keeps the open run.
  Verify (mechanical): `pytest tests/test_server.py` — the runs API returns the wrapped command, and the HTML has no external script or stylesheet.
  Learner check: `runledger serve`, open the URL, click the run, see the chart and the log tail.
  Commit: `Show runs and GPU curves on the local dashboard`

- [ ] **3. Ping a bot when the job ends**
  Becomes usable: A saved URL receives one POST on finish or crash, in generic, WeCom, DingTalk, or Feishu shape. The child exit code does not change if the POST fails.
  Why now: Notification is the other half of the kernel (the phone rings), and it needs a finished run to attach to.
  PRD ref: `prd.md > Webhook`
  Spec ref: `spec.md > Webhook`
  Build: Payload builders, urllib POST, `runledger notify`, settings form and test ping on the page.
  Verify (mechanical): `pytest tests/test_webhook.py tests/test_runner.py` — WeCom body on a non-zero exit, no POST when notify is crash-only and the child succeeds, DingTalk and Feishu shapes.
  Learner check: Point notify at a request bin or a bot, crash a command, see one message.
  Commit: `Notify WeCom, DingTalk, Feishu, or a generic webhook`

- [ ] **4. Demo examples, tests for the done line, and the written deliverables**
  Becomes usable: `runledger demo` fills the page with labeled fake history without deleting real wraps. README, license, demo script, and submission draft match the running tool.
  Why now: The page has to be recordable on a machine with no GPU, and the hackathon form needs the written pieces. They sit on top of a loop that already works.
  PRD ref: `prd.md > Demo examples`, `prd.md > What We're Building`
  Spec ref: `spec.md > Demo examples`, `spec.md > Where It Runs and How Someone Tries It`
  Build: Seed four shaped runs. Cover the install-and-wrap done line. Write README, MIT LICENSE, DEMO.md, SUBMISSION.md. Capture dashboard screenshots.
  Verify (mechanical): `pytest` and `pip install -e .` then `runledger -- python -c "print('runledger-ok')"` with the dashboard API showing that run.
  Learner check: Open the page with demo data and with a real wrap. Confirm the simulated badge is visible on seeded runs and that the real wrap's exit code matches.
  Commit: `Add demo history, docs, and the hackathon write-up`

## Hands-on Checkpoints

- [ ] Early usable behavior explored — after slice 2, the wrapped run is visible on the dashboard
- [ ] Final kick-the-tires exploration and feedback completed

## Final Review

- [ ] Final review complete — feedback resolved and learner confirms ready to ship

## Code Tour and App Map

- [ ] Learning activity complete — guided route, focused alternative, prior practice connected, or brief recap
- [ ] Optional edit and transfer reflection addressed — offered/declined/already covered/not applicable as appropriate
- [ ] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: not started
Route and stops: not started
Edit outcome: not started
Reflection: not started
Activity mode: not started

## Revisions
