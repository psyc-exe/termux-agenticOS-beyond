# Software store and shell setup

Run `bash software.sh` in Termux, or `agenticos-software` after installation.
Use Space to select components, Enter to review/install, and Cancel to go back.
The store installs **and configures** each selected integration. Installed apps
can be launched from the store or from TUIPKG (`apps` with shell shortcuts).

The distro installer's final question offers **Beginner-friendly** or **Vanilla**.
Beginner enables Fish, the Cyberdream Starship theme, practical `tldr` examples,
local command spelling and package hints, failure hints, explicit AI error help,
fuzzy history/file finding, app shortcuts, and new-command discovery after
installation. Vanilla chooses Bash; the store and stable command PATH remain.
AI chat is a separate Yes/No choice. The store offers the whole beginner bundle
and individual components, with a Disable menu for optional shell features.
Restart Fish after toggling features. Original user shell files are preserved.

For another device's acceptance test, use the distro installer's
`--profile vanilla --isolated-host --state-dir "$HOME/.local/state/agenticos-tablet-test"`.
This leaves host shell/PATH/configuration alone and keeps tgpt settings within
the test state. Required Termux packages and the X11 APK remain shared. Invoke
the test's explicit `state/bin` commands. See [tablet prompt](TABLET-TEST-PROMPT.md).

```sh
bash software.sh --plan tuipkg tgpt tgpt-tui beginner
bash software.sh --install tuipkg tgpt tgpt-tui beginner
bash software.sh --install fish shell-hints shell-fuzzy
bash software.sh --disable shell-theme
bash software.sh --install sgpt-tui cline kilo tgpt-mcp
bash software.sh --status
```

## Stable commands and updates

All managed command entry points live in `~/.local/state/agenticos/bin`, added to
Bash and Fish. The distro installer uses its chosen state directory instead.
Native npm agents live in `agents/<name>-<version>/`, Python apps in the store's
isolated `pipx/venvs/`, and tgpt in `tgpt/bin/`. There are no per-package exports
to remember and no global npm-prefix changes. Termux APT packages necessarily
remain under `$PREFIX`; their executable locations are stable package paths.
Existing user installs remain available outside the managed PATH.

Receipts record versions and file hashes. The store does not run automatic
upgrades. tgpt self-update is rejected by its managed wrapper. Native agents
use explicit pinned binaries rather than app-managed update caches. TermuxVoid
packages installed through the store receive APT holds. The store checks
receipts before launching. This is update management, not a filesystem security
boundary: explicit external npm/pipx commands or agent self-modification can
bypass it. Reinstall/repair from the store to restore its tested version.

TermuxVoid's AI catalog is a 2026-09-09 snapshot of 15 AI packages. The catalog
links to each package recipe, and fresh repository setup scopes its pinned key
with `signed-by`. Package postinst scripts can fetch newer upstream components;
an APT package version is not proof that every downloaded dependency is pinned.
Those tools are optional and individually unverified unless validation says otherwise.

## Chat and worker integration

`tgpt` retains the full CLI: providers, interactive mode, code/shell generation,
images, search and tools, subject to provider support. PowerBrain is the default
in `~/.config/agenticos/tgpt.conf`; `--provider` or the TUI can change it. Free
without a key, free tiers requiring a key, paid providers and local servers are
different categories. Availability, quotas and backend model identities can change.
An AI answer is not inherently a verified Google search.

`ask` opens natural-language chat: type `how do I clean cache?` at its prompt.
Normal Bash/Fish input remains command input. Mistyped commands receive local
hints without being sent to a remote provider. `err -e "error text"` explicitly
asks AI for an explanation. Alt+G drafts into the Fish input line for review.

`tgpt-mcp` adds the `tgpt_ask` worker to managed `opencode` via runtime inline
config. It overrides only the `tgpt` MCP entry; user/project config files and
provider credentials remain untouched. The adapter uses PowerBrain, no user
API key, a 60-second timeout, and no automatic fallback provider. Calls explicitly
send their prompt to PowerBrain. The existing user adapter remains on disk.

## Native runtime choices

Prefer the installed tested Termux tgpt 2.14.0 package, then the official APT
version. A checksum-verified native source build is the fallback. Native builds
use CGO and Termux Clang so DNS uses Android's resolver. The Android clipboard
patch uses OSC52; it does not require Termux:API.

Cline 3.0.61 uses the owner's glibc launcher plus per-process PRoot Bash binds
for `/bin/bash`, `/bin/sh`, and `/usr/bin/bash`. This avoids modifying Android's
system directories. Kilo 7.5.14 uses its glibc launcher with automatic updates
disabled. A managed glibc execution helper preserves argument boundaries that
the installed upstream runner lost; child Bash commands were tested. These are version-bound
ARM64 ports; startup/version checks alone do not prove every agent tool works.
Credentials are configured inside each app by its user, never bundled.

`--adopt sgpt cline kilo` snapshots the matching existing phone versions into
managed state before applying portable launchers. It does not copy provider
config into the repository. Do not use it for unverified versions.

Sources: [TermuxVoid recipes](https://github.com/termuxvoid/repo),
[tgpt](https://github.com/aandrew-me/tgpt),
[OpenCode config merging](https://opencode.ai/docs/config/),
[OpenCode MCP](https://opencode.ai/docs/mcp-servers/).
