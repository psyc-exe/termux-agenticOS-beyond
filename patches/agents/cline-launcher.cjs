#!/usr/bin/env node
const termuxPrefix = process.env.PREFIX;
if (!termuxPrefix) throw new Error("PREFIX is required");

// Binary resolver for Cline CLI.
//
// This script runs with Node.js (available everywhere npm is) and finds the
// correct platform-specific compiled binary to execute. The compiled binary
// has Bun embedded, so users don't need Bun installed.
//
// Resolution order:
// 1. CLINE_BIN_PATH env var override
// 2. Cached binary at bin/.cline (created by postinstall)
// 3. Walk up node_modules to find the platform-specific package

const childProcess = require("child_process");
const fs = require("fs");
const path = require("path");
const os = require("os");

const scriptPath = fs.realpathSync(__filename);
const scriptDir = path.dirname(scriptPath);
const childEnv = {
	...process.env,
	CLINE_WRAPPER_PATH: scriptPath,
};

// Auto-discover OS trust anchors and pass them to the Bun child via
// NODE_EXTRA_CA_CERTS. The Bun runtime does not read the OS store on its own,
// so corporate/self-signed CAs would otherwise fail. This wrapper runs on
// Node, which can read the full store here.
try {
	const caCerts = require("./ca-certs.cjs");
	const outcome = caCerts.configureNodeExtraCaCerts(childEnv);
	const debug =
		process.env.CLINE_DEBUG === "1" || process.env.CLINE_DEBUG === "true";
	// Not debug-gated: on old Nodes the harvest silently doing nothing is
	// indistinguishable from a broken corporate proxy. Stamped per Node
	// version so the nudge shows once, not on every command.
	if (
		outcome &&
		outcome.action === "api-unavailable" &&
		!childEnv.NODE_EXTRA_CA_CERTS &&
		caCerts.shouldWarnApiUnavailable(childEnv)
	) {
		console.warn(
			`[cline] Node ${process.versions.node} cannot read the OS trust store (needs >= 22.15); ` +
				"corporate or self-signed CAs may fail TLS. Upgrade Node or set NODE_EXTRA_CA_CERTS.",
		);
	}
	if (debug && outcome) {
		if (outcome.action === "no-system-certs") {
			console.warn(
				"[cline] No OS trust anchors found; relying on the runtime's bundled CAs.",
			);
		} else if (outcome.action === "write-failed") {
			console.warn(
				"[cline] Could not write the managed CA bundle; relying on the runtime's bundled CAs.",
			);
		} else {
			console.warn(
				`[cline] Trust: ${outcome.systemCertCount} OS + ${outcome.userCertCount} user CAs (${outcome.action}) -> ${outcome.path}`,
			);
		}
	}
} catch {
	// Best effort: fall back to the runtime's default trust on any failure.
}

function run(target) {
	// Termux Android: glibc binary needs glibc-runner + /bin/bash visibility (fix-cline.md Method 1)
	let execTarget = target;
	let execArgs = process.argv.slice(2);
	if (os.platform() === "android") {
		const proot = (termuxPrefix + "/bin/proot");
		const termuxBash = (termuxPrefix + "/bin/bash");
		const termuxFish = (termuxPrefix + "/bin/fish");
		const termuxSh = (termuxPrefix + "/bin/sh");
		const glibcBash = (termuxPrefix + "/glibc/bin/bash");
		const glibcRunner = process.env.AGENTICOS_GLIBC_RUNNER || (termuxPrefix + "/bin/glibc-runner");
		const ldso = (termuxPrefix + "/glibc/lib/ld-linux-aarch64.so.1");
		const needProot = !fs.existsSync("/bin/bash") && fs.existsSync(termuxBash) && fs.existsSync(proot);
		if (needProot) {
			// Proot bind exposes Termux shells at /bin/* for glibc binary's child spawns.
			// Keeps host env intact (no -r), only adds bind mounts.
			const bashSrc = fs.existsSync(glibcBash) ? glibcBash : termuxBash;
			const binds = [];
			if (fs.existsSync(bashSrc)) binds.push("-b", `${bashSrc}:/bin/bash`, "-b", `${bashSrc}:/bin/sh`);
			if (fs.existsSync(termuxFish)) binds.push("-b", `${termuxFish}:/bin/fish`);
			// Also ensure /usr/bin/bash visible for scripts that expect it
			if (fs.existsSync(bashSrc)) binds.push("-b", `${bashSrc}:/usr/bin/bash`);
			if (fs.existsSync(glibcRunner)) {
				execTarget = proot;
				execArgs = [...binds, glibcRunner, target, ...execArgs];
			} else if (fs.existsSync(ldso)) {
				execTarget = proot;
				execArgs = [...binds, ldso, "--library-path", (termuxPrefix + "/glibc/lib"), target, ...execArgs];
			}
		} else if (fs.existsSync(glibcRunner)) {
			execTarget = glibcRunner;
			execArgs = [target, ...execArgs];
		} else if (fs.existsSync(ldso)) {
			execTarget = ldso;
			execArgs = ["--library-path", (termuxPrefix + "/glibc/lib"), target, ...execArgs];
		}
	}
	const result = childProcess.spawnSync(execTarget, execArgs, {
		stdio: "inherit",
		env: childEnv,
	});
	if (result.error) {
		console.error(result.error.message);
		// Windows application control (Smart App Control, WDAC, AppLocker)
		// blocks the child exe at launch, which Node surfaces only as an
		// opaque "spawnSync ... UNKNOWN" error. Point users at the real cause.
		const code = result.error.code;
		if (
			os.platform() === "win32" &&
			(code === "UNKNOWN" || code === "EACCES" || code === "EPERM")
		) {
			console.error(
				"\nWindows refused to start the Cline binary:\n  " +
					target +
					"\n\n" +
					"This usually means an application control policy (Smart App Control,\n" +
					"WDAC, or AppLocker) or antivirus blocked the executable. To confirm,\n" +
					"run the path above directly in a terminal and check the error Windows\n" +
					"reports, or inspect its signature with:\n\n" +
					'  Get-AuthenticodeSignature "' +
					target +
					'"\n\n' +
					"If it was blocked by policy, allow the file or ask your administrator\n" +
					"to trust it. See https://github.com/cline/cline/issues for known issues.",
			);
		}
		process.exit(1);
	}
	if (typeof result.status === "number") {
		process.exit(result.status);
	}
	if (result.signal) {
		process.kill(process.pid, result.signal);
		process.exit(128);
	}
	process.exit(1);
}

// 1. Check env var override
const envPath = process.env.CLINE_BIN_PATH;
if (envPath) {
	run(envPath);
}

// 2. Check cached binary
const cached = path.join(scriptDir, ".cline");
if (fs.existsSync(cached)) {
	run(cached);
}

// 3. Detect platform and architecture
const platformMap = {
	darwin: "darwin",
	linux: "linux",
	android: "linux",
	win32: "windows",
};
const archMap = {
	x64: "x64",
	arm64: "arm64",
};

let platform = platformMap[os.platform()];
if (!platform) {
	platform = os.platform();
}
let arch = archMap[os.arch()];
if (!arch) {
	arch = os.arch();
}

const base = "@cline/cli-" + platform + "-" + arch;
const binary = platform === "windows" ? "cline.exe" : "cline";

// Build fallback chain of package names to try
const names = [base];

function findBinary(startDir) {
	let current = startDir;
	for (;;) {
		const modules = path.join(current, "node_modules");
		if (fs.existsSync(modules)) {
			for (const name of names) {
				// Scoped package: @cline/cli-darwin-arm64 lives at
				// node_modules/@cline/cli-darwin-arm64
				const candidate = path.join(modules, name, "bin", binary);
				if (fs.existsSync(candidate)) return candidate;
			}
		}
		const parent = path.dirname(current);
		if (parent === current) {
			return undefined;
		}
		current = parent;
	}
}

const resolved = findBinary(scriptDir);
if (!resolved) {
	console.error(
		"Could not find the Cline CLI binary for your platform.\n" +
			"Your platform: " +
			os.platform() +
			" " +
			os.arch() +
			"\n" +
			"Looked for: " +
			names.map(function (n) {
				return '"' + n + '"';
			}).join(" or ") +
			"\n\n" +
			"Try reinstalling: npm install -g cline",
	);
	process.exit(1);
}

run(resolved);
