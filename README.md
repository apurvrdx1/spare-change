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
./scripts/seed_task.sh                                                 # synthetic untyped helper (safe fallback)
./scripts/seed_from_repo.sh psf/requests src/requests/help.py annotate # real file from a real OSS project
./scripts/seed_from_repo.sh tornadoweb/tornado tornado/escape.py review
./scripts/seed_from_repo.sh httpie/cli httpie/utils.py test-gen
```

`seed_from_repo.sh` pulls a file from any public GitHub repo and seeds it as a
task. Three task kinds: `annotate`, `review`, `test-gen`.

## Architecture
```
+--------------+      HTTP      +-------------------+      HTTP      +--------------+
| Donor agent  | <------------> |   Distributor     | <------------> |   Result     |
| (Python)     |  poll / post   |  (FastAPI + queue)|   webhook      |   webhook    |
+------+-------+                +-------------------+                +--------------+
       |
       | subprocess: claude --print
       v
+--------------+
| claude (Pro) |
+--------------+
```

## Real OSS problems this unlocks
- Whole-repo semantic re-indexing for large codebases (Kubernetes, Rust).
- Fuzz harness generation for parsers and codecs (libwebp, tree-sitter).
- Per-dependency upgrade impact analysis (Astro, Home Assistant).
- PR first-pass review for drive-by contributors (Babel, Astro).
- Test-gap detection turned into generated tests (Requests, Lodash, Pydantic).
- New-issue triage and dedup against existing reports (Home Assistant, Kubernetes).

## Roadmap
- NATS JetStream gateway behind HTTP for durable fan-out, replacing the in-memory queue.
- Multi-donor coordination so two agents do not burn credits on the same task.
- Move runtime to Goose once Anthropic ships OAuth for Claude subscriptions. Today the agent shells out to `claude --print`.

## Why not Goose / Numaflow today
Goose is the obvious runtime, but it needs an API key. Anthropic currently blocks third-party tools from authenticating against Pro and Max subscriptions, so a Goose-based agent would force donors onto pay-per-token API billing, which defeats the point. Until that changes we shell out to the official `claude` CLI in `--print` mode against the donor's existing session.

Numaflow is a strong fit on paper for streaming fan-out, but it is K8s-native and push-edge. Pull semantics from donor laptops would need a bridge, and operating a K8s control plane is overkill at MVP scale. NATS JetStream gives durable queues without that footprint and is the planned next step.

## License
MIT
