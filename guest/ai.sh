#!/usr/bin/env bash
set -Eeuo pipefail
unset LD_PRELOAD LD_LIBRARY_PATH
export SHELL=/bin/bash
test -x /bin/bash && test -x /usr/bin/bash
node -e 'if (+process.versions.node.split(".")[0] < 20) process.exit(1)'
mkdir -p "$HOME/.local/share/termux-linux-ai"
cd "$HOME/.local/share/termux-linux-ai"
# npm saves exact top-level versions and integrity-checked transitive dependencies.
# Re-runs use the lock and do not move to a newer release.
if [[ -f package-lock.json ]]; then
    npm ci
else
    npm init -y >/dev/null
    npm install --save-exact cline @kilocode/cli
fi
timeout 30 node_modules/.bin/cline --version
timeout 30 node_modules/.bin/kilo --version
node -e 'require("child_process").execFileSync("/bin/bash",["-c","printf glibc-shell-ok"],{stdio:"inherit"})'
printf '\nAuthenticate interactively with linux ai cline or linux ai kilo.\n'
