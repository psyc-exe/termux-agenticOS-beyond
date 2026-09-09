import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tgpt_mcp", ROOT / "integrations/tgpt_mcp.py")
mcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp)


class McpTests(unittest.TestCase):
    def test_handshake_and_tools(self):
        response = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(response["result"]["serverInfo"]["name"], "tgpt-mcp")
        self.assertEqual(mcp.handle({"id": 2, "method": "tools/list"})["result"]["tools"][0]["name"], "tgpt_ask")
        self.assertIsNone(mcp.handle({"method": "notifications/initialized"}))

    def test_prompt_cannot_become_a_tgpt_flag(self):
        with patch.object(mcp.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "answer", "")) as run:
            result = mcp.run_tgpt({"prompt": "--config=/private/file"})
        self.assertEqual(run.call_args.args[0][-2:], ["--", "Question: --config=/private/file"])
        self.assertIn("powerbrain", run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(result["content"][0]["text"], "answer")

    def test_invalid_input_does_not_start_a_process(self):
        with patch.object(mcp.subprocess, "run") as run:
            for payload in ({}, {"prompt": []}, {"prompt": "hi", "model": []}, {"prompt": "hi", "model": "--config=/private"}):
                self.assertTrue(mcp.run_tgpt(payload)["isError"])
            run.assert_not_called()

    def test_provider_failure_is_not_a_success(self):
        with patch.object(mcp.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "offline")):
            self.assertTrue(mcp.run_tgpt({"prompt": "hello"})["isError"])
