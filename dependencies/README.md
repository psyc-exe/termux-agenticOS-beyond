# Custom artifacts

No custom binary/driver is currently required for the default software/PRoot path.

Host reproducible custom builds as release assets or a signed package repository, not opaque binaries committed without source. config/artifacts.json is reserved for reviewed entries with name, version, ABI, guest distribution, HTTPS URL, SHA-256, source commit, build recipe, license, and device compatibility evidence.

Potential entries: a guest-glibc KGSL Turnip build, a native Android agent adapter, or a prefix-specific Termux bootstrap. Do not install an Android/Bionic library into a glibc guest. Do not invent hashes or mark untested GPU families supported.

This first installer does not execute custom artifact entries. Add a tested adapter and acceptance checks before enabling one. Ordinary dependencies use their package managers.
