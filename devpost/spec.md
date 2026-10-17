---
doc: spec
status: approved
---

# Run Ledger — Technical Spec

## How This Works, In Plain Language

Run Ledger is three pieces on one computer. No account, no extra server to install.

The wrapper starts the command you put after `runledger --`, lets that command print to the terminal as usual, and writes down when it started, when it ended, the exit code, and the last lines of output.

The sampler, every few seconds, asks `nvidia-smi` how full the GPU memory is, how many watts it is drawing, how hot it is, and how busy it is. Those readings go in the same notebook. If `nvidia-smi` is not there or does not answer, the sampler writes a simulated curve instead and labels it, so a demo on a laptop is honest.

The page and the optional ping read that notebook. `runledger serve` is a small local web server. The notebook is a SQLite file. If you saved a bot URL, the wrapper sends one HTTP POST when the job finishes or crashes, in the shape that bot expects.

This shape instead of a web framework and a hosted database: the person is on a single Windows machine that should be busy training. Python's standard library already has processes, SQLite, and a small HTTP server. Another service would be something else to install.

## The Core Journey Through the System

PRD ref: `prd.md > The Core Journey`.

1. `pip install -e .` puts the `runledger` command on PATH. No runtime packages are downloaded for the install beyond the build tool.
2. `runledger -- python train_lora.py` lands in `cli.py`, which starts `runner.execute` with the arguments after `--`.
3. The runner opens the SQLite file (creating it on first use), inserts a `running` row, and starts the child process with stdout and stderr piped. Two reader threads copy those pipes to the terminal and into a tail buffer.
4. A sampler thread calls `sampler.read_once`. That tries `nvidia-smi`. If that returns GPU rows, they are stored as measured samples. If not, `sampler.demo_gpus` builds one labeled demo GPU reading. Rows go into the `samples` table, and the live tail is written onto the run so the page can show a job that is still going.
5. When the child exits, the runner stores the final tail, exit code, status (`success`, `failed`, or `interrupted`), and peak values, then calls `webhook.maybe_notify`. That reads the saved URL and format and, if the event matches, POSTs. The HTTP result is stored on the run. The wrapper then exits with the child's code.
6. `runledger serve` starts `server.py`, which reads the same SQLite file and returns the page plus JSON. The page's script draws the list and the chart. Nothing is fetched from the internet.
7. A later `runledger serve` reads the same file. Closing the terminal does not delete it.
8. On a machine with no `nvidia-smi`, step 4 takes the demo branch and the page says so. `runledger demo` inserts extra rows with `origin = seed` that the page badges as simulated examples.

## Stack

- Python 3.10+ (developed on 3.12). Standard library only at runtime: `sqlite3`, `subprocess`, `http.server`, `urllib`, `argparse`, `pathlib`, `json`, `threading`, `csv`. https://docs.python.org/3/library/index.html
- Packaging: setuptools via `pyproject.toml`. https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html
- Tests: pytest, a dev dependency, not installed for someone who only wants the tool. https://docs.pytest.org/
- GPU readings: the `nvidia-smi` query CLI already installed with the NVIDIA driver. https://developer.nvidia.com/nvidia-system-management-interface
- No web framework, no frontend build, no chart library, no CDN.

Rationale: the brief asks for minimal dependencies and a local page. Zero runtime dependencies is the tradeoff they get — the chart is hand-drawn SVG, and the HTTP server is the standard library. That is enough for one user on localhost, and it avoids a Node toolchain on the training machine.

## Where It Runs and How Someone Tries It

Local command line and a browser tab pointed at localhost. Windows and Linux. No API keys.

```bash
python -m pip install -e ".[dev]"
runledger -- python -c "print('runledger-ok')"
runledger serve
```

Open the URL the serve command prints (default `http://127.0.0.1:8765`).

Windows, from the repo, if `python` is the `py` launcher:

```bat
py -m pip install -e ".[dev]"
runledger -- python -c "print('runledger-ok')"
runledger serve
```

The hackathon submission needs a short demo video and a public Git repository. Deployment is not required and is not part of this proof. Record the terminal command and the local page.

Optional environment variable: `RUNLEDGER_DB`, a path to the SQLite file. Default is `~/.runledger/runs.sqlite`.

## Look and Feel

Carried from `prd.md > Look and Feel` and `scope.md > Inspiration & Identity`.

The page is one HTML file served by `server.py`, with CSS and the chart script inlined. Colors are a dark green-black bench (`#121614`), warm paper text (`#efe7d6`), amber (`#e2a04a`) for selection and in-progress, green (`#7dcaa0`) for success, red (`#e07a62`) for failure. Chart series: VRAM blue, power amber, temperature red, utilization green.

Fonts are system stacks only: a serif (Palatino / Iowan / Georgia) for the name and peak numbers, a sans for UI labels, a mono stack (Cascadia, ui-monospace) for commands and logs. On a Chinese Windows install, the sans stack includes Microsoft YaHei / PingFang so the bot names render.

No external font or image requests. Density is a tool, not a marketing page: the list stays compact, the open run gets the chart and the log.

## Components

### CLI

`cli.py` parses `serve`, `list`, `show`, `notify`, `demo`, and `--` (wrap). Global `--db` and `--interval` apply to the wrap. It is the only place that reads `sys.argv`.

PRD ref: `prd.md > Wrap a command`, `prd.md > Terminal list and show`.

### Runner

`runner.py` owns one wrapped process: insert the run, stream pipes, sample on a thread, finish the row, notify, return the exit code. Stdin is `DEVNULL`. If `PYTHONUNBUFFERED` is unset, the child gets `PYTHONUNBUFFERED=1` so Python log lines show up before the process exits. Other programs may still buffer when stdout is a pipe; that limit is documented, not papered over.

PRD ref: `prd.md > Wrap a command`, `prd.md > Sample the GPU`.

### Sampler

`sampler.py` turns one `nvidia-smi --query-gpu=... --format=csv` snapshot into readings, or builds the demo reading. `[N/A]` and `[Not Supported]` become empty numbers, not errors. The demo GPU is named so a chart title cannot be mistaken for a real card.

PRD ref: `prd.md > Sample the GPU`.

### Store

`db.py` is the only module that writes SQL. One SQLite file, WAL mode, foreign keys on. Tables: `runs`, `samples`, `settings`.

PRD ref: `prd.md > States and Boundaries`.

### Webhook

`webhook.py` builds the four JSON bodies and POSTs them with `urllib`. It does not raise into the runner. Formats and the official bot docs:

- Generic: Run Ledger's own JSON (`event`, command, status, exit code, duration, peaks, short tails).
- WeCom markdown: https://developer.work.weixin.qq.com/document/path/91770
- DingTalk markdown: https://open.dingtalk.com/document/robots/custom-robot-access
- Feishu interactive card: https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot

PRD ref: `prd.md > Webhook`.

### Local page

`server.py` is a `ThreadingHTTPServer` on 127.0.0.1. It serves `dashboard.html` and the JSON the page fetches (`/api/runs`, `/api/runs/<id>`, `/api/meta`, `/api/settings`, `/api/notify/test`). `dashboard.html` draws the list, the SVG chart, the log tails, and the webhook form. It polls every two seconds while a run is still going.

PRD ref: `prd.md > Local dashboard`, `prd.md > Look and Feel`.

### Demo examples

`demo_data.py` deletes previous `origin = seed` rows and inserts four finished runs with hand-shaped curves and log tails. It never deletes `origin = wrap`.

PRD ref: `prd.md > Demo examples`.

## Data Model

SQLite file at `~/.runledger/runs.sqlite` unless `--db` or `RUNLEDGER_DB` is set. Created on first use. Survives restarts.

`runs`

- `id` integer primary key
- `command` text, the display form of the argv
- `argv_json` text
- `cwd` text
- `started_at`, `ended_at` ISO 8601 UTC text
- `exit_code` integer, null while running
- `status` text: `running`, `success`, `failed`, `interrupted`
- `stdout_tail`, `stderr_tail` text
- `sampler` text: `nvidia` or `demo`
- `sampler_note` text
- `origin` text: `wrap` or `seed`
- `peak_vram_mb`, `peak_power_w`, `peak_temp_c`, `peak_util_pct` real, null if no numeric samples
- `gpu_name` text
- `webhook_status`, `webhook_error` text, null if no ping was attempted

`samples`

- `id`, `run_id` (cascade delete), `ts` ISO text
- `gpu_index`, `gpu_name`
- `vram_used_mb`, `vram_total_mb`, `power_w`, `temp_c`, `util_pct` (null when the driver had no number)

`settings`

- `webhook_url` text, default empty
- `webhook_format` text: `generic`, `wecom`, `dingtalk`, `feishu`
- `notify_on` text: `both`, `finish`, `crash`

Peaks are recomputed from samples when a sample is written, so the list can show a live peak without reading every point.

## File Structure

```
.
├── pyproject.toml          # package metadata, console script, pytest path
├── README.md               # English install and usage
├── LICENSE                 # MIT
├── DEMO.md                 # 2-minute video script
├── SUBMISSION.md           # draft Devpost write-up
├── skills-lock.json        # Skill Pack pin from `npx skills add`
├── docs/
│   ├── skill-pack-usage.md # how the Skill Pack was used
│   └── screenshots/        # dashboard captures for the README
├── src/runledger/
│   ├── __init__.py
│   ├── __main__.py         # python -m runledger
│   ├── cli.py
│   ├── runner.py
│   ├── sampler.py
│   ├── db.py
│   ├── webhook.py
│   ├── server.py
│   ├── demo_data.py
│   └── dashboard.html
├── tests/
│   ├── test_sampler.py
│   ├── test_webhook.py
│   ├── test_runner.py
│   ├── test_server.py
│   └── test_cli.py
├── devpost/
│   ├── scope.md
│   ├── prd.md
│   ├── spec.md
│   ├── checklist.md
│   ├── app-map.html
│   └── learner-profile.md  # gitignored personal context
└── .agents/skills/         # Devpost Learn Skill Pack
```

## External Services and Dependencies

None are required to record a run or open the page.

Optional, only when the user sets a URL:

- WeCom group bot, POST JSON, no key inside Run Ledger (the key is in the URL the user pastes). Docs linked under Webhook. No fee from this project. Their bot may rate-limit; one POST per run is the whole use.
- DingTalk custom robot, same. The message includes the words "Run Ledger" because many bots require a keyword. Docs linked under Webhook.
- Feishu custom bot, interactive card. Docs linked under Webhook.
- Any other HTTPS endpoint receives the generic JSON. The user is responsible for that URL.

nvidia-smi is a local executable, not a network service. If it is missing, nothing is contacted.

No API keys ship in the repo. `.env.example` is unnecessary; `RUNLEDGER_DB` is documented in the README.

## Important Failure Modes

- **nvidia-smi missing or empty** → the run is stored with `sampler = demo`, the terminal says so once, and the page says the curve is simulated. Exit code and logs are real.
- **Webhook URL down, slow, or rejected** → the error is stored on the run and shown on the page. The wrapper still returns the child's exit code. Timeout is 5 seconds.
- **Command not found** → status failed, exit 127, stderr tail explains it. No traceback-only failure.
- **Two processes writing the file** → SQLite WAL and a busy timeout. The wrapper is the writer; the page is the reader. A locked database for longer than the timeout surfaces as an error on that call rather than a corrupted file.
- **Dashboard HTML missing from the install** → the server responds with a short plain error telling them to reinstall, instead of a blank 500.

## What Was Simplified and Why

- **Standard-library HTTP server and a single HTML file** instead of a frontend framework and a build step. The page has one screen. A toolchain would not make the curve more true. The fuller version would matter if the page grew a second app.
- **A tail, not a log file** instead of capturing unbounded output to disk. Enough to see the OOM line in the video. The fuller version is a file next to the SQLite database.
- **Demo sampler and seeded examples** instead of requiring an RTX 4090D to try the page. The kernel (a real exit code and a real tail, plus a curve that is labeled when it is fake) stays intact. Seed rows are `origin = seed` and the page says "simulated example".
- **Localhost only** instead of accounts and a deployed service. The video can be recorded locally. Deployment was never a hackathon requirement.
- **One GPU charted at a time** instead of a fleet view. Extra GPUs are stored with `gpu_index`. The page shows GPU 0 and notes if more exist. The target machine has one card.

## Decisions and Open Issues

Learner choices, from the brief, accepted as specified:

- Python CLI and a local page, SQLite, minimal dependencies. Accepted tradeoff: no runtime dependencies, hand-drawn chart, stdlib server.
- nvidia-smi samples of VRAM, power, temperature, utilization, every few seconds.
- Webhook formats: generic, WeCom, DingTalk, Feishu. No service that mainland China cannot reach is required.
- Windows and Linux. Labeled demo sampler when nvidia-smi is missing.

Agent assumptions, also listed in `prd.md > Product Decisions`: default interval 3 seconds, tail of 160 lines, database under `~/.runledger/`, bind `127.0.0.1`, dark bench palette, child's exit code is the wrapper's exit code, `runledger demo` seeds labeled examples.

One uncertainty from the brief: "every few seconds" does not name a number, and a command used in the done line (`python -c "..."`) can finish faster than one interval. Clarification used for the build: default interval is 3 seconds and overridable with `--interval`; the runner always takes a sample at the start of the loop and once more when the process exits, so a sub-second command still has a point on the chart. Evidence: `tests/test_runner.py` (short command has at least one sample) and `tests/test_sampler.py` (demo readings stay in a plausible range, nvidia CSV `[N/A]` parses).

No product question left open from `prd.md > Open Questions`.
