#!/usr/bin/env bash
set -Eeuo pipefail
# Distribute with a release URL and independently verified digest.
[[ $# == 2 || $# == 3 ]] || { echo 'Usage: bash bootstrap.sh HTTPS_RELEASE_URL SHA256 [NEW_DESTINATION]' >&2; exit 64; }
url=$1 digest=$2
destination=$HOME/.local/share/termux-linux-release
if [[ $# == 3 ]]; then destination=$3; fi
[[ $url == https://* && $digest =~ ^[a-fA-F0-9]{64}$ ]] || exit 64
[[ $destination == "$HOME/"* && $destination != *..* && ! -e $destination ]] || {
    echo 'Use a new directory below private HOME.' >&2; exit 64;
}
for command in curl python sha256sum; do
    command -v "$command" >/dev/null || { echo 'First run: pkg install curl python coreutils' >&2; exit 1; }
done
umask 077
mkdir -p -- "$(dirname -- "$destination")"
stage=$(mktemp -d "$(dirname -- "$destination")/.termux-release.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
curl --fail --location --proto '=https' --proto-redir '=https' --retry 3 --max-time 600 "$url" -o "$stage/release.tar.gz"
printf '%s  %s\n' "$digest" "$stage/release.tar.gz" | sha256sum --check --status
python - "$stage" <<'PY'
import sys, tarfile
from pathlib import Path, PurePosixPath
stage = Path(sys.argv[1])
with tarfile.open(stage / "release.tar.gz") as archive:
    members = archive.getmembers()
    for member in members:
        path = PurePosixPath(member.name)
        if (path.is_absolute() or ".." in path.parts or not path.parts
                or path.parts[0] != "termux-linux" or not (member.isfile() or member.isdir())):
            raise SystemExit("Unsafe release archive entry")
    archive.extractall(stage, members=members, filter="data")
PY
test -f "$stage/termux-linux/install.sh"
mv -- "$stage/termux-linux" "$destination"
printf 'Verified release ready: %s\n' "$destination"
bash "$destination/install.sh"
