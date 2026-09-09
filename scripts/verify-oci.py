#!/usr/bin/env python3
"""Read-only hash/size validation of a local OCI archive; never extracts guest files."""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("archive", type=Path)
args = parser.parse_args()
with tarfile.open(args.archive) as archive:
    index = json.load(archive.extractfile("index.json"))
    count = 0
    def read_checked(descriptor):
        global count
        path = "blobs/" + descriptor["digest"].replace(":", "/")
        member = archive.getmember(path)
        if member.size != descriptor["size"]:
            raise SystemExit("Size mismatch: " + path)
        with archive.extractfile(member) as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if "sha256:" + digest != descriptor["digest"]:
            raise SystemExit("Hash mismatch: " + path)
        count += 1
        return path
    for descriptor in index["manifests"]:
        path = read_checked(descriptor)
        manifest = json.load(archive.extractfile(path))
        config_path = read_checked(manifest["config"])
        config = json.load(archive.extractfile(config_path))
        print("Platform:", config["os"] + "/" + config["architecture"])
        for layer in manifest["layers"]:
            read_checked(layer)
    print("Verified descriptors:", count)
