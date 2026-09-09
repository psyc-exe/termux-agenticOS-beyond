#!/usr/bin/env python3
"""Resolve official Docker Hub tags to verified, native-platform digests. No extraction."""
import argparse
import hashlib
import json
import os
import re
import io
import sys
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path

ACCEPT = ", ".join((
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
))


def fetch(url, token=None):
    headers = {"Accept": ACCEPT, "User-Agent": "termux-linux-installer/1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as response:
        return response.read()


def checked_json(body, expected=None):
    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    if expected and digest != expected:
        raise ValueError("Registry content digest mismatch")
    return json.loads(body), digest


def choose_platform(index, architecture):
    for item in index.get("manifests", []):
        platform = item.get("platform", {})
        if platform.get("os") == "linux" and platform.get("architecture") == architecture:
            if platform.get("variant", "v8") == "v8" or architecture == "amd64":
                digest = item["digest"]
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                    raise ValueError("Unsupported digest")
                return digest
    raise ValueError(f"Publisher has no linux/{architecture} image; refusing cross-architecture fallback")


def resolve(spec, arch):
    repo, tag = spec["repository"], spec["tag"]
    query = urllib.parse.urlencode({"service": "registry.docker.io", "scope": f"repository:{repo}:pull"})
    token = json.loads(fetch("https://auth.docker.io/token?" + query))["token"]
    base = f"https://registry-1.docker.io/v2/{repo}"
    manifest, digest = checked_json(fetch(f"{base}/manifests/{tag}", token))
    if "manifests" in manifest:
        digest = choose_platform(manifest, arch)
        manifest, digest = checked_json(fetch(f"{base}/manifests/{digest}", token), digest)
    config_digest = manifest["config"]["digest"]
    config, _ = checked_json(fetch(f"{base}/blobs/{config_digest}", token), config_digest)
    if config.get("os") != "linux" or config.get("architecture") != arch:
        raise ValueError("Image config architecture does not match device")
    return {"repository": repo, "tag": tag, "architecture": arch, "digest": digest,
            "reference": f"{repo}@{digest}", "expected_os": spec["os_id"],
            "expected_version": spec["version"]}


def fetch_blob(base, descriptor, token, cache):
    digest = descriptor["digest"]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("Unsupported blob digest")
    destination = cache / digest.split(":")[1]
    if destination.exists():
        with destination.open("rb") as stream:
            actual = "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()
        if actual == digest and destination.stat().st_size == descriptor["size"]:
            return destination
    temporary = destination.with_suffix(".part")
    request = urllib.request.Request(f"{base}/blobs/{digest}", headers={"Authorization": "Bearer " + token})
    checksum, size = hashlib.sha256(), 0
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > descriptor["size"]:
                    raise ValueError("Blob exceeds declared size")
                checksum.update(chunk)
                stream.write(chunk)
        if size != descriptor["size"] or "sha256:" + checksum.hexdigest() != digest:
            raise ValueError("Blob size/digest mismatch")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def write_oci_archive(lock, manifest_body, blobs, output):
    manifest, digest = checked_json(manifest_body, lock["digest"])
    index = {"schemaVersion": 2, "manifests": [{
        "mediaType": manifest["mediaType"], "digest": digest, "size": len(manifest_body),
        "platform": {"os": "linux", "architecture": lock["architecture"]},
        "annotations": {"org.opencontainers.image.ref.name": lock["tag"]},
    }]}
    temporary = output.with_suffix(".part")
    def add_bytes(archive, name, content):
        entry = tarfile.TarInfo(name)
        entry.size, entry.mode = len(content), 0o644
        archive.addfile(entry, io.BytesIO(content))
    try:
        with tarfile.open(temporary, "w") as archive:
            add_bytes(archive, "oci-layout", b'{"imageLayoutVersion":"1.0.0"}')
            add_bytes(archive, "index.json", json.dumps(index).encode())
            add_bytes(archive, "blobs/sha256/" + digest.split(":")[1], manifest_body)
            for path in blobs:
                archive.add(path, arcname="blobs/sha256/" + path.name, recursive=False)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def download_archive(lock, output):
    # Current upstream's image reference parser does not accept repo@sha256 syntax.
    # Construct a verified OCI archive and use its documented local-image interface.
    repo = lock["repository"]
    query = urllib.parse.urlencode({"service": "registry.docker.io", "scope": f"repository:{repo}:pull"})
    token = json.loads(fetch("https://auth.docker.io/token?" + query))["token"]
    base = f"https://registry-1.docker.io/v2/{repo}"
    body = fetch(f'{base}/manifests/{lock["digest"]}', token)
    manifest, _ = checked_json(body, lock["digest"])
    cache = output.parent / "blobs"
    cache.mkdir(parents=True, exist_ok=True)
    blobs = []
    for descriptor in [manifest["config"], *manifest["layers"]]:
        print("Verifying/downloading " + descriptor["digest"], file=sys.stderr)
        path = fetch_blob(base, descriptor, token, cache)
        if path not in blobs:
            blobs.append(path)
    write_oci_archive(lock, body, blobs, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("image")
    parser.add_argument("architecture", choices=("arm64", "amd64"))
    parser.add_argument("lock", type=Path)
    parser.add_argument("--archive", type=Path, help="Download verified blobs and construct a local OCI archive")
    args = parser.parse_args()
    spec = json.loads(args.catalog.read_text())["images"][args.image]
    if args.lock.exists():
        result = json.loads(args.lock.read_text())
        if (result["repository"] != spec["repository"] or result["tag"] != spec["tag"]
                or result["architecture"] != args.architecture):
            raise ValueError("Existing image lock differs; use a new state directory")
        if not re.fullmatch(re.escape(spec["repository"]) + r"@sha256:[0-9a-f]{64}", result["reference"]):
            raise ValueError("Invalid lock reference")
    else:
        result = resolve(spec, args.architecture)
        args.lock.parent.mkdir(parents=True, exist_ok=True)
        temp = args.lock.with_suffix(".tmp")
        temp.write_text(json.dumps(result, indent=2) + "\n")
        os.replace(temp, args.lock)
    if args.archive:
        download_archive(result, args.archive)
        print(args.archive)
    else:
        print(result["reference"])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        sys.exit(f"Image resolution failed: {error}")
