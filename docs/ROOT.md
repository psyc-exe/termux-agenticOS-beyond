# Native root backend

The current script **does not automatically provision a native rootfs**. It accepts an administrator-provisioned filesystem with --rootfs. PRoot is the complete automated installation path.

Do not chroot into a PRoot-Distro tree: app ownership, emulated users, and .l2s hard-link substitutions have different semantics. Native provisioning must retain real numeric ownership.

## Provisioning contract

1. On a trusted Linux host, select the architecture-specific official base digest resolved by scripts/resolve-image.py.
2. Create a stopped Docker/Podman container from that digest and export its filesystem. Record image digest and archive SHA-256 in the release manifest. No guest package scripts need to execute simply to export it.
3. Verify the release manifest and archive hash on the rooted device. Using the root administrator's provisioning tool, extract into a **fresh**, root-owned directory directly below /data/local/termux-linux/, mode 0755, preserving numeric ownership. Never extract over an active guest.
4. Ensure real /dev, /proc, /sys and /tmp directories exist, /tmp has mode 1777, and the guest resolver is configured for the device network. Do not overwrite a resolver symlink through the host filesystem.
5. From the ordinary Termux app user:

~~~bash
bash install.sh --mode root --rootfs /data/local/termux-linux/debian13 \
  --base debian --fallback abort
~~~

The helper checks root identity, canonical path, root-owned non-writable root/parent, mount targets, absence of .l2s, and a chroot test in a private namespace. It does not disable SELinux. The entire supplied rootfs must be trusted; structural checks are not an authenticity audit.

Each session mounts Android /dev, /proc, /sys and Termux temp only in its private namespace. The namespace disappears after its last process exits. Keep services in the foreground. Real device bindings and native root mean this is not a sandbox for hostile software.

Native execution applies to the base only; security guests stay PRoot. Native shared-storage binding is not implemented; --storage maps PRoot guests only.

If namespace, chroot, ABI, mounts, or SELinux checks fail, --fallback proot continues with a PRoot base and reports the downgrade. Use --fallback abort when native execution is mandatory. Automated native provisioning and raw-device capabilities remain release gates.
