# Patch policy

Keep each patch with its upstream project, exact base commit, reason, affected ABI, regression test, and removal condition. Prefer upstream-supported options.

No speculative Bash symlink, loader, kernel, or SELinux patches are shipped. The glibc guest already supplies FHS paths. Panix is documented without copying its source.

The tested [tgpt Android clipboard adapter](tgpt/README.md) addresses an observed upstream build failure for standalone native terminals.
