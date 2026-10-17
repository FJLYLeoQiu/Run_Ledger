---
doc: scope
status: approved
---

# Run Ledger

A local flight recorder for long GPU jobs on a single machine. Wrap the command you were already going to run. The ending — time, exit code, last lines, GPU curve — is still there when you come back. Optionally, a chat bot pings you when it finishes or dies.

## The Unique Kernel

`runledger -- <any command>` writes down the run and samples nvidia-smi every few seconds (VRAM, power, temperature, utilization). When the process ends, Run Ledger can POST one message in a shape WeCom, DingTalk, Feishu, or a generic webhook already accept. If nvidia-smi is missing, a clearly labeled demo sampler still draws a curve so the same page can be shown on a laptop with no GPU. The command's real exit code and log tail are never faked.

Take away the curve, the China-reachable bot formats, or the honest demo fallback, and this is just a command timer.

## Who It's For

A solo developer with one RTX 4090D on a Windows box, running ComfyUI, a LoRA training script, or a local LLM. They start a job, leave the desk, and come back to a terminal whose scrollback is gone. They are not looking for a cloud experiment tracker, an account, or a service that is awkward to reach from mainland China.

## The Core Loop

They prefix a command with `runledger --`. Output still streams in the terminal. They walk away. Later they open the local page and see that run: how long it took, whether it died, the last lines, and the GPU curve. If a bot URL is set, the phone gets one message when the job finishes or crashes. Next job, same prefix.

## Inspiration & Identity

A flight recorder left on the bench, not a multi-tenant dashboard. Weights & Biases is what this person would use if the job lived in the cloud and they wanted an account. nvidia-smi is what they already glance at and then lose. Run Ledger sits between those: one machine, no account, the ending kept.

Tone: short, specific, a little dry. It should feel like a tool you trust with an overnight train, not a product tour.

## Why This Matters to the Learner

The brief is a tool the author would actually put in front of a training command. The hackathon asks for one working loop, the Skill Pack's planning docs, and a short video. This is that loop. The audience is specific (one 4090D, mainland China, jobs that outlast a terminal scrollback), which is the whole case for building it.

## What "Working" Looks Like

Install with `pip install -e .`. Run `runledger -- python -c "..."`. The command's own prints still appear, and a one-line summary follows: run id, status, exit code, duration. Start `runledger serve` and open the printed URL. That run is in the list. Open it and see the samples. On a machine with no nvidia-smi, the page says the curve is from the demo sampler, and the exit code and log tail are still the real ones. That is the beat the video has to show.

## The POC Boundary

In, tightly:

- Wrap any command, on Windows and Linux, and return the child's exit code.
- Record start, end, exit code, and a tail of stdout and stderr.
- Sample VRAM, power, temperature, and utilization every few seconds.
- One SQLite file shared by the CLI and the page.
- One local page, no internet required: a list of runs and a chart plus log tail for the run you open.
- Optional webhook: generic JSON, WeCom, DingTalk, Feishu. Failure to deliver does not change the child's exit code.
- Labeled demo sampler when nvidia-smi is missing, plus a `runledger demo` seed of obviously fake example runs so the page is not empty in a recording.
- Tests, English README, MIT license, a two-minute demo script, a draft submission write-up.

If it is not needed to prove that loop, it is not in this proof of concept.

## Later

Worth doing after the proof, not as part of it:

- Keep the full log on disk, not only the tail.
- Estimate watt-hours for the run.
- More than one machine in the same ledger.
- A ComfyUI node that records a workflow without the CLI.

## Explicitly Cut

- Accounts, teams, and hosted sync. The person has one GPU. A login would hide the kernel.
- Prometheus and Grafana. They are a second product this person did not ask to operate.
- Training-framework plugins (a Hugging Face callback, a ComfyUI node in the proof). The kernel is "any command". A plugin would make it smaller.
- Notification services that need their own account or are a poor fit in mainland China. The brief asks for a URL the user already has, in the bot formats they already use.
