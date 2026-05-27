# spare-change maintainer adoption kit

If you maintain an open-source project and you want Claude Pro/Max donors to
send their idle weekly credits your way, this kit is the minimum surface
area you need to commit. Five files. Copy them into your repo, edit the
placeholders, set two secrets, and you are done.

Read more about the donor side at <https://github.com/apurvrdx1/spare-change>.

## What is in the kit

| File | Where it goes in your repo | What it does |
|------|----------------------------|--------------|
| `.github/SPARE_CHANGE.md` | same path | Public notice. Tells donors and the distributor what tasks you accept and what you don't. |
| `scripts/queue_spare_change_tasks.py` | same path | Stdlib-only Python script that POSTs tasks to a distributor. Run it manually or from CI. |
| `.github/workflows/spare-change.yml` | same path | GitHub Action. Runs every Monday at 09:00 UTC and seeds a batch of tasks. |
| `.github/spare-change-manifest.yaml` | same path | Starter manifest. Lists which files to send and what kind of help you want. |
| `README.md` (this file) | discard, or keep as `docs/spare-change.md` | The thing you are reading. Not required in your repo. |

## Suggested order to adopt

1. **Read** `.github/SPARE_CHANGE.md` and edit the bracketed sections so it
   reflects what you actually want donors to work on. Especially the
   **What we accept** and **What we don't accept** lists — donors read these.
2. **Drop in** `scripts/queue_spare_change_tasks.py`. Do not chmod it —
   invoke it as `python scripts/queue_spare_change_tasks.py`.
3. **Edit** `.github/spare-change-manifest.yaml` so the listed paths exist
   in your repo. Start with 3–5 entries; you can always add more.
4. **Add secrets** to your repo (Settings -> Secrets and variables -> Actions):
   - `SPARE_CHANGE_DISTRIBUTOR_URL` — the distributor base URL.
   - `SPARE_CHANGE_DISTRIBUTOR_TOKEN` — bearer token issued by the distributor.
5. **Commit** `.github/workflows/spare-change.yml`. The first scheduled run
   happens the following Monday. You can also click **Run workflow** from
   the Actions tab to test it immediately.

## Placeholders and secrets

The workflow reads three things from the environment:

| Name | Where | Required | Default |
|------|-------|----------|---------|
| `SPARE_CHANGE_DISTRIBUTOR_URL` | repo secret | yes | — |
| `SPARE_CHANGE_DISTRIBUTOR_TOKEN` | repo secret | yes | — |
| `SPARE_CHANGE_MANIFEST_PATH` | workflow `env:` block | no | `.github/spare-change-manifest.yaml` |

The script itself takes the same values via flags:
`--distributor`, `--token`, `--manifest`. The token also falls back to the
env var `SPARE_CHANGE_DISTRIBUTOR_TOKEN`, which is how the workflow passes it.

## Trying it without the GitHub Action

You can seed tasks from your laptop while you decide whether to enable the
weekly cron. From the root of your repo:

```bash
pip install pyyaml   # only needed for YAML manifests; JSON works without it
export SPARE_CHANGE_DISTRIBUTOR_TOKEN=...
python scripts/queue_spare_change_tasks.py \
  --manifest .github/spare-change-manifest.yaml \
  --distributor https://distributor.example.org \
  --dry-run
```

Drop `--dry-run` once the printed payloads look right.

## Cost expectations

Each task is capped at `$0.50` by default. The cap is per-task, not
per-project. If you raise it in the manifest, raise it deliberately — donor
credits are finite.

## Questions

Open an issue on <https://github.com/apurvrdx1/spare-change>.
