#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
STATE_DIR=${AGENTICOS_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/agenticos}
TGPT=yes
source "$ROOT_DIR/lib/common.sh"
source "$ROOT_DIR/lib/tgpt.sh"
mkdir -p "$STATE_DIR/bin" "$STATE_DIR/logs"
setup_tgpt
