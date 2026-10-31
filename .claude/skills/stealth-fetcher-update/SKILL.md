---
name: stealth-fetcher-update
description: Updates stealth-fetcher's dependencies and browser engines, smoke-tests them, and ships the result by redeploying cfb-tv-schedule, the only image that bundles it. Use when asked to update stealth-fetcher, camoufox or patchright, fix a CVE that Trivy reports in the /stealth-fetcher path of the cfb-tv-schedule image, or respond to Cloudflare challenge failures.
---

# stealth-fetcher Update

This repo deploys nothing by itself. The `cfb-tv-schedule` Dockerfile copies this repo into its image through a build context, so a change reaches production only when `cfb-tv-schedule` is redeployed.

## Check before you change

1. Run `git status -sb`.
2. If the repo has uncommitted work that you did not make, stop and ask Kyle. The deploy sends the working tree, including uncommitted files.

## Update dependencies

- **One package, for a CVE:** run `uv lock --upgrade-package <package>`.
- **Everything:** run `uv lock --upgrade`, then read the diff of `uv.lock`. Look closely at `camoufox`, `patchright` and `playwright`.

## Test

This repo has no test suite. Use these smoke tests.

1. Run `uv sync --frozen --no-dev`.
2. Run `uv run --frozen --no-dev python -c "import stealth_fetcher.engines, stealth_fetcher.cli; print('ok')"`.
3. Run `uv run --frozen --no-dev python -m stealth_fetcher.cli --help`.
4. If a browser engine changed, do a real fetch. Run `uv run camoufox fetch` first if the browser is missing, then run `uv run stealth-fetcher fetch https://example.com`.
5. Stop if a step fails. Do not deploy.

A smoke test does not prove that a browser passes a Cloudflare challenge. After an engine update, watch the first scheduled scrape in the `cfb-tv-schedule` logs.

## Ship it

1. Use the `cfb-tv-schedule-release` skill in `~/src/cfb-tv-schedule` to deploy.
2. If that skill is not loaded, read `~/src/cfb-tv-schedule/.claude/skills/cfb-tv-schedule-release/SKILL.md` and follow it.

## Rules

- `FINGERPRINT_OS` in `stealth_fetcher/engines.py` and the camoufox font list in the `cfb-tv-schedule` Dockerfile must change together.
- Keep site knowledge out of this repo. URLs, selectors and parsing belong in the project that uses the data.
- Commit only when Kyle asks, and follow `~/.claude/rules/git-conventions.md`.
- Never push. Say what is committed and ready, and that Kyle must push it.

## Report

Give the packages that changed, the smoke test results, and the result of the `cfb-tv-schedule` deploy.
