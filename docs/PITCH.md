# spare-change — hackathon pitch deck

Slide content drafted for the demo. Render in your design tool of choice.
Voice: engineering-literate, no marketing fluff, named projects, short
declarative sentences. One strong line per slide beats six bullets.

Track: **Best Project Overall**. Rubric: Impact / Execution / Creativity / Track fit.

---

## Slide 1 — Spare Change

**On-screen copy** (≤30 words):
Spare Change
Donate the Claude Code credits you won't use this week to open source projects that need them.

**Speaker notes** (60-90 words):
Hey. I'm building Spare Change. Every Sunday night, a few million dollars of Claude Code credits expire across Pro and Max accounts because most of us never hit our weekly cap. Meanwhile open source maintainers are buried in work AI could handle, but no maintainer is paying a per-repo subscription to do it. Spare Change is the pipe between those two facts. Four minutes, then a live demo against a real repo.

**Visual:** Coin with the Claude logo dropping into a tip jar labeled with GitHub octocats.

---

## Slide 2 — Your credits die every Sunday

**On-screen copy:**
Claude Pro and Max reset weekly.
Most users finish the week with hours of unused credit.
Sunday 23:59, gone.

**Speaker notes:**
Show of hands: who hit their weekly Claude cap this week? Yeah, almost nobody. The cap is sized so heavy users don't churn, which means the median user leaves real capacity on the floor every single week. You paid for it. You can't bank it. You can't gift it. At midnight Sunday, Anthropic's meter ticks over and your unused hours are scrap. That's the first piece of waste.

**Visual:** Weekly usage graph that flatlines Thursday onward, with a red "expires" cliff at Sunday midnight.

---

## Slide 3 — Open source is drowning in AI-shaped work

**On-screen copy:**
Kubernetes: 3,000+ open issues.
Babel PRs wait weeks for first review.
Home Assistant gets the same bug filed every week.

**Speaker notes:**
Now the other side. Kubernetes sits on three thousand open issues. Babel maintainers can't keep up with drive-by PRs that need style and test nits before a human should touch them. Home Assistant gets duplicate bug reports weekly because GitHub search is bad. None of these projects are going to pay for Claude seats per maintainer. The work AI could do today is sitting there, unfunded, because the unit economics of paid subscriptions don't match the shape of OSS labor.

**Visual:** Three project logos (Kubernetes, Babel, Home Assistant) with red counters: open issues, PR wait time, duplicate reports.

---

## Slide 4 — Donate the dying hours

**On-screen copy:**
Your last 10 hours of the week → an OSS project you pick.
Your session. Your allowlist. Your cap.

**Speaker notes:**
Here's the match. You tell Spare Change: in the last ten hours of my weekly window, run tasks for these four projects I care about, up to this dollar cap. The work happens in your local Claude Code session, on your machine, against credits that were about to expire anyway. For API users it's even cleaner: a single line-item donation, deductible, no micro-transaction fees, no ambiguity. You give the part you weren't using. The project gets work it couldn't otherwise afford.

**Visual:** Two clocks side by side: donor's weekly window ticking down, OSS task queue ticking up. Arrow between them.

---

## Slide 5 — The loop

**On-screen copy:**
Daemon polls → picks up task → runs claude --print → POSTs result.
No new auth. No new infra on the donor side.

**Speaker notes:**
Four boxes. The donor runs a Python daemon with a YAML config. It polls a distributor for chunked JSON tasks scoped to the donor's allowlist. When one matches, it shells out to claude --print against the donor's existing Claude Code session, so no API keys, no OAuth gymnastics, no Anthropic terms violated. Result POSTs back to a webhook the maintainer controls. Maintainer integrates the work into their repo on their schedule. Donor goes back to their evening.

**Visual:** Four-box diagram: Donor daemon → Distributor → Donor's Claude session → Maintainer webhook. Clean arrows, no clutter.

---

## Slide 6 — What this actually unlocks

**On-screen copy:**
Nightly semantic re-index of monorepos.
Fuzz harnesses for libwebp, tree-sitter.
First-pass PR review on Babel.
Dedup triage on Home Assistant issues.

**Speaker notes:**
Four concrete jobs nobody is doing today. One: nightly whole-repo re-indexing — Cursor and Sourcegraph indexes go stale on Kubernetes-scale monorepos and maintainers skip the rebuild because it costs hundreds a night. Two: fuzz harness generation for parsers like libwebp and tree-sitter grammars that aren't in the OSS-Fuzz funded list. Three: first-pass review of drive-by PRs on Babel and Astro — the eighty percent of nits that eat reviewer time. Four: deduping the same bug filed weekly on Home Assistant. Real work, queued, doable.

**Visual:** Four-quadrant grid, one logo per quadrant (Kubernetes, libwebp, Babel, Home Assistant), one task verb under each.

---

## Slide 7 — Live demo

**On-screen copy:**
Live dashboard, left. Seed a real review on Scrapling, right.
Watch the leaderboard tick. $0.02. 45 seconds.

**Speaker notes:**
Real thing. On the left, the live dashboard at localhost:8080 — queue, per-donor and per-project leaderboards, total donated USD, auto-refreshing every two seconds. On the right, I seed one task against a real OSS project: review scrapling/core/mixins.py. Agent picks it up, shells out to claude --print in my session, posts the result back. Watch the leaderboard update live. Claude finds real bugs in a real OSS project — an infinite-loop, XPath issues, test gaps — in about 45 seconds for under $0.02. Click the task to expand the raw claude output.

**Visual:** Split screen: dark-mode dashboard on the left with queue counts and leaderboards animating; terminal on the right running the Scrapling review and streaming claude output. Cost ticker visible on the dashboard.

---

## Slide 8 — What's next

**On-screen copy:**
NATS JetStream gateway for fan-out.
Multi-donor coordination + dedup.
Goose runtime when Anthropic ships OAuth for subscriptions.

**Speaker notes:**
Today the MVP is FastAPI plus an in-memory queue, which is fine for the demo and bad for fifty thousand donors. Next is NATS JetStream behind an HTTP gateway so we can fan tasks out durably and let donors come and go. After that, donor coordination so two people don't burn credits on the same task. And when Anthropic ships OAuth for Claude subscriptions, we move the runtime to Goose and drop the subprocess hack entirely. Until then, claude --print works.

**Visual:** Three-stage timeline: now (subprocess), next (NATS gateway), later (Goose + OAuth).

---

## Slide 9 — The ask

**On-screen copy:**
OSS maintainers: bring us a task queue.
Donors: try it next week.
Builders: the distributor is open. Help us shape it.

**Speaker notes:**
Three asks, pick whichever you are. If you maintain an OSS project and you have a backlog of bounded, automatable work, talk to me after — we'll wire up your first queue this weekend. If you're a Claude Code user who never hits the cap, install the daemon next week, donate one window, tell me what broke. If you build distributed systems and the NATS gateway sounds fun, the repo is open and I want collaborators. That's it. Thanks.

**Visual:** Three columns, one icon each: wrench (maintainers), coin (donors), keyboard (builders). QR code to repo at the bottom.

---

# Lightning 3-slide cut (2-minute version)

## Slide L1 — Spare Change

**On-screen copy:**
Spare Change
Donate the Claude Code credits you won't use this week to open source.

**Speaker notes:**
I'm building Spare Change. Two minutes. Most Claude Pro and Max users never hit their weekly cap, and at Sunday midnight the unused credit expires. Meanwhile open source maintainers are buried in work AI could do. Spare Change connects the two sides. Watch the demo.

**Visual:** Coin dropping into a tip jar labeled with octocats.

## Slide L2 — Two wastes, one loop

**On-screen copy:**
Credits expire weekly. OSS work piles up.
Local daemon → distributor → your Claude session → maintainer webhook.

**Speaker notes:**
Kubernetes has three thousand open issues. Babel PRs wait weeks. Home Assistant gets the same bug filed weekly. None of these projects pay for AI per maintainer. On the other side, you paid for credits you're not using. Donor runs a daemon, picks an allowlist and a window, the daemon pulls chunked tasks, runs claude --print in your existing session, POSTs the result. No new auth, no new infra for you.

**Visual:** Four-box loop diagram with the two waste sources funneling in from opposite sides.

## Slide L3 — Live demo + ask

**On-screen copy:**
Watch it run. Then: maintainers, donors, builders — find me after.

**Speaker notes:**
Config on the left, mock distributor on the right. I seed a real task: draft type hints for an untyped file in a real OSS project. Daemon polls, picks it up, runs Claude in my session, posts the result back. That's it. If you maintain OSS, bring me a queue. If you have spare credits, try it next week. If you want to help build the NATS gateway, the repo is open.

**Visual:** Split terminal demo, with a QR code to the repo persistent in the corner.

---

# 60-word elevator pitch

Most Claude Pro and Max users never hit their weekly credit cap, and at Sunday midnight the rest expires. Open source projects are drowning in work AI could do but can't afford to fund. Spare Change is a local daemon plus distributor that lets you donate the dying hours of your weekly window to OSS projects you pick. Demo today.
