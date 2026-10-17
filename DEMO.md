# Demo video script — about 2 minutes

Judges watch the video, not the repo. Record a screen capture with this narration in English. No copyrighted music. Do not show API keys; if you paste a real bot URL, blur the key.

Total time is about 120 seconds. Speak a little slower rather than adding shots.

## What the video has to land

- **Design.** A whole product: empty page, a real wrap, the chart and log, a crash you can read, and the webhook sitting on the same screen. Not a terminal-only demo.
- **Potential impact.** One person, one RTX 4090D, jobs that outlast a terminal scrollback (ComfyUI, LoRA training, a local LLM), and a chat bot they can actually receive in mainland China.
- **Innovation / idea.** A prefix on any command, plus a GPU curve, plus WeCom / DingTalk / Feishu — and a demo sampler that is labeled when it is fake. Not another cloud experiment tracker.
- **Presentation.** Problem, who it is for, and why it matters, in that order, with the product working on screen the whole time.

## Shot list

### 0:00–0:15 — The person and the problem

**On screen:** The desktop. A terminal in a training folder, or a ComfyUI window that has clearly been left running. No title card.

**Do:** Don't click around. Start talking.

**Narration:**

> I train on one graphics card, an RTX 4090D, on a Windows PC at my desk. ComfyUI, a LoRA, a local model. I start the job and leave. When I come back, the terminal is dead and the scrollback is gone. I don't know if it finished, ran out of memory, or just sat there hot.

### 0:15–0:25 — Empty, on purpose

**On screen:** `runledger serve` already open. The page shows "Nothing recorded yet" and the command `runledger -- python train_lora.py`.

**Do:** Hover the empty state. Don't scroll past it.

**Narration:**

> Run Ledger starts as an empty page on this machine. No account. Nothing is loaded from the internet.

### 0:25–0:48 — Wrap the command

**On screen:** A second terminal. Type and run:

```bash
runledger -- python -c "import time; print('epoch 1 loss 0.42'); time.sleep(3); print('done')"
```

Use `python3` if that is the interpreter on the machine. Let the prints appear, then hold on the summary line (`runledger #… success exit 0`).

**Narration:**

> I don't launch the job from a new app. I prefix the command I was already going to run. Output still scrolls here. When it ends, one line: the id, success or failure, the exit code, how long, the peak memory. The exit code is the program's exit code, so a script still fails when the train fails.
>
> This laptop has no nvidia-smi, so Run Ledger says the curve will be simulated and labeled. The log and the exit code are real.

### 0:48–1:08 — The page has the run

**On screen:** Back to the browser. The new run is at the top. Click it if it is not already open. Point at the status pill, the log tail (`epoch 1 loss 0.42` / `done`), and the banner that says the curve is simulated.

**Narration:**

> The same run is on the local page. Exit zero. The last lines are here. The chart is labeled demo sampler, so I don't confuse it with a measurement from a card I don't have. On the 4090D, this chart is nvidia-smi: memory, watts, temperature, utilization, every few seconds.

### 1:08–1:28 — The crash you used to lose

**On screen:** If you have not already, run `runledger demo` before recording so the examples exist. Click the failed `train_lora.py --rank 64` run. Show the curve climbing, then the stderr tab with `CUDA out of memory`. Leave the "Simulated example" banner readable.

**Narration:**

> This is the ending I used to lose. Memory climbs into the ceiling, the process dies, and the last line is CUDA out of memory. These four history rows are simulated examples — the page says so — so the shape of the product can be shown on a machine with no GPU. They are not a fake 4090D.

### 1:28–1:48 — The phone

**On screen:** The webhook form on the same page. Open the format menu so WeCom, DingTalk, and Feishu are visible. If you can do it without showing a secret, hit Send test against a bot or a local catcher and show "Test ping delivered". Otherwise leave the URL blank and say nothing is sent.

**Narration:**

> When the job finishes or crashes, Run Ledger can POST once. Generic JSON, or the bots I already have in China: WeCom, DingTalk, Feishu. Nothing leaves this machine until I paste a URL. If the bot is down, the train's exit code does not change.

### 1:48–2:00 — Why it matters

**On screen:** The run list, with the real wrap and the failed example both visible. Stop talking on the list, not on a slide.

**Narration:**

> Cloud experiment trackers assume an account and a cluster. I have one card and a chat bot. Run Ledger is the prefix that keeps the ending until I come back.

## Before you upload

- Length under 2:30, so a judge who stops at two minutes still heard the close.
- Public on YouTube or Vimeo, no unlisted-only link.
- The simulated badge must be readable in the crash shot. Do not narrate those rows as a real training run.
- Blur any webhook key.
- Put the video URL in `SUBMISSION.md` before you paste the draft into the Devpost form.
