#!/usr/bin/env bash
# Full tgpt interface, with a managed default and a protected Android build.
set -Eeuo pipefail
binary=$1
shift
config=${AGENTICOS_TGPT_CONFIG:-$HOME/.config/agenticos/tgpt.conf}
provider=powerbrain
if [[ -f $config ]]; then
    while IFS='=' read -r key value; do
        [[ $key != AI_PROVIDER ]] || provider=$value
    done < "$config"
fi
# Only interpret flags before the prompt / --, as Go's flag parser does.
for arg in "$@"; do
    case $arg in
        --) break;;
        -u|--update|-update|-u=*|--update=*|-update=*)
            echo 'tgpt update is locked: use a tested AgenticOS patch release.' >&2
            exit 2;;
    esac
done
[[ -f $config ]] || config=/dev/null
exec "$binary" --config "$config" --provider "$provider" "$@"
