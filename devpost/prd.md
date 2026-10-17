---
doc: prd
status: approved
---

# Run Ledger — Product Requirements

A local flight recorder for one developer and one GPU. They prefix a command with `runledger --`, and a page on the same machine keeps the ending: time, exit code, log tail, and a VRAM / power / temperature / utilization curve. An optional webhook pings WeCom, DingTalk, Feishu, or any generic endpoint when the job finishes or crashes.

Source: `scope.md > The Unique Kernel`, `scope.md > Who It's For`, `scope.md > The Core Loop`.

## The Core Journey

1. They install Run Ledger into the environment they already use for training (`pip install -e .` from a checkout, or the same install on Windows with `py -m pip`).
2. They start the job they were already going to run, with a prefix: `runledger -- python train_lora.py --rank 16`. The program's own output still scrolls in that terminal. If nvidia-smi is not available, one stderr line says the curve will be simulated and labeled.
3. They can leave. When the process exits, the same terminal prints one summary line: run id, success or failure, exit code, duration, and peak VRAM when a sample exists. The process's exit code is the child's exit code, so a shell script still fails when the train fails.
4. If a webhook URL is saved and this ending matches the chosen notify rule (finish, crash, or both), Run Ledger POSTs one message. If the POST fails, the summary line still reports the child's exit code. The page shows that the ping failed.
5. They run `runledger serve` and open the URL it prints (localhost only). The run is at the top of the list. They open it and see peak VRAM, power, temperature, and utilization, a chart of the samples, and the stdout and stderr tails.
6. They close the terminal and the browser. Later, `runledger serve` shows the same run. Nothing was uploaded anywhere unless they saved a webhook URL.
7. On a computer with no NVIDIA driver, steps 2 through 6 still work. The page says the curve is from the demo sampler. The exit code and log tail are the real command's. `runledger demo` can also drop a few labeled example runs (a long train, a ComfyUI-like job, a local LLM, and an out-of-memory crash) so a recording is not an empty page. Those examples are marked simulated, not as measurements.

Source: `scope.md > The Core Loop`, `scope.md > What "Working" Looks Like`.

## Screens and Layout

Two surfaces. No accounts, no second website.

**Terminal.** `runledger` with no command prints help. The wrap form is `runledger -- <command> [args...]`. Also: `list`, `show <id>`, `serve`, `notify`, and `demo`.

**Local page, one screen.** A header (name, one-line purpose, whether this machine is measuring with nvidia-smi or using the demo sampler). A list of runs down the side: status, command, duration, peak VRAM. The rest of the screen is the open run: command, status, exit code, times, four peak numbers, a chart with VRAM / power / temperature / utilization (and an overlay), then the log tail with a stdout / stderr switch. The webhook URL, format, and notify rule sit on the page so they can be set without remembering a flag. Narrow windows stack the list above the run.

The open run is reflected in the URL hash (`#12`) so a refresh stays put.

## Look and Feel

The brief did not name a palette. Assumption for the proof, so the page does not fall back to a generic purple gradient: a dark bench and warm paper type. System serif for the name and the big numbers (Palatino / Iowan class), system mono for commands and logs, system sans for labels. Amber for a selected or still-running run, green for success, red for failure. Four chart series stay visually distinct (memory, watts, degrees, utilization). No web fonts, no CDN, no images loaded from the network. The page has to work with the wifi off.

Bot formats are labeled in English and with the names a mainland China user looks for: WeCom (企业微信), DingTalk (钉钉), Feishu (飞书).

Copy is short and concrete. Empty state tells them the exact prefix to type. It does not welcome them to the app.

Source: `scope.md > Inspiration & Identity`.

## Features and Behavior

### Wrap a command

They run `runledger -- <command> [args...]` from the directory of the job. Arguments after `--` are the program and its arguments, not a shell string. The child's stdout and stderr stream to the terminal as they are produced and are also stored as a tail. When the child exits, Run Ledger prints one summary line and exits with the child's code.

A missing program is a failed run with exit code 127 and a clear "command not found" line, not a Python traceback as the only result.

Ctrl+C stops the child, records the run as interrupted, and exits 130. That counts as a crash for the webhook.

- As the solo developer, I want to prefix the command I already run so that I do not have to launch jobs from a different app.
  - [ ] `runledger -- python -c "print('runledger-ok')"` prints `runledger-ok`, then a summary line, and the process exit code is 0.
  - [ ] A child that exits 2 makes `runledger` exit 2, and the stored run says failed.
  - [ ] A command name that does not exist is stored as failed, exit 127, with "command not found" in the stderr tail.
  - [ ] The last lines of a long printout are kept, including the final line. The stored tail is not the entire log.

### Sample the GPU

Every few seconds while the child is running, and once at the end, Run Ledger records VRAM used, VRAM total, power, temperature, and utilization. The default gap is 3 seconds. `--interval` changes it.

When `nvidia-smi` returns data, the run is marked measured. When it is missing or returns nothing, the run is marked demo sampler. The demo curve is shaped like a job warming up (memory and utilization rise, temperature lags). It is labeled in the terminal and on the page. Demo numbers are never stored under the measured label.

A short command still gets at least one sample, so the page is not a blank chart.

- As the solo developer, I want the curve that nvidia-smi would have shown me if I had been watching.
  - [ ] A finished run has one or more samples with VRAM, power, temperature, and utilization fields.
  - [ ] With nvidia-smi absent, the run's sampler is `demo`, and the page copy says the curve is simulated.
  - [ ] A parsed nvidia-smi row that contains `[N/A]` for power does not crash the sampler; power is empty and the other fields remain.

### Local dashboard

`runledger serve` prints a localhost URL and serves the page from this machine. The list is newest first. Opening a run shows the command, status, exit code, start and end, duration, working directory, sampler label, the four peaks, the chart, and the log tails. A running job updates on the page without a manual reload. Refreshing later still shows finished runs.

Empty list: a specific empty state and the wrap command, not a blank table.

- As the solo developer, I want to open one page after a job and see whether it died and what the card was doing.
  - [ ] After a wrapped command, the runs API includes that command and its exit code, and the page HTML is served from the same server with no external stylesheet or script.
  - [ ] Opening a run shows its samples on a chart and the log tail.
  - [ ] Before any run exists, the page shows the empty state and the wrap command.

### Webhook

They can save a URL, a format (`generic`, `wecom`, `dingtalk`, `feishu`), and when to send (`both`, `finish`, `crash`). Default is both, once a URL is set. No URL means no network call.

Generic is a JSON body with the event name, command, status, exit code, duration, and peaks. WeCom is a markdown bot body (`msgtype: markdown`). DingTalk is a markdown bot body with a title that includes "Run Ledger" (many DingTalk bots require a keyword). Feishu is an interactive card (`msg_type: interactive`). A test ping from the page sends one sample message without creating a run.

- As the solo developer, I want a message in the bot I already have when an overnight job ends or crashes.
  - [ ] A failed run with format `wecom` POSTs a body whose `msgtype` is `markdown` and whose text includes the exit code.
  - [ ] Formats `dingtalk` and `feishu` produce their bot shapes, and `generic` includes `run.finished` or `run.crashed`.
  - [ ] `notify_on: crash` does not POST when the child exits 0.
  - [ ] A refused POST still leaves the child's exit code unchanged, and the run records that the ping failed.

### Demo examples

`runledger demo` inserts a handful of finished example runs and replaces any previous examples. They are visually distinct (a long steady train, a sawtooth image-generation job, a spiky local LLM, an out-of-memory crash). The page badges them as simulated examples. The command does not delete real wrapped runs.

- [ ] After `runledger demo`, the list contains the example runs, each marked as simulated, and a previously wrapped run is still there.

### Terminal list and show

`runledger list` prints recent runs. `runledger show <id>` prints one run's summary and where the tail begins. This is how they check a result without opening the browser.

- [ ] `list` includes a run that was just wrapped, with its status and exit code.

## States and Boundaries

- **First use** — no database yet. The first wrap creates it. The page, opened before any wrap, shows the empty state, not an error.
- **Running** — status `running`, end time empty, list shows it as in progress, page keeps updating.
- **Success** — exit code 0.
- **Failed** — exit code non-zero, including 127 for a missing program.
- **Interrupted** — Ctrl+C. Status `interrupted`, treated as a crash for notifications.
- **Measured vs demo vs example** — measured means nvidia-smi; demo sampler means a real command with a simulated curve; simulated example means `runledger demo`. The page says which one you are looking at.
- **Webhook unset** — no request is made. The page says nothing leaves the machine unless a URL is saved.
- **Webhook set but unreachable** — the run still finishes; the page shows the ping failure.
- **Persistence** — runs and samples survive a restart of the terminal and of `runledger serve`. They live in one SQLite file under the home directory (`.runledger/runs.sqlite`), overridable with `--db` or `RUNLEDGER_DB`.
- **Who can see it** — the page binds to 127.0.0.1. There is no login. Anyone who can run commands as this user can read the ledger, which is the same trust boundary as the terminal scrollback.
- **Stdin** — not forwarded. These are long jobs, not interactive prompts.
- **Log tail** — the last part of the output, not the full file. Assumption: 160 lines is enough to see the crash. Full logs are deferred.

## Product Decisions

- Prefix syntax `runledger -- <command>` — from the brief, so any command can be wrapped without a shell quoting puzzle.
- Child exit code is Run Ledger's exit code — assumed from "records exit code"; a wrapper that swallows failure would break scripts. Called out because the brief did not say it in those words.
- Notify on both finish and crash when a URL is set — the brief says "on finish or crash". The page can narrow that to one of the two.
- Sample interval default 3 seconds — the brief says "every few seconds". Assumption, overridable.
- Tail of 160 lines — the brief says "tail", not the whole log. Assumption.
- Database path `~/.runledger/runs.sqlite` — not specified. Assumption, so the CLI and the page share one file no matter which directory they start in.
- Page binds to localhost — the brief says a local page and no internet required. Assumption that it is not exposed on the LAN by default.
- Visual direction (dark bench, warm paper, system fonts) — not specified. Assumption, recorded here so the build does not invent a second look later.
- Demo examples via `runledger demo` — the brief requires a demo sampler when nvidia-smi is missing. Separate labeled example history is included so a recording can show a full curve, and it is badged as fake. Assumption that a single short command's curve is not enough to judge the page.

## What We're Building

The journey above: wrap, sample, persist, show on one local page, optional webhook in four formats, labeled demo behavior, tests, and the docs the hackathon asks for.

## Deferred From the POC

- Full log files on disk. The tail proves the crash was an OOM; the whole log can wait.
- Watt-hour cost. Peaks are enough for the video.
- More than one computer in one ledger.
- A ComfyUI custom node.

## Possible Later Enhancements

A field for watt-hours, computed from the power samples, would tell this person what an overnight train drew. A single folder of full logs next to the SQLite file would answer "what happened at step 400" without changing the wrap habit.

## Non-Goals

- Cloud accounts, hosted sync, and multi-user access. They contradict `scope.md > Explicitly Cut` and the one-machine kernel.
- Prometheus, Grafana, or a training-framework plugin. Same cut.
- Replacing nvidia-smi as a driver tool, or controlling the GPU. Run Ledger only reads.
- Shipping a notification service of our own. The user brings the URL.

## Open Questions

None that block the spec. Interval, tail length, database path, bind address, and palette are assumptions above. If a later change contradicts one of them, update this list rather than silently drifting.
