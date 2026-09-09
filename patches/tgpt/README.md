# tgpt v2.14.0 Android terminal clipboard adapter

Upstream tag: v2.14.0, commit c61a79c50aeec94582774f4c41382d10e254a09b.
Module checksum is pinned in config/catalog.json and checked before copying source.

The upstream clipboard_other.go includes Android and imports golang.design/x/clipboard. Its Android backend expects cgo plus a Go-mobile JVM/app context; a standalone Termux CLI does not provide that context. A CGO-disabled Android build fails with undefined clipboard backend symbols.

scripts/prepare-tgpt.py excludes Android from that file and adds clipboard_android.go. Command-copy requests use the terminal's OSC 52 protocol with bounded, base64-encoded text. Unsupported terminals still permit manual selection. Normal chat does not require clipboard APIs. Upstream's separate TUI clipboard shortcuts need device verification.

All other tgpt/provider code stays unchanged. Remove this adapter when upstream supports standalone Android terminals. Native builds use CGO_ENABLED=1 with Termux Clang (Android DNS resolver), GOOS=android, the pinned module and its go.sum. Source remains governed by upstream's GPL-3.0 license; distribute corresponding patched source and notices with any binary APK/release.
