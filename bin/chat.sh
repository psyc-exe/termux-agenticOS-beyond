#!/usr/bin/env bash
set -Eeuo pipefail
binary=$1
shift
[[ -x $binary ]] || { echo 'tgpt is unavailable; rerun setup with --tgpt yes.' >&2; exit 1; }
# Keep provider selection explicit. Do not rotate to another service automatically.
unset AI_ROTATE_PROVIDERS AI_API_KEY
if (($#)); then
    # Treat arguments as question text, including anything resembling CLI options.
    # Prefix also prevents upstream's manual --config scan from interpreting the question.
    exec "$binary" --config /dev/null --provider powerbrain -- "Question: $*"
fi
printf 'PowerBrain online chat. Questions are sent to the provider. Ctrl+C to leave.\n' >&2
exec "$binary" --config /dev/null --provider powerbrain --interactive
