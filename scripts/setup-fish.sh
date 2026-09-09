#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
STATE_DIR=${AGENTICOS_STATE:-$HOME/.local/state/agenticos}
feature=${1:-core}
packages() { bash "$ROOT_DIR/scripts/ensure-packages.sh" "$@"; }
case $feature in
    core) packages fish;;
    theme) packages starship;;
    aliases) packages eza bat;;
    hints) packages tealdeer command-not-found;;
    fuzzy) packages fzf fd bat;;
    discovery) :;;
    *) printf 'Unknown Fish component\n' >&2; exit 2;;
esac
mkdir -p "$HOME/.config/fish/conf.d" "$STATE_DIR/backups"
target=$HOME/.config/fish/conf.d/agenticos.fish
if [[ -f $target ]]; then cp -p -- "$target" "$STATE_DIR/backups/agenticos.fish.$(date +%s)"; fi
# JSON string syntax is not Fish syntax. Escape Fish single quoted literals directly.
python - "$ROOT_DIR" "$STATE_DIR" "$target" <<'PY'
from pathlib import Path
import sys
def quote(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"
root, state, target = sys.argv[1:]
Path(target).write_text('''# Managed AgenticOS profile; remove this file to disable.
status is-interactive; or return
set -gx AGENTICOS_ROOT ''' + quote(root) + '''
set -gx AGENTICOS_STATE ''' + quote(state) + '''
function __agenticos_load --on-event fish_prompt
    source $AGENTICOS_ROOT/integrations/fish.fish
    functions -e __agenticos_load
end
''')
PY
fish --no-config --no-execute "$target"
fish --no-config --no-execute "$ROOT_DIR/integrations/fish.fish"
if [[ $feature == theme ]]; then
    # Theme has its own config, so toggling it does not overwrite the user's prompt file.
    mkdir -p "$HOME/.config/agenticos"
    cp -- "$ROOT_DIR/integrations/starship.toml" "$HOME/.config/agenticos/starship.toml"
fi
if [[ $feature != core ]]; then
    mkdir -p "$HOME/.config/agenticos"
    touch "$HOME/.config/agenticos/fish-enabled"
    if ! grep -Fxq "$feature" "$HOME/.config/agenticos/fish-enabled"; then
        printf '%s\n' "$feature" >> "$HOME/.config/agenticos/fish-enabled"
    fi
fi
if [[ $feature == hints ]]; then
    timeout 30 tldr --update || printf 'tldr cache update failed; retry with tldr --update when online.\n'
fi
printf 'Fish integration ready. Start fish; helpme shows shortcuts. Existing login shell is preserved.\n'
