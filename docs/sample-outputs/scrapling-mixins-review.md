# Sample output: Scrapling mixins.py — code review

Real captured artifact from running spare-change end-to-end against the live distributor.
Backup for the live demo: if the network or claude CLI breaks on stage, point to this file.

- **Captured:** 2026-05-27 17:35 UTC
- **Task ID:** `tsk_6b08fd2d1087`
- **Project:** `D4Vinci/Scrapling`
- **File:** `scrapling/core/mixins.py`
- **Kind:** review
- **Donor:** `agent_donor_alice`
- **Status:** success
- **Duration:** 66.6s
- **Output:** 4182 chars
- **Estimated cost:** $0.0188

---

Findings for `scrapling/core/mixins.py`:

- [bug] L46–53 — The sibling counter only counts up to the target, so a first-of-multiple sibling (e.g. target is the 1st of 3 `<div>`s) gets `counter[target.tag] == 1` and no `:nth-of-type` is added, yielding an ambiguous selector that matches all three. Fix: count total siblings with `target.tag` in `target.parent.children` and also record target's index; emit `:nth-of-type(i)` whenever the total is > 1, not only when the running count is > 1.

- [bug] L58, L65 — When the walk terminates without ever entering the `if target.parent` branch (e.g. called on the root element or a detached node), `selectorPath` is empty and the function returns `""` (CSS) or `"//"` (XPath); `"//"` is an invalid XPath. Fix: if `selectorPath` is empty, return `target.tag` / `f"//{target.tag}"` (or raise) before joining.

- [bug] L57 — `target.tag == "html"` is case-sensitive; XHTML/XML-parsed documents can preserve `HTML`/uppercase tags and the stop condition will be skipped, walking past the root. Fix: compare `target.tag.lower() == "html"` (or use a sentinel like `target.parent is None`).

- [bug] L46 — `child._root == target._root` compares wrapped roots with `==`; for lxml `_Element` this usually works but is fragile if `_root` is ever wrapped or proxied. Fix: use `child._root is target._root` for identity comparison, which is what's actually intended.

- [bug] L21–37 — In `full_path=True` CSS mode an ancestor `id` becomes just one component (`#id`) and the walk continues to `html`, producing selectors like `html > body > #main > div`; that's verbose but valid. However in `full_path=True` XPath mode the same path emits `//html/body/*[@id='main']/div`, where `//html` plus an absolute path is semantically odd. Fix: in XPath full-path, prefix with `/` (absolute) rather than `//` once you've walked to `html`, or document the intent.

- [perf] L43–50 — For every ancestor you iterate *all* siblings and bucket *every* tag into a dict just to read one key. Fix: iterate `target.parent.children` once counting only `child.tag == target.tag`, breaking when you've passed `target`; drop the `Dict` entirely.

- [perf] L18, L37, L57, L65 — `" > ".join(reversed(selectorPath))` and the XPath equivalent are recomputed at three return sites with identical logic. Fix: build the result once after the loop via a small helper (`_join(parts, css)`), removing duplicated branches and making the empty-path bug easier to fix.

- [style] L11 — `selectorPath` is camelCase and untyped; rest of the codebase + PEP 8 use snake_case. Fix: rename to `selector_path: list[str] = []`.

- [style] L40–45 — Five lines of commented-out class-selector code with an explanatory rationale belong in a commit message, not the source. Fix: delete the commented block; the git history preserves the reasoning.

- [style] L15 — `self: Any` on every method defeats type checking for what is functionally a `Selector` mixin. Fix: use a `Protocol` (or `TYPE_CHECKING` import of `Selector`) describing `_root`, `parent`, `attrib`, `tag`, `children`, `_is_text_node`.

- [style] L21 — `selection.lower() == "css"` is recomputed once but the API accepts any string silently; `"CSS"`, `"xpath"`, `"foo"` all map to XPath. Fix: accept a `Literal["css", "xpath"]` or validate and raise on unknown values.

- [style] L67–94 — Four near-identical `@property` wrappers; each docstring is duplicated. Fine as-is, but consider a single method with `kind`/`full_path` kwargs and keep the properties as thin aliases to reduce drift.

- [test-gap] No visible tests exercise: (a) first-of-N siblings (the counter bug above), (b) root element with no parent, (c) uppercase `HTML` tag, (d) `full_path=True` with an ancestor carrying an `id`, (e) text-node early return, (f) elements whose id contains `'` (the `f"[@id='{...}']"` interpolation will break XPath — also a latent injection-style bug worth a separate fix using `concat()` or escaping).

- [bug] L26, L29 — Related to the test gap above: ids containing `'` produce malformed XPath (`[@id='a'b']`). Fix: if the id contains both quote types, emit `concat('a', "'", 'b')`; if it contains only `'`, switch to double quotes.
