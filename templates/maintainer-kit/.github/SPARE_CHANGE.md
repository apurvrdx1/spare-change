# spare-change opt-in notice

This file declares that **this project accepts donated Claude compute** via
[spare-change](https://github.com/apurvrdx1/spare-change). If you maintain
another OSS project and want to copy this notice, edit the bracketed sections
to match what you actually want help with.

## What this means

Claude Pro and Max subscribers often have unused weekly credits. spare-change
routes that idle compute to OSS projects that have opted in. When you commit
this file to your repo, you are telling donors and the distributor that you
accept tasks of the kinds listed below, that you have read the cost
expectations, and that you will treat donor-produced output as you would
treat any other community contribution — with review, gratitude, and the
right to decline.

You are not on the hook to merge anything. A donor task produces a markdown
artifact (typically posted as an issue via `gh issue create --body-file -`).
You review it like any other suggestion.

## What we accept

These are the task kinds we will actually look at. Donors are expected to
stick to this list. Edit freely — be concrete, the donor side reads this.

- Code review on PRs touching `src/parser/` or `src/runtime/`
- Type annotations on files in `src/legacy/` (Python 3.11+ syntax only)
- Test generation for modules with less than 60% line coverage
- Docstring improvements on public API surface in `src/api/`
- Small refactors flagged with the `good-first-task` label

## What we don't accept

If a donor task falls into one of these categories, we will close it without
review. This protects donor credits as much as it protects us.

- Anything that modifies CI configuration (`.github/workflows/`, `tox.ini`, etc.)
- Tasks targeting branches other than `main`
- Dependency upgrades — we manage these through Dependabot
- Rewrites of any module larger than 500 lines (split it first)
- Anything touching secrets, auth, or cryptographic code
- Documentation translation (handled by our localization team)

## Donor allowlist

> Replace this section with one of:
> - "Open to any donor in good standing with the spare-change distributor."
> - An explicit list of GitHub handles whose donations we will accept.
> - A reference to a CODEOWNERS-style file.

Open to any donor in good standing with the spare-change distributor.

## Reporting abuse

If a donor task contains harmful, low-quality, or off-topic content, please
report it so we can flag the donor with the distributor.

> Replace with your contact:
> - Email: `security@your-project.example`
> - Or see [SECURITY.md](./SECURITY.md)

## Cost expectations

We expect each donor's contribution to stay under **$0.50 per task**. Tasks
that cost more than this should be split, or routed to a human contributor.
The distributor enforces a `max_cost_usd` ceiling per task — we set ours at
$0.50 in our seed script and our GitHub Action.

If you want to raise or lower this ceiling for your own project, edit
`scripts/queue_spare_change_tasks.py` and `.github/spare-change-manifest.yaml`
together — the ceiling is per-task, not per-project.

## How tasks reach us

Two paths:

1. **Manual seeding** — a maintainer (or trusted contributor) runs
   `python scripts/queue_spare_change_tasks.py --manifest <path>` against a
   distributor URL. This produces one task per manifest entry.
2. **Scheduled seeding** — the GitHub Action in
   `.github/workflows/spare-change.yml` runs weekly and seeds whatever is in
   `.github/spare-change-manifest.yaml`.

Both paths are opt-in. Nothing happens unless you commit a manifest and set
the `SPARE_CHANGE_DISTRIBUTOR_URL` / `SPARE_CHANGE_DISTRIBUTOR_TOKEN` secrets.

---

Learn more or run your own distributor:
<https://github.com/apurvrdx1/spare-change>
