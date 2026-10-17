# Devpost submission draft — Run Ledger

Draft for the [Build With AI: Basics](https://learn-ai-basics.devpost.com/) form. Edit it in your own voice before you submit. The age-of-majority checkbox is yours to confirm. Do not submit this file for me.

**Project name:** Run Ledger

**Tagline:** The flight recorder for the one GPU on your desk.

**Video:** paste the public YouTube or Vimeo URL after you record `DEMO.md`.

**Try it out:** paste the public Git repository URL. The form's "Try it out" field is where reviewers look for the repo.

## What it does

Run Ledger wraps any command:

```bash
runledger -- python train_lora.py
```

It records when the job started and ended, the exit code, and a tail of stdout and stderr, and it samples the GPU every few seconds — VRAM, power, temperature, utilization — from `nvidia-smi`. A local page, with no account and no internet, lists the runs and charts each one. When the job finishes or crashes, it can POST once to a generic webhook or to a WeCom, DingTalk, or Feishu bot.

If `nvidia-smi` is missing, a demo sampler still draws a curve and the page says the curve is simulated. The exit code and the log tail stay real. `runledger demo` can also drop labeled example runs so the page is not empty in a recording. Those examples are badged as simulated. They are not measurements.

The wrapper returns the child's exit code. A webhook that fails does not change that.

## Who it's for

A solo developer with one RTX 4090D on a Windows PC, running ComfyUI, LoRA training, or a local LLM. They start a job, leave the desk, and come back to a dead terminal whose scrollback is gone. They do not want a cloud experiment tracker, a login, or a notification service that is awkward to reach from mainland China. They already have a group-bot URL.

## How it was built

Empty folder. The Devpost Learn Skill Pack (`npx skills add challengepost/learn-ai-basics --all -y`) ran before application code: scope, then a product requirements doc, then a technical spec, all in `devpost/`. The spec locked a proof of concept with no runtime dependencies: a Python CLI, SQLite, the standard-library HTTP server, and one offline HTML page.

The build followed that boundary. Wrap a command and read it back. Show it on the page. Ping a bot in four payload shapes. Add a labeled demo path so the page can be recorded without a GPU. Tests cover the exit code, the log tail, the nvidia-smi parser, the webhook bodies, and the local API.

## What I learned

Planning the done line before code changed what got built. "A short command still shows up on the page, with at least one sample" is checkable. "It monitors the GPU" is not. That sentence is why the wrapper samples at the start and again when the process exits, and why `tests/test_runner.py` asserts a tail and a sample instead of a happy-path story.

The other lesson was honesty in the demo. A laptop with no NVIDIA driver cannot show a real 4090D curve. Faking one unlabeled would make the video a lie. Labeling the demo sampler, and badging `runledger demo` rows as simulated examples, kept the kernel — a real exit code and a real log — intact on hardware the judges might not have.

## How the Devpost Learn Skill Pack was used

Paste this into the form's Skill Pack question:

> I installed the Devpost Learn Skill Pack with `npx skills add challengepost/learn-ai-basics --all -y` in an empty project and ran it in order. 1-start captured the learner profile. 2-scope, 3-prd, and 4-spec turned the Run Ledger idea into `devpost/scope.md`, `devpost/prd.md`, and `devpost/spec.md` before any application code. 5-build implemented that spec in working slices (wrap a command and record it, show it on the local dashboard, ping a webhook, then demo data and tests). The pack's rule was to plan before writing code and to keep the proof of concept to one loop: prefix a GPU job, keep the ending, optionally notify a chat bot.

Longer notes: `docs/skill-pack-usage.md`.

## Built with

Python 3 standard library only at runtime (SQLite, subprocess, a small HTTP server). pytest for tests. `nvidia-smi` when a driver is installed. Optional HTTP POST to a bot URL the user already has.

No cloud account, no hosted database, no paid API.

## Checklist before you hit submit

- Public repo link in "Try it out", with this MIT `LICENSE` visible.
- `devpost/scope.md`, `devpost/prd.md`, and `devpost/spec.md` are in that repo.
- Video is public, under three minutes, and shows a wrap plus the page. The simulated badge is readable.
- Skill Pack answer is filled in.
- Age-of-majority checkbox is yours.
