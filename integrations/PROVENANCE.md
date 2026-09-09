# Imported custom integrations

Imported with the repository owner's request from their Termux installation on
2026-09-09. Private provider keys, proxy addresses, SSH shortcuts, project paths,
phone history and application credential files are not included.

- `tuipkg/`: owner's TUIPKG 0.1.0 source, MIT (`TUIPKG-LICENSE`). The application
  already supports terminal mouse events, portrait layouts, package scanning,
  command launching, and tldr/help examples.
- `tgpt-tui.py`, `sgpt-tui.py`: owner's Python terminal menus. Sanitized default
  credentials; tgpt uses separate AgenticOS config and defaults to PowerBrain.
  Provider capabilities and pricing labels are indicative upstream metadata,
  not promises of unlimited service or live search.
- `tgpt_mcp.py`: owner's stdio adapter, changed to explicit PowerBrain, bounded
  requests, stdin isolation, validated input and protected prompt arguments.
  It provides text answers; it cannot autonomously execute terminal commands.
- `fish/`, `fish.fish`, `starship.toml`: portable components derived from the
  owner's interactive Fish setup and Cyberdream prompt. No private proxy
  autostart, SSH passwords, or unrelated device/project aliases.
- `../patches/agents/`: owner's working Cline 3.0.61 and Kilo 7.5.14 launchers,
  based on their upstream packages, with runtime PREFIX resolution. Keep upstream
  package licenses when installing/distributing the original packages. The
  installer obtains packages separately; it does not redistribute their binaries.
  The derived launchers retain `patches/agents/cline-LICENSE` (Apache-2.0) and
  `patches/agents/kilo-LICENSE` (MIT), obtained from those exact npm versions.

The installed `shell-gpt` 1.5.1 Python files were compared against its official
PyPI source distribution: no differences. Its customization is currently in the
TUI and local provider configuration, rather than a core source patch. Existing
provider configuration remains on the phone and is reused locally, not vendored.

The custom Kilo repair script referenced a missing temporary `patch_kilo.py`.
The repository instead installs the pinned Linux ARM64 package explicitly and
uses the working launcher, bypassing that missing script and postinstall cache.
Both launchers can use the managed glibc helper. This fixes observed splitting
of prompts and shell-command arguments in glibc-runner 2.0's unquoted `$@` calls.
