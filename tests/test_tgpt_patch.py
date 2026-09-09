import importlib.util
import tempfile
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tgpt_patch", root / "scripts/prepare-tgpt.py")
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


class TgptPatchTests(unittest.TestCase):
    def test_wrong_source_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "output"
            with self.assertRaisesRegex(ValueError, "checksum"):
                patcher.prepare({"Path": "module", "Version": "v1", "Sum": "wrong"},
                    {"ai": {"tgpt": "module@v1", "tgpt_sum": "expected"}}, target, Path("unused"))
            self.assertFalse(target.exists())

    def test_only_android_constraints_change_and_cache_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "cache"
            source_file = source / "src/clipboard/clipboard_other.go"
            source_file.parent.mkdir(parents=True)
            original = "//go:build !freebsd\n// +build !freebsd\n\npackage clipboard\n"
            source_file.write_text(original)
            metadata = {"Path": "module", "Version": "v1", "Sum": "expected", "Dir": str(source)}
            catalog = {"ai": {"tgpt": "module@v1", "tgpt_sum": "expected"}}
            output = directory / "output"
            patcher.prepare(metadata, catalog, output, root / "patches/tgpt/clipboard_android.go")
            self.assertEqual(source_file.read_text(), original)
            self.assertIn("!freebsd && !android", (output / "src/clipboard/clipboard_other.go").read_text())
            self.assertTrue((output / "src/clipboard/clipboard_android.go").is_file())
            with self.assertRaisesRegex(ValueError, "fresh"):
                patcher.prepare(metadata, catalog, output, Path("unused"))


if __name__ == "__main__":
    unittest.main()
