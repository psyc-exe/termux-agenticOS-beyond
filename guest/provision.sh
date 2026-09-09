#!/usr/bin/env bash
set -Eeuo pipefail
role=$1 expected=$2 version=$3 footprint=$4 desktop=$5 ai=$6
source /etc/os-release
[[ $ID == "$expected" ]] || { echo "Wrong OS: wanted $expected, got $ID" >&2; exit 1; }
[[ $version == rolling || ${VERSION_ID:-} == "$version" ]] || { echo "Wrong release: expected $version" >&2; exit 1; }
export DEBIAN_FRONTEND=noninteractive
# Prevent daemon launch by package scripts; this rootfs is managed without PID 1.
if [[ ! -e /usr/sbin/policy-rc.d ]]; then
    printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
    chmod 755 /usr/sbin/policy-rc.d
fi
mkdir -p /var/lib/termux-linux /etc/apt/apt.conf.d
cat > /etc/apt/apt.conf.d/90termux-linux <<'EOF'
Acquire::Retries "3";
Acquire::http::Timeout "45";
Acquire::https::Timeout "45";
DPkg::Lock::Timeout "120";
EOF
# Deliberately no trusted=yes, keyserver key retrieval, forced dependencies, or lock deletion.
dpkg --configure -a
apt-get update
apt-get install -y --no-install-recommends ca-certificates locales bash curl git procps \
    iproute2 dnsutils nano less util-linux passwd python3 python3-venv
if ! id dev >/dev/null 2>&1; then useradd -m -s /bin/bash dev; fi
mkdir -p /home/dev/projects /mnt/shared
chown dev:dev /home/dev/projects
if [[ $role == tools ]]; then
    packages=()
    case "$expected:$footprint" in
        kali:minimal|parrot:minimal) ;;
        kali:top10) packages=(kali-tools-top10);;
        kali:full) packages=(kali-linux-everything);;
        parrot:top10) packages=(nmap sqlmap nikto hydra john aircrack-ng tcpdump wireshark-common gobuster netcat-openbsd);;
        parrot:full) packages=(parrot-tools-full);;
        *) echo 'Unsupported profile' >&2; exit 1;;
    esac
    if ((${#packages[@]})); then
        apt-get -s install "${packages[@]}" > /var/lib/termux-linux/toolchain-plan.txt
        apt-get install -y "${packages[@]}"
        for package in "${packages[@]}"; do
            [[ $(dpkg-query -W -f='${Status}' "$package") == 'install ok installed' ]]
        done
    fi
fi
if [[ $role == base && $desktop == xfce ]]; then
    apt-get install -y --no-install-recommends xfce4 xfce4-terminal dbus-x11 mesa-utils mesa-vulkan-drivers x11-xserver-utils xauth
fi
if [[ $role == base && $ai == distro ]]; then
    apt-get install -y --no-install-recommends nodejs npm build-essential ripgrep
fi
printf 'LANG=C.UTF-8\n' > /etc/default/locale
dpkg --audit > /var/lib/termux-linux/dpkg-audit.txt
[[ ! -s /var/lib/termux-linux/dpkg-audit.txt ]] || { cat /var/lib/termux-linux/dpkg-audit.txt; exit 1; }
dpkg-query -W > /var/lib/termux-linux/packages.tsv
printf '%s\n' "$expected:$version $role $footprint" > /var/lib/termux-linux/profile
