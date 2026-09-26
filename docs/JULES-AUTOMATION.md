# Jules automation for A

This repository is the **A** side of the A/B experiment. Its CI workflows are `installer-checks` and `Android Termux arm64 Tests`. Jules should work only in `psyc-exe/termux-agenticOS-beyond` when handling an A issue. Read `README.md`, `docs/VALIDATION.md`, and `handoff.md` before changing installer behavior. Host checks and the ARM64 container do not prove Android installation, X11, GPU, native root, or APK acceptance.

## One-time setup

1. Connect this repository to the Jules GitHub app. The Jules CLI can confirm access with `jules remote list --repo`.
2. Create a Jules API key in [Jules Settings](https://jules.google.com/settings). Add it to this repository's GitHub Actions secrets as `JULES_API_KEY`. Do not commit it or place it in the Jules Initial Setup script.
3. Push `.github/workflows/jules-ci-triage.yml` to `main`. A failed `installer-checks` or `Android Termux arm64 Tests` run on `main` then creates one issue per workflow and commit, starts a Jules API session with automatic PR creation, and records the session link in that issue. PRs stay open for review. If a workflow is renamed, update the monitored name.
4. In Jules **Configuration → Initial Setup**, enter `bash scripts/jules-env-setup.sh` and select [Run and Snapshot](https://jules.google/docs/environment/). It runs the host gate and dispatcher tests inside Jules's Ubuntu VM. CI also runs ShellCheck when installed; `scripts/check.sh` reports when ShellCheck is unavailable in the Jules VM.

## Ongoing maintenance

- Create a [weekly Scheduled Task](https://jules.google/docs/scheduled-tasks/) using the prompt below. This can make one scoped change and open a PR without a new manual prompt.
- Enable [Suggested Tasks](https://jules.google/docs/suggested-tasks/) if available. The current feature mainly recognizes resolvable TODO comments, and suggestions require review before work starts.
- For a specific bug or feature, open a focused GitHub issue with a reproduction or acceptance criteria and add the `jules` label. The connected Jules GitHub app can start from the issue.

Weekly Scheduled Task prompt:

> Read `README.md` and `docs/VALIDATION.md`. Inspect current A issues and PRs. Choose at most one small, verifiable maintenance fix or useful feature that is not already in progress. Make a focused change, run `bash scripts/check.sh`, and open a PR for review. Do not edit the B repository. Keep Android device acceptance pending unless actually performed. If blocked by missing hardware, credentials, or source, report the blocker rather than claiming success.

The [Jules REST API](https://jules.google/docs/api/reference/) is experimental. This integration uses its Sources and Sessions endpoints with `AUTO_CREATE_PR`; check for API changes if CI triage starts failing. The session API starts work but does not merge PRs.
