import hashlib
import importlib.util
import json
import unittest
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("resolver", Path(__file__).resolve().parents[1] / "scripts/resolve-image.py")
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class ResolverTests(unittest.TestCase):
    def test_oci_archive_contains_verified_manifest_and_blobs(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            blob_data = b'{"architecture":"arm64","os":"linux"}'
            blob_hash = hashlib.sha256(blob_data).hexdigest()
            blob = directory / blob_hash
            blob.write_bytes(blob_data)
            manifest = json.dumps({"schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {"digest": "sha256:" + blob_hash, "size": len(blob_data)}, "layers": []}).encode()
            digest = "sha256:" + hashlib.sha256(manifest).hexdigest()
            output = directory / "image.oci.tar"
            resolver.write_oci_archive({"digest": digest, "architecture": "arm64", "tag": "test"}, manifest, [blob], output)
            with tarfile.open(output) as archive:
                index = json.load(archive.extractfile("index.json"))
                self.assertEqual(index["manifests"][0]["digest"], digest)
                for item in archive:
                    if item.name.startswith("blobs/sha256/"):
                        content = archive.extractfile(item).read()
                        self.assertEqual(hashlib.sha256(content).hexdigest(), item.name.rsplit("/", 1)[1])

    def test_digest_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            resolver.checked_json(b'{}', 'sha256:' + '0' * 64)

    def test_native_platform_only(self):
        index = {"manifests": [{"platform": {"os": "linux", "architecture": "amd64"}, "digest": "sha256:" + "a" * 64}]}
        with self.assertRaisesRegex(ValueError, "refusing cross-architecture"):
            resolver.choose_platform(index, "arm64")

    def test_attestation_is_not_a_platform(self):
        index = {"manifests": [
            {"platform": {"os": "unknown", "architecture": "arm64"}, "digest": "sha256:" + "b" * 64},
            {"platform": {"os": "linux", "architecture": "arm64", "variant": "v8"}, "digest": "sha256:" + "a" * 64},
        ]}
        self.assertEqual(resolver.choose_platform(index, "arm64"), "sha256:" + "a" * 64)

    def test_config_platform_is_independently_checked(self):
        config = json.dumps({"os": "linux", "architecture": "amd64"}).encode()
        digest = "sha256:" + hashlib.sha256(config).hexdigest()
        manifest = json.dumps({"config": {"digest": digest}}).encode()
        with patch.object(resolver, "fetch", side_effect=[b'{"token":"token"}', manifest, config]):
            with self.assertRaisesRegex(ValueError, "does not match"):
                resolver.resolve({"repository": "library/debian", "tag": "trixie"}, "arm64")

    def test_platform_manifest_hash_is_verified(self):
        index = json.dumps({"manifests": [{"platform": {"os": "linux", "architecture": "arm64"}, "digest": "sha256:" + "0" * 64}]}).encode()
        with patch.object(resolver, "fetch", side_effect=[b'{"token":"token"}', index, b'{}']):
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                resolver.resolve({"repository": "library/debian", "tag": "trixie"}, "arm64")


if __name__ == "__main__":
    unittest.main()
