# Paste into native OpenCode on the tablet

Use the user's selected Muse Spark 1.3 model. Do not change their model, provider,
credentials, existing Fish configuration, or OpenCode installation.

You are performing an on-device acceptance test of:
https://github.com/psyc-exe/termux-agenticOS-beyond

Install and test its **non-root PRoot path**, including Debian, XFCE/Termux:X11,
TUIPKG and native tgpt/TUI with PowerBrain. Work from native Termux, not from an
existing Linux guest. Keep commands and progress visible. Do not claim success
from logs alone when the test requires the user to see or interact with the GUI.

## Foreground execution

**First open a NEW Termux terminal session/tab and launch the test there.** Keep
OpenCode running in its original session. Use **Ctrl+Alt+C** to create the new
Termux tab, and **Ctrl+Alt+Down** to switch to the next tab. If you have an Android
UI-control tool, send those shortcuts to Termux and run the commands in the new
visible session. If you cannot operate that UI, ask me to press **Ctrl+Alt+C**
(or use the session drawer's **NEW SESSION**) and paste the foreground command
you provide. Do not pretend a background shell
tool is a new visible tab. After installation, launch the GUI from that new tab;
use another visible session when a concurrent check needs a terminal.

Use a visible Termux terminal session or an attached tmux pane. Run installation
in the foreground with `tee`, preserving the installer's exit status. Do not use
`nohup`, detached jobs, output suppression, or silently background the installer.
If your tool runner would background a long command, give me the exact foreground
command to run in a second Termux session, and inspect its log while I watch it.
The GUI launcher stays in that visible session; use another session for inspection.
Its internal X11 server process is expected, but do not detach the whole launcher.

## Protect the existing tablet setup

- Never use su, Shizuku, root chroot, or simulated escalation. PRoot's emulated
  root for guest package management is expected and is not Android root.
- Preserve existing Fish, aliases, themes, native npm/pipx installs, provider
  credentials, and current OpenCode configuration. Do not export secrets or copy
  them into a report. Do not apply the beginner bundle during this test.
- Use a fresh checkout and the unique state directory below. Never remove or
  repurpose another PRoot rootfs. If that state directory already exists, inspect
  it and choose a new suffix rather than deleting it.
- `--isolated-host` avoids global PATH, shell/RC, tgpt config and X11 preference
  changes. Required Termux packages remain shared; check their proposed changes
  and report them. Do not run a blanket `pkg upgrade` or install extra agents.
- Termux:X11's APK and its display socket are shared with the host. If display
  `:1` is already occupied, stop and report the collision; don't kill its owner.

## Prepare and install

1. Record Android API level, architecture, Termux version, free private storage,
   and current shell. Read the repository README, architecture, store guide and
   validation notes. Check that you are in native Termux and the device meets the
   installer's requirements. Do not treat existing phone tests as tablet passes.
2. Clone the repo into a fresh directory under Termux HOME. Record the exact Git
   commit tested. Keep source and rootfs off shared `/sdcard` storage.
3. Confirm the official Termux:X11 Android APK is installed and can be opened.
   The companion package alone is insufficient. If the APK is missing, give me
   its official upstream release link and wait for installation; don't substitute
   an unrelated APK or claim the GUI is ready.
4. In the visible terminal run the following Bash commands from the checkout:

```bash
bash
export TEST_STATE="$HOME/.local/state/agenticos-tablet-test"
export TEST_REPORT="$HOME/agenticos-tablet-test-report"
mkdir -p "$TEST_REPORT"
git rev-parse HEAD | tee "$TEST_REPORT/commit.txt"
set -o pipefail
bash install.sh --plan --mode proot --base debian --tools kali \
  --footprint minimal --ai none --tgpt yes --desktop xfce \
  --gpu software --profile vanilla --isolated-host --state-dir "$TEST_STATE"
bash install.sh --yes --mode proot --base debian --tools kali \
  --footprint minimal --ai none --tgpt yes --desktop xfce \
  --gpu software --profile vanilla --isolated-host --state-dir "$TEST_STATE" \
  2>&1 | tee "$TEST_REPORT/install.log"
printf 'installer exit: %s\n' "${PIPESTATUS[0]}"
```

Use the same recorded options for a retry. A changed setup identity requires a
different state directory. The Kali selection is a separate minimal security
guest; do not add Kali repositories to Debian or install full security suites.

## Acceptance checks

Run from native Termux using explicit state/bin paths; don't depend on the
tablet's old Fish aliases or global PATH to find the new build.

```bash
"$TEST_STATE/bin/linux" doctor 2>&1 | tee "$TEST_REPORT/doctor.log"
"$TEST_STATE/bin/linux" exec /bin/bash -lc \
  'cat /etc/os-release; id; printf "bash=%s\n" "$BASH_VERSION"; getent hosts deb.debian.org'
"$TEST_STATE/bin/agenticos-software"
"$TEST_STATE/bin/tuipkg"
"$TEST_STATE/bin/tgpt" --version </dev/null
"$TEST_STATE/bin/tgpt" --whole 'Reply with exactly: Tablet PowerBrain OK' </dev/null
"$TEST_STATE/bin/tgpt-tui"
"$TEST_STATE/bin/ask"
```

- Confirm the store renders, opens its checklist, cancels without installation,
  and exits. Confirm TUIPKG and tgpt-tui render and exit normally. Verify the
  tgpt TUI shows PowerBrain by default.
- In `ask`, type a plain question such as `how do I inspect cache size safely?`
  without a `tgpt` prefix. Confirm an answer, then exit chat back to the shell.
  Do not execute generated cleanup commands. PowerBrain is free without a user
  API key; do not substitute a paid provider or silently fall back if it fails.
- Verify `tgpt --update` is blocked without modifying its binary.
- Verify a new native Fish session still has the original shell/configuration
  and no newly added AgenticOS PATH/RC entries from this isolated installation.
- Keep runtime package failures separate from provider outages. Capture the
  actual error and exit code; never convert a failed request into a PASS.

Launch the desktop **in the foreground** from a visible session:

```bash
set -o pipefail
"$TEST_STATE/bin/linux" desktop 2>&1 | tee "$TEST_REPORT/desktop.log"
```

Open Termux:X11 if necessary. Ask me to confirm I can see XFCE, move the pointer,
open a terminal, and type. Test portrait/landscape and the on-screen keyboard.
Use split-screen or switch to the native Termux session for `ask`/`tgpt-tui`:
tgpt is deliberately native, not installed inside Debian. Do not claim a guest
terminal has native tgpt unless you implement and separately test a bridge.

Inspect `$TEST_STATE/logs/gpu-software.txt`; require an actual llvmpipe/softpipe
renderer. A running X11 process or socket alone does not prove a visible GUI.
Exit the session cleanly and relaunch once. Confirm the launcher cleans up its
own processes without touching pre-existing X11/PRoot sessions. Do not change
GPU mode mid-test; accelerated graphics are a separate follow-up.

## Results

Write a compact Markdown report under `$TEST_REPORT` containing the commit,
device versions, commands, PASS/FAIL/BLOCKED for each check, relevant log paths,
actual renderer, and my visual/input observations. Include reproducible failures
and material host package changes. Do not include credentials or private config.
You may diagnose and make narrow local fixes in the fresh checkout, but keep a
diff and rerun the affected check. Do not push or label the original build as
passing when only a locally modified version passes.

Finish with what works, what fails, and the next concrete fix. A missing APK,
missing visual confirmation, or provider outage is BLOCKED/FAIL as appropriate,
not a successful end-to-end install. Leave my original environment intact.
