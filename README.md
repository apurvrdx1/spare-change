# spare-change

> Donate unused Claude Pro/Max weekly credits to open-source projects.

## What this is
Pro and Max subscriptions reset weekly. Credits not spent by the cycle boundary are gone. Meanwhile open-source maintainers sit on long backlogs of work an LLM could do but no one is paying to run. spare-change is a small daemon that lets a donor route their unused end-of-week capacity to vetted OSS tasks, signs them with their own `claude` session, and ships the result back to the project.

## How it works
1. You install the agent locally and log in to `claude` as you normally would.
2. You set a credit window in `config.yaml` (e.g., last 10h of the weekly cycle) and an allowlist of OSS projects you want to support.
3. The agent polls the distributor for a JSON task that fits your window and allowlist.
4. It runs the task with `claude --print` against your existing session, capturing the output.
5. It POSTs the result back to the distributor, which forwards it to the project as a PR, issue comment, or artifact.

API users who do not have a subscription can instead set a dollar cap and contribute as a clean line-item donation.

## Quickstart
```bash
git clone https://github.com/apurvrdx1/spare-change
cd spare-change
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.yaml config.yaml
# edit config.yaml if you want
./scripts/run_local.sh        # starts distributor + agent

# in another terminal — pick one:
./scripts/seed_task.sh                                                       # synthetic helper (safe fallback)
./scripts/seed_from_repo.sh D4Vinci/Scrapling scrapling/core/mixins.py review # finds real bugs in a real project
./scripts/seed_from_repo.sh psf/requests src/requests/help.py annotate
./scripts/seed_from_repo.sh httpie/cli httpie/utils.py test-gen
```

Open the live dashboard at <http://127.0.0.1:8080/>. It auto-refreshes every 2
seconds and shows the queue, total donated USD, per-donor and per-project
leaderboards, and click-to-expand task previews.

`seed_from_repo.sh` pulls a file from any public GitHub repo and seeds it as a
task. Three task kinds: `annotate`, `review`, `test-gen`. The Scrapling review
above is the demo — Claude finds an infinite-loop bug, XPath construction
issues, and test gaps in ~45 seconds for under $0.02.

## Multi-donor demo
```bash
./scripts/run_multi_donor_demo.sh    # 1 distributor + 3 donor agents in parallel
./scripts/stop_multi_donor_demo.sh   # idempotent cleanup
```

Spins up three simulated donors (alice / bob / charlie) with distinct
allowlists and poll intervals, seeds five Scrapling tasks across `annotate`,
`review`, and `test-gen`, then tails all four logs. Dashboard shows three
donors contributing to one project in real time. Verified: $0.07 donated
across 4 completed tasks in 75 seconds.

## Auth (optional)
Set `SPARE_CHANGE_DISTRIBUTOR_TOKEN=...` in the distributor's environment.
Agents send the same token in `config.yaml` as `auth_token`. The dashboard
and `GET /tasks`, `GET /tasks/:id`, `GET /healthz` stay unauthenticated; the
three write/claim endpoints (`POST /tasks`, `GET /tasks/next`, `POST /webhook/:id`)
require `Authorization: Bearer <token>`. Comparison is constant-time
(`secrets.compare_digest`). Leave the env var unset for unauthenticated demo
mode.

## Architecture
```
┌──────────────┐                ┌──────────────────────────────────┐
│  Maintainer  │   POST /tasks  │          Distributor             │
│  (seed task) │ ─────────────► │  ┌────────────────────────────┐  │
└──────────────┘                │  │  in-memory queue + costs   │  │
                                │  │  donor & project leaders   │  │
┌──────────────┐  GET /tasks/   │  └────────────────────────────┘  │
│ Donor agent  │     next       │            ▲     │               │
│  (Python)    │ ─────────────► │   webhook  │     │ task JSON     │
│              │ ◄───────────── │   /:id     │     ▼               │
└──────┬───────┘   task chunk   └────────────┼─────────────────────┘
       │                                     │           │
       │ subprocess: claude --print          │           │ GET /
       ▼                                     │           ▼
┌──────────────┐      stdout/stderr          │   ┌──────────────┐
│ claude (Pro) │ ──────────────► result ─────┘   │  Dashboard   │
│  session     │     POST /webhook/:id           │ (auto 2s)    │
└──────────────┘                                 └──────────────┘
```

Maintainer seeds tasks; the distributor holds them in an in-memory queue and
tracks per-donor and per-project totals plus estimated USD cost. The donor
agent polls, runs `claude --print` against the donor's session, and POSTs the
result back, which the dashboard renders live.

The distributor's in-memory queue is the swap-point for NATS JetStream. The
agent's `claude --print` subprocess is the swap-point for Goose runtime
(pending Anthropic OAuth for subscriptions).


## Real OSS problems this unlocks
- Whole-repo semantic re-indexing for large codebases (Kubernetes, Rust).
- Fuzz harness generation for parsers and codecs (libwebp, tree-sitter).
- Per-dependency upgrade impact analysis (Astro, Home Assistant).
- PR first-pass review for drive-by contributors (Babel, Astro).
- Test-gap detection turned into generated tests (Requests, Lodash, Pydantic).
- New-issue triage and dedup against existing reports (Home Assistant, Kubernetes).

## Roadmap
- NATS JetStream gateway behind HTTP for durable fan-out, replacing the in-memory queue.
- SQLite persistence for the in-memory store so tasks survive restart.
- Multi-donor *coordination* (today: simulation only — donors race for tasks; tomorrow: leases + dedup so two agents do not burn credits on the same task).
- Move runtime to Goose once Anthropic ships OAuth for Claude subscriptions. Today the agent shells out to `claude --print`.

## Why not Goose / Numaflow today
Goose is the obvious runtime, but it needs an API key. Anthropic currently blocks third-party tools from authenticating against Pro and Max subscriptions, so a Goose-based agent would force donors onto pay-per-token API billing, which defeats the point. Until that changes we shell out to the official `claude` CLI in `--print` mode against the donor's existing session.

Numaflow is a strong fit on paper for streaming fan-out, but it is K8s-native and push-edge. Pull semantics from donor laptops would need a bridge, and operating a K8s control plane is overkill at MVP scale. NATS JetStream gives durable queues without that footprint and is the planned next step.

## License
MIT
