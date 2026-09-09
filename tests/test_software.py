import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("store", ROOT / "scripts/software.py")
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


class SoftwareTests(unittest.TestCase):
    def test_plan_rejects_arbitrary_package_or_conflicting_shell(self):
        with self.assertRaises(ValueError):
            store.plan(["void:evil; touch file"])
        with self.assertRaises(ValueError):
            store.plan(["beginner", "vanilla"])

    def test_receipt_detects_changed_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary = root / "tgpt"
            binary.write_bytes(b"first build")
            with patch.object(store, "STATE", root):
                store.receipt("tgpt", [binary], "test")
                self.assertEqual(store.status("tgpt"), "installed / locked")
                binary.write_bytes(b"unreviewed replacement")
                self.assertTrue(store.status("tgpt").startswith("CHANGED"))

    def test_disable_preserves_other_components(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            enabled = root / ".config/agenticos/fish-enabled"
            enabled.parent.mkdir(parents=True)
            enabled.write_text("theme\nhints\nfuzzy\n")
            with patch.object(Path, "home", return_value=root):
                store.disable("shell-hints")
            self.assertEqual(enabled.read_text().splitlines(), ["theme", "fuzzy"])

    def test_activation_preserves_user_config_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prefix = root / "prefix"
            (prefix / "bin").mkdir(parents=True)
            state = root / "state"
            rc = root / ".bashrc"
            original = "# user config\nalias work='cd ~/project'\n"
            rc.write_text(original)
            with patch.object(Path, "home", return_value=root), patch.object(store, "PREFIX", prefix), patch.object(store, "STATE", state):
                store.activate()
                first = rc.read_text()
                store.activate()
            self.assertTrue(first.startswith(original))
            self.assertEqual(first, rc.read_text())
            self.assertEqual(first.count("# >>> agenticos PATH >>>"), 1)

    def test_void_key_matches_lock(self):
        self.assertEqual(store.digest(ROOT / "config/termuxvoid.gpg"), store.VOID["key_sha256"])

    def test_isolated_activation_leaves_host_files_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rc = root / ".bashrc"
            rc.write_text("original\n")
            with patch.object(Path, "home", return_value=root), patch.object(store, "STATE", root / "state"), patch.object(store, "ISOLATED", True):
                store.activate()
            self.assertEqual(rc.read_text(), "original\n")
            self.assertFalse((root / ".config/fish").exists())
            self.assertTrue((root / "state/bin/agenticos-software").exists())

    def test_isolated_tuipkg_uses_private_test_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(Path, "home", return_value=root), patch.object(store, "STATE", root / "state"), patch.object(store, "ISOLATED", True):
                store.install("tuipkg")
            wrapper = (root / "state/bin/tuipkg").read_text()
            self.assertIn("AGENTICOS_TUIPKG_CONFIG=", wrapper)
            self.assertIn("config/tuipkg", wrapper.replace("\\", "/"))
            self.assertFalse((root / ".config/tuipkg").exists())

    def test_phone_private_defaults_are_not_distributed(self):
        import re
        for p in (ROOT / "integrations").rglob("*.py"):
            self.assertIsNone(re.search(r"(?:sk_|sk-|freellmapi-)[A-Za-z0-9]{16,}", p.read_text(encoding="utf8")), str(p))


if __name__ == "__main__":
    unittest.main()
