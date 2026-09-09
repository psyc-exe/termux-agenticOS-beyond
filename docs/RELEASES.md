# Distribution, updates, and recovery

## Path 1 repository contract

The repository hosts installer code, a reviewed catalog, build recipes, and scoped patches. Official package managers remain the source of ordinary binaries. Custom builds belong in immutable release assets or a signed APT repository with source and compatibility metadata.

The project remote is [psyc-exe/termux-agenticOS-beyond](https://github.com/psyc-exe/termux-agenticOS-beyond). This implementation is prepared locally but has not been pushed, and no release endpoint exists yet. Build a source release:

~~~bash
python scripts/package-release.py dist/termux-linux-0.1.0.tar.gz
~~~

Publish the archive, hash, signing metadata, source, and evidence. The packager excludes the supplied video, .codex, caches, and state. Pin the release hash in the distributed entry point or first verify a detached signature against a separately provisioned project key.

~~~bash
bash bootstrap.sh https://YOUR-RELEASE-HOST/termux-linux-0.1.0.tar.gz VERIFIED_SHA256
~~~

This is a placeholder URL/hash, not a functioning release. The bootstrap follows HTTPS redirects only, checks the digest, rejects traversal/link/device entries, and extracts into a fresh private directory. A hash fetched from the same compromised endpoint is not independent authenticity proof.

## Latest versus repeatability

- Review stable/LTS changes in config/catalog.json; do not automatically follow Ubuntu interim releases.
- Resolve image tags once per installation. Verify blob sizes/hashes before constructing the local OCI archive.
- APT verifies signatures and uses current package candidates at install/retry time. Image locks do not pin subsequent APT repository state.
- Guest npm records a lock and uses npm ci on retries. Native Codex VL has an exact top-level version and local lock. Production promotion should test complete dependency locks.
- Native tgpt pins its module/version/checksum and preserves a patched build-source copy under state. Its optional clipboard adapter is source-controlled. Distribute corresponding GPL source/notices with any tgpt binary; the MIT license of this installer does not relicense tgpt.
- Use a new state directory/rootfs for a new major OS or changed profile. Test, migrate selected project files, then retire the previous environment.
- config/artifacts.json is intentionally empty; no unverified custom driver or libc download executes.

## Retry and recovery

State is installing, failed, or complete. A failed command records exit/line information. Only a successful image install writes its ownership marker. Matching options rerun package configuration without deleting rootfs.

An interruption after PRoot-Distro creates a container but before its marker is written deliberately requires inspection. Inspect the exact generated container name/image; then use a new state directory or back up/remove that specific failed container with PRoot-Distro. Unknown containers are never automatically adopted or erased.

Correct network, repository, disk, or package-state issues before retrying. No APT lock deletion or signature bypass occurs. Full toolchain failure stays a failure.

## Backups and lifecycle

Stop sessions before PRoot-Distro backups. Consult the installed version's backup help. Keep state/image/package records with backups and protect them as credentials.

The initial runtime provides foreground sessions and launcher-owned X11/VirGL cleanup. No boot daemons or Android process-limit changes are installed. To remove an environment, stop it, back it up, and use PRoot-Distro remove for the exact generated names before manually removing its state.

Native provisioning/removal belongs to the root administrator. Never recursively delete a mounted rootfs. A future APK service must expose start/stop/recovery and preserve the previous runtime until its replacement passes acceptance.
