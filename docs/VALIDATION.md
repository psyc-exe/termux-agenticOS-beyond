# Verification and remaining device gates

Recorded 2026-09-09. Host: Windows, Git Bash 5.3.9, Python 3.14, ShellCheck 0.11.0. A Samsung SM-S921E (ARM64, Android SDK 36, Termux 0.119.0-beta.3) was subsequently accessed over authorized SSH for the native software-store checks below.

## Completed locally

- Bash syntax checks across installer, bootstrap, modules, guest scripts, launcher, tests, and root helper.
- ShellCheck warning-level checks; root helper additionally checked as POSIX sh.
- Shell assertions cover denied/false root, fallback/abort, removed Shizuku rejection, tgpt opt-in validation, explicit PowerBrain selection, prompt argument isolation, no inherited provider rotation, rendering fallbacks, guest bindings, and read-only planning.
- Python tests cover native platform selection, attestation exclusion, manifest/config mismatch rejection, OCI integrity, and tgpt source/checksum/patch preconditions.
- Live registry resolution of native ARM64 images for Debian, Ubuntu, Kali and Parrot.
- Real Debian ARM64 config/layer download into a local OCI archive, followed by independent descriptor size/hash verification. This is download-format evidence, not an Android installation pass.
- tgpt v2.14.0, module checksum pinned in the catalog: the original CGO-disabled Android build reproduced clipboard-backend errors. After the Android-only adapter, Go 1.26.5 successfully cross-built an Android ARM64 executable. The cross-built binary starts on Android, but its CGO-disabled DNS lookup fails. A native Termux Go 1.27.0 / Clang / CGO-enabled build passed startup and a real PowerBrain request. The existing Termux main repository tgpt 2.14.0 also passed a real PowerBrain request and is the managed installation used on this phone.

Live image locks:

| Publisher image | ARM64 manifest SHA-256 |
|---|---|
| library/debian:trixie-slim | 7215f78f35ffe58fe13f244fac9c4f21326d55187271fbb3e1a8aa5cc7e387ab |
| library/ubuntu:26.04 | 61b65dc6bddff5e68c552f22126fe77496395f956ff2e983e05d8a52efd63e55 |
| kalilinux/kali-rolling:latest | 15bbec1a8457c4e06037319d825dc54926c7d090cba2bd5a94dd99b8c41b3f38 |
| parrotsec/core:latest | bf75ecf3e201337845f13b8faf0b265c49f3ed17388ad8a75f47ae4319a01b86 |

These record this verification run, not permanent latest values. New installations resolve their own locks.

## Native phone checks completed

Samsung SM-S921E, ARM64, SDK 36, accessed over authorized SSH:

- The DietPi-style store rendered at 48 columns, opened its software checklist,
  cancelled back to its main menu and exited normally in a PTY.
- TUIPKG, tgpt-tui and sgpt-tui rendered their menus and exited normally. The
  tgpt TUI showed PowerBrain as the selected provider. This is keyboard/PTY
  evidence, not a physical touchscreen or Android lifecycle test.
- Real Fish startup loaded the optional integrations. tgpt, sgpt, Cline and Kilo
  resolved to the same managed `~/.local/state/agenticos/bin` directory. Existing
  pipx paths initially outranked it; `fish_add_path --move` fixed the conflict.
- The installed tgpt 2.14.0 is from Termux main, not TermuxVoid. Its copied native
  binary produced a real PowerBrain answer with no user API key.
- The MCP adapter completed initialize/tools-list/tools-call and returned
  `MCP PowerBrain OK`. Managed `opencode mcp list` reported `tgpt connected`.
- Managed Cline 3.0.61 and Kilo 7.5.14 start and print their expected versions.
  Their `upgrade` subcommands are blocked. Kilo's binary contains the
  `KILO_DISABLE_AUTOUPDATE` setting; the managed launcher enables it.
- A child `/bin/bash -c` call with a spaced payload returned `agent-shell-ok`
  under Cline's per-process FHS binds. The stock glibc runner split arguments;
  `bin/glibc-exec.sh` fixes this by forwarding the original argument array to
  the loader. Both agents still pass startup after that change.
- Existing shell-gpt 1.5.1 was snapshotted from pipx. Its Python source matches
  the official PyPI source; the custom TUI and local config supply its adaptations.
- Custom source copies exclude embedded provider credentials and private host
  addresses. Original phone app installations and provider configs remain intact.
- The first Fish setup attempt was interrupted by a development-time script
  replacement; it was rerun successfully from stable source. Fish advanced from
  4.9.2 to 4.9.3 during that package step. Final recipes skip already-installed
  prerequisites instead of unnecessarily upgrading them.

Host checks: 38 shell assertions, 20 Python tests, Bash syntax and ShellCheck.
The tests cover store plan validation, conflicting profiles, stable PATH setup,
receipt tamper detection, independent component disabling, pinned signing key,
MCP handshake/prompt isolation/failure handling, alongside existing distro tests.

## Full Android acceptance matrix — remaining

Test at least Android 12, 13, 14 and 15+, ARM64 Adreno and Mali, one Samsung DeX device, and one rooted device. AMD64 needs its own emulator/device pass.

| Gate | Required observable evidence |
|---|---|
| First installation | Base OS/version, successful APT, security metapackage/list, dpkg audit, shell launch |
| Retry | Interrupted download/package setup resumes safely; no duplicate or erased guest |
| Privileges | No su, denied su, successful su, chroot/mount denial, fallback abort |
| Native tgpt | Android build/startup, Yes/No setup, interactive chat, real PowerBrain response and unavailable-service behavior |
| APK Home role | Opt in/out, native Ask AI PTY, agent shortcuts, Home/resume, recovery and return to another launcher |
| Native chroot | Root-owned provisioned tree, namespace isolation, no host mount leak, dev-user shell |
| AI | Binary startup, authentication, a small authorized edit/test task, subprocess, network and sandbox behavior |
| GUI | Visible XFCE session and input, X11 cookie, renderer string, backend failure fallback |
| GPU | Adreno/Mali actual driver access, VirGL/Zink result, LLVMpipe fallback, no false acceleration claim |
| Display | Portrait/landscape resize, DPI, split screen, DeX attach/detach, IME/mouse/keyboard |
| Services | Foreground lifecycle, loopback socket access, no unintended externally listening service |
| Storage | Grant/deny, scoped binding, executable/rootfs kept private |
| Android lifecycle | Background/foreground, screen lock, low memory, stopped app, clean session restart |

Do not label this production-ready before those gates pass. Native rootfs provisioning, a tested custom KGSL artifact, integrated APK/API host adapters, and signed public release hosting are not delivered by this first script implementation.
