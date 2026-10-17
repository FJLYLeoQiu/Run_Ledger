# How the Devpost Learn Skill Pack was used

This project was planned and built with the [Devpost Learn Skill Pack](https://github.com/challengepost/learn-ai-basics) for the hackathon [Build With AI: Basics](https://learn-ai-basics.devpost.com/).

## Install

From the project root, before any application code:

```bash
npx skills add challengepost/learn-ai-basics --all -y
```

That installed skills `1-start`, `2-scope`, `3-prd`, `4-spec`, `5-build`, and `6-ship` under `.agents/skills/` (with the lockfile `skills-lock.json` pinning `challengepost/learn-ai-basics`). The official rules and judging criteria were read first, at `https://learn-ai-basics.devpost.com/rules`.

## Workflow

The pack's flipped-interaction interview was answered from the written product brief for Run Ledger (a local GPU-job flight recorder for one RTX 4090D, with a labeled demo sampler and WeCom / DingTalk / Feishu webhooks). Decisions in that brief were treated as the learner's answers. Details the brief did not specify — sample interval, log-tail length, database path, bind address, visual palette — are marked as assumptions in the planning docs, not as personal preferences.

Documents written before application code, in the pack's templates:

| Skill | Artifact | Status |
| --- | --- | --- |
| 1-start | `devpost/learner-profile.md` (gitignored; personal learning context) | written |
| 2-scope | `devpost/scope.md` | approved |
| 3-prd | `devpost/prd.md` | approved |
| 4-spec | `devpost/spec.md` | approved |
| 5-build | `devpost/checklist.md`, then the code in slices | see checklist |
| 6-ship | `DEMO.md`, `SUBMISSION.md`, README, MIT `LICENSE` | draft for the human submitter |

`learner-profile.md` is listed in `.gitignore`, as `1-start` requires, so the public repo is not carrying that personal context.

The submission form asks for a short explanation of Skill Pack use. The paragraph below is the one to paste:

> I installed the Devpost Learn Skill Pack with `npx skills add challengepost/learn-ai-basics --all -y` in an empty project and ran it in order. 1-start captured the learner profile. 2-scope, 3-prd, and 4-spec turned the Run Ledger idea into `devpost/scope.md`, `devpost/prd.md`, and `devpost/spec.md` before any application code. 5-build implemented that spec in working slices (wrap a command and record it, show it on the local dashboard, ping a webhook, then demo data and tests). The pack's rule was to plan before writing code and to keep the proof of concept to one loop: prefix a GPU job, keep the ending, optionally notify a chat bot.
