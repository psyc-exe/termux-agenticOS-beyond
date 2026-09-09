# Path 2: one integrated APK

## Panix reference

Inspected Decentricity/Panix at commit **7b0f8dac047d44dd6ab05947e2403e657cc62226**, 2026-09-09. It is an implementation reference, not a verified production dependency here.

Panix demonstrates a distinct application ID, vendored X11 library, embedded surface activity, and X11 entry point loaded from its APK. It bundles Debian and PRoot. Its README describes an experimental release with acceptance work remaining. [Panix](https://github.com/Decentricity/Panix).

| Source evidence | Established pattern |
|---|---|
| [app/build.gradle](https://github.com/Decentricity/Panix/blob/7b0f8dac047d44dd6ab05947e2403e657cc62226/app/build.gradle) | Application ID io.github.decentricity.panix and conditional :lorie dependency |
| [PanixX11Bridge.java](https://github.com/Decentricity/Panix/blob/7b0f8dac047d44dd6ab05947e2403e657cc62226/app/src/main/java/com/termux/app/PanixX11Bridge.java) | X11 startup through app_process with the app APK classpath |
| [PanixRuntimeManager.java](https://github.com/Decentricity/Panix/blob/7b0f8dac047d44dd6ab05947e2403e657cc62226/app/src/main/java/com/termux/app/PanixRuntimeManager.java) | Runtime state machine and bundled payload/rootfs management |
| [build-proot-payload.sh](https://github.com/Decentricity/Panix/blob/7b0f8dac047d44dd6ab05947e2403e657cc62226/scripts/build-proot-payload.sh) | Selected verified Termux packages assembled into a small native payload |
| [Architecture](https://github.com/Decentricity/Panix/blob/7b0f8dac047d44dd6ab05947e2403e657cc62226/docs/ARCHITECTURE.md) | Single launcher/HOME integration and native library packaging |

Relocating a selected PRoot payload does not establish that every ordinary Termux package is relocatable. API preference classes do not establish a complete embedded Termux:API implementation.

## Packaging answer

**One install and one icon are feasible through source integration.** Storing three APKs as assets still leaves Android needing to install three packages before their services work. Scripts cannot replace those services or their permissions. Hiding launcher icons does not combine installed packages.

Path 1 needs Termux plus X11 for GUI; Termux:API is optional. Path 2 compiles terminal/runtime, X11, and selected device APIs into one project-owned package and signing identity. Internal components need no shared UID or companion APK.

## Proposed modules

~~~text
app-shell          setup/recovery UI; optional Android HOME role; terminal/X11 navigation
terminal-emulator  Termux terminal parsing and PTY support
terminal-view      terminal rendering and input
runtime-host       bootstrap, foreground service, child PIDs, cancellation, logs
x11-host           forked lorie and shell-loader; embedded surface activity
device-api         selected handlers and Android permission broker
privilege-broker   explicit su-backed root mode; non-root uses PRoot
installer-assets   shared scripts/catalog plus validated host adapter
~~~

Pass structured arguments rather than interpolating UI strings into shell commands. The foreground runtime service owns child processes and wake-lock lifecycle. Keep recovery outside the Linux desktop.

## Optional Linux Home launcher

Adopt the Panix pattern as an explicit APK setup option: **Use Linux desktop as Home: Yes/No**. Register a HOME/DEFAULT-capable activity and request Android's Home role/chooser only after initial runtime verification and a visible desktop launch. Declining leaves the app as a normal application.

The Home surface should offer large shortcuts for Terminal, coding agents, Ask AI (native tgpt), Android apps, and Settings. Ask AI opens the embedded native PTY with agenticos-chat. Agent buttons open their native or guest PTYs through the runtime host, without leaving the app. TUI mouse/touch support varies by tool: provide tap-to-focus, scrolling, selection/copy, and an extra-key row for Esc/Tab/arrows/Enter; do not promise every TUI is touch-friendly.

Use the embedded X11 surface for XFCE. Preserve sessions during Home presses, rotate/resize events, and DeX transitions. Always expose Stop/Restart Desktop and Change Home App outside the guest. If Linux fails to start, show the recovery dashboard rather than a blank Home screen.

This is a required optional feature of the planned APK, not an implemented Android launcher in the current Bash-only project. Path 1 cannot become a Home app through a shell script alone.

Start device-api with only needed features: storage selection, clipboard, notifications, battery and display information. Refactor API command clients to reach internal handlers. Request each permission at its point of use. Internal components should be non-exported or narrowly signature-protected. Do not expose arbitrary privileged execution to guests. [Termux:API](https://github.com/termux/termux-api).

## Package-prefix decision

Use a new project-owned application ID so official Termux can coexist. Rebuild the native bootstrap and required package channel for its private prefix, auditing shebangs, ELF paths, library lookup, JNI names, and native helpers. Setting an environment variable cannot rewrite compiled package paths. [Termux fork guidance](https://github.com/termux/termux-app#forking).

Two viable payload strategies:

1. **Full Termux package support:** rebuild the native bootstrap/package set for the new prefix. This preserves the shared installer's pkg workflow and native AI path.
2. **Panix-style minimal host:** bundle tested PRoot/X11/helpers and use guest APT for tools. This reduces the native rebuild surface but requires a host adapter; the current installer cannot run unchanged without pkg, Python, coreutils, and compatible PRoot-Distro.

Retaining com.termux avoids a new prefix but conflicts with official Termux and its signing identity. Public debug keys are unsuitable for a production signing strategy.

## Shared script contract

The app supplies executable Bash, Python, curl, PRoot-Distro, core utilities, a package installer, private HOME/PREFIX, and writable temp storage. Replace the stock X11 activity launch in lib/display.sh with the embedded surface, supply a preference bridge, and route storage setup into the app's permission UI. Package a tested native tgpt build for the optional Ask AI shortcut; no Shizuku component is required.

This repository implements the **stock Termux host**. The APK components are a technical design, not a compiled app; an Android build and device testing are still required.

## Distribution gates

Pin terminal/X11/API commits together with the script/catalog version. Build ARM64 first. Verify native-library loading and 16-KiB page-size compatibility on applicable devices. Test target-SDK changes against Android executable-file, dynamic loading, foreground-service, notification, and background-launch restrictions; raising a legacy target can require runtime changes.

Use a project release key, publish corresponding source/notices and dependency inventory, and record APK certificate/artifact hashes. Choose a small online installer APK or a larger offline bundle. Downloaded dependencies must be verified before extraction. Upstream merges must rerun the device matrix in VALIDATION.md.
