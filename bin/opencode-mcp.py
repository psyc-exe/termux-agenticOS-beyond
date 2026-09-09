#!/usr/bin/env python3
"""Add the optional tgpt worker at runtime, preserving user/project config files."""
import json
import os
import sys

binary, worker = sys.argv[1:3]
config = json.loads(os.environ.get("OPENCODE_CONFIG_CONTENT", "{}"))
config.setdefault("mcp", {})["tgpt"] = {
    "type": "local", "command": [worker], "enabled": True, "timeout": 65000,
}
os.environ["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)
os.execv(binary, [binary] + sys.argv[3:])
