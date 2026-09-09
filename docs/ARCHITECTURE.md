# Architecture

## Decision

Use one installer engine and two hosts: native Termux first, then a source-integrated Android app. Keep the stable base, security environment, Android privilege broker, and graphics host separate. Linux userspaces share Android's kernel; this is not a VM or bootable distribution.

~~~mermaid
flowchart TD
    A[Termux shell or integrated app] --> B[Validate and record selections]
    B --> C{check.root}
    C -->|UID 0 via su| D[Offer rooted or PRoot]
    C -->|Unavailable or denied| E[Non-root PRoot]
    D --> H{Native rootfs and private namespace pass?}
    H -->|yes| I[Native chroot base]
    H -->|no| J[Fallback or abort]
    B --> K[Debian or Ubuntu base]
    B --> L[Separate Kali or Parrot PRoot guest]
    K --> M[Native AI adapter or glibc guest CLIs]
    K --> N[CLI or XFCE]
    N --> O[Authenticated Unix X11 socket]
    O --> P[Termux:X11 Android surface]
~~~

## Execution model

| Backend | Authority | Execution cost | Limits |
|---|---|---|---|
| Native Termux | Android app UID, Bionic ABI | Native execution | Termux prefix rather than Linux FHS; glibc binaries incompatible |
| PRoot | Same app UID, emulated guest users | Syscall interception/path translation; more costly for metadata and subprocess workloads | No new kernel privileges or kernel-level isolation |
| Root chroot | Real root through su, subject to SELinux | Native syscalls after mount setup | Requires compatible kernel, root-owned rootfs, allowed mounts |
| unshare | Kernel capabilities and SELinux decide | Root mount isolation | Cannot presume unprivileged user namespaces are available |

There is no universal PRoot slowdown percentage. Benchmark identical cold/warm Git operations, dependency installs, subprocess-heavy builds, and CPU-only work. Shizuku does not remove PRoot overhead. [PRoot](https://proot-me.github.io/), [Shizuku introduction](https://shizuku.rikka.app/introduction/).

**check.root** runs su's id command with a timeout. Denial/timeout means root is unavailable to this session, not proof that the device is unrooted. Interactive setup offers the requested branches; noninteractive auto chooses PRoot without probing root. No SELinux changes or Android system remounts occur.

Shizuku is intentionally omitted: ADB shell access helps Android administration but does not turn Kali/Parrot PRoot sessions into privileged Linux sessions or unlock NetHunter kernel features. A root-started Shizuku service adds no necessary privilege beyond the already available su backend. Keep two modes: root and non-root. [Shizuku introduction](https://shizuku.rikka.app/introduction/).

## Selection and filesystems

The reviewed baseline is **Debian 13 Trixie** and **Ubuntu 26.04 LTS**. Release-specific tags avoid Ubuntu's unrestricted latest tag. Maintainers review new stable/LTS releases in the catalog; existing installations never silently cross a major release. [Debian releases](https://www.debian.org/releases/), [Ubuntu release notes](https://documentation.ubuntu.com/release-notes/26.04/).

The image resolver selects the native ARM64/AMD64 manifest, checks hashes and architecture, and persists a digest lock. It downloads digest-verified blobs and constructs a local OCI archive for PRoot-Distro to extract. This avoids upstream's current lack of repo@digest parsing. Cached layers, the OCI archive, and extracted files all consume storage. Kali/Parrot use their publisher images and their own signed APT repositories. Image locks and package inventories are separate records. [PRoot-Distro](https://github.com/termux/proot-distro), [Parrot images](https://www.parrotsec.org/docs/containers/parrot-on-docker/).

Never add Kali/Parrot sources to Debian/Ubuntu. Install a sibling rootfs and enter it from the host, avoiding nested PRoot. Separate homes keep package state and agent credentials apart. [Kali repository guidance](https://www.kali.org/docs/general-use/kali-apt-sources/).

| Footprint | Kali | Parrot |
|---|---|---|
| Minimal | Base utilities | Base utilities |
| Top 10 | kali-tools-top10 | Curated nmap, sqlmap, nikto, hydra, john, aircrack-ng, tcpdump, wireshark-common, gobuster, netcat-openbsd |
| Full | kali-linux-everything | parrot-tools-full |

Full means the publisher's metapackage including its normal recommendations. APT simulates the selection and fails visibly when unavailable; the installer never silently substitutes a smaller profile. Free-space admission floors are 4/12/40 GiB for minimal/top10/full, with additional GUI/cache headroom. These are planning floors, not measured download sizes. [Kali metapackages](https://www.kali.org/tools/kali-meta/), [Parrot editions](https://www.parrotsec.org/docs/introduction/download-parrot/).

This Kali userspace is not a complete NetHunter kernel/app installation. Monitor mode, injection, HID, raw sockets, and device drivers depend on the actual kernel and permissions. Neither root nor Shizuku supplies missing hardware/kernel support. [NetHunter editions](https://www.kali.org/docs/nethunter/).

## Agentic CLI integration

**Prefer native execution for a tested Android build; use the glibc base for Linux-first CLIs.** An npm entry point does not prove that all its native dependencies support Android.

| Path | Setup | Checks |
|---|---|---|
| Codex VL | Native, exact catalog version, state-local npm prefix | Binary version and native Bash subprocess |
| Cline/Kilo | Guest Node/glibc, dev-owned npm project and lock | Node >=20, both binary versions, FHS Bash subprocess |
| TermuxVoid | Optional third-party supply route, not enabled automatically | Repository key, source, ABI, versions, device tests |
| Native Cline forks | Candidate adapter | Additional Bun/native renderer dependencies need pinned evaluation |
| tgpt / PowerBrain | Independent Yes/No setup choice; pinned native Android Go build | Version smoke test; explicit provider and interactive/question shortcuts |

[Codex VL](https://github.com/DioNanos/codex-vl), [TermuxVoid](https://github.com/termuxvoid/repo), [Cline installation](https://docs.cline.bot/getting-started/installing-cline), [Kilo CLI](https://kilo.ai/docs/code-with-ai/platforms/cli), [Cline Termux fork](https://github.com/NeroBlackstone/cline-termux).

Do not create Android-wide /bin/bash symlinks. The guest already supplies FHS paths. A glibc runner outside PRoot must consistently resolve ELF interpreters, libraries, native helpers, and subprocess paths; patching the interpreter alone is not an ABI conversion. Scope loader variables and any FHS wrapper to one launcher. This installer uses a complete guest instead of introducing a second patched libc tree. A device-specific Kilo/PRoot failure is a compatibility signal, not proof that all devices fail. [Kilo Android issue](https://github.com/Kilo-Org/kilocode/issues/12445).

Agents use dev inside guests and never native root. Authenticate interactively; keep credentials in the selected private home. Startup checks do not prove OAuth callbacks, networking, actual tool execution, or sandbox compatibility. Do not silently disable a required sandbox or enable auto-approval. Loopback callbacks use Android's shared network stack.

Optional tgpt is a terminal help/chat feature, independent of coding-agent setup. It uses PowerBrain, which upstream lists as free and implements without a user-provided API key. Build the pinned module with Termux Go rather than assuming Linux release binaries are Android-compatible. The agenticos-chat shortcut opens interactive chat or accepts a question, fixes the provider, avoids inherited config/provider rotation, and does not enable command execution. Installation sends no prompts. The service requires internet and may be unavailable; this is not guaranteed web search or a verified model identity. [Provider source](https://github.com/aandrew-me/tgpt/blob/v2.14.0/src/providers/powerbrain/powerbrain.go).

The pinned v2.14.0 needs the Android clipboard adapter in patches/tgpt: its default clipboard dependency expects an Android JVM/app context, while native Termux is a standalone process. Apply the adapter to a checksum-verified source copy, then compile with CGO disabled. Command-copy uses terminal OSC 52; manual selection remains available. An Android ARM64 cross-build passes; device execution and provider connectivity remain separate gates.

## Desktop and GPU pipeline

The host owns X11 and optional VirGL processes. A foreground XFCE session owns its D-Bus session. PRoot shares the host temp directory; native chroot bind-mounts it inside a private namespace. X11 uses a random MIT cookie and disables TCP listening. Only launcher-owned processes are terminated. [Termux:X11](https://github.com/termux/termux-x11/blob/master/README.md).

Auto rendering tries **VirGL → Zink → LLVMpipe**, testing actual glxinfo output. A successful exit reporting zink over LLVMpipe is software. Guest Mesa/Vulkan packages come from the guest's repository; Bionic drivers cannot simply be copied into glibc.

- **Adreno:** Turnip/Zink needs the exact GPU, KGSL/DRM interface, build, and SELinux access to match. Repository Mesa may lack a usable Android KGSL backend. A tested glibc KGSL build belongs in the custom artifact channel.
- **Mali:** try host Android EGL through VirGL. Panfrost/PanVK need compatible kernel interfaces, which stock vendor drivers do not imply. Turnip is not a Mali driver.
- **Software:** require an LLVMpipe/softpipe renderer result. Missing display/software support stops startup with logs.

[Mesa Turnip](https://docs.mesa3d.org/drivers/freedreno.html), [Panfrost](https://docs.mesa3d.org/drivers/panfrost.html), [Android driver builds](https://docs.mesa3d.org/android.html), [Mesa environment controls](https://docs.mesa3d.org/envvars.html).

Use native X11 resolution and automatic orientation so surface resizing reaches XRandR. Set Xft DPI without changing Android's global density. DeX is treated as an Android external window/display; no forced display ID or DeX activation is assumed. Verify portrait/landscape, split screen, external attach/detach, IME, mouse, and keyboard on-device. Preference writes alone do not prove dynamic resizing. [X11 preferences](https://github.com/termux/termux-x11/blob/master/lorie/src/main/res/xml/preferences.xml).

## Operations

- Executables and rootfs remain in private storage. Optional shared storage maps only to /mnt/shared; its Unix permission/symlink behavior is unsuitable for a rootfs or npm project.
- APT retries network requests, waits on package locks, repairs interrupted configuration, suppresses service autostart with policy-rc.d, simulates tool selections, and audits installed packages. No deleted locks, forced dependencies, or disabled signatures.
- Run services in the foreground under a session supervisor, using high ports and loopback by default. There is no systemd PID 1 or normal boot sequence. Optional SSH/PostgreSQL support requires separate device testing.
- Android process limits, memory pressure, battery settings, and foreground-service restrictions still apply. Use a visible session notification and optional active-session wake lock; do not automatically weaken device settings.
- Logs, configuration, locks, and inventories stay local. Retry identical options after a package failure; different profiles use a new state directory. Back up before replacing rootfs or upgrading releases.
