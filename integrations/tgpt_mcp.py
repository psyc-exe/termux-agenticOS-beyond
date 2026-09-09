#!/usr/bin/env python
"""Minimal stdio MCP server exposing tgpt as a tool for opencode."""
import json
import os
import subprocess
import sys
import re


TOOLS = [
    {
        "name": "tgpt_ask",
        "title": "Ask tgpt",
        "description": (
            "Ask a standalone question to tgpt CLI (PowerBrain by default, no user API key). "
            "Best for quick second opinions, summaries, or facts that don't need local files. "
            "Returns the model's text answer as plain text."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Complete, self-contained question. Example: 'Explain DNS resolution in 3 sentences'",
                },
                "model": {
                    "type": "string",
                    "description": "Optional provider-supported model override; availability is provider-dependent.",
                },
                "preprompt": {
                    "type": "string",
                    "description": "Optional persona/instruction prepended to the conversation. Example: 'Answer as concisely as possible'",
                },
            },
            "required": ["prompt"],
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    }
]


def run_tgpt(args):
    if not isinstance(args, dict) or not isinstance(args.get("prompt"), str) or not args["prompt"].strip() or len(args["prompt"]) > 32768:
        return {"content": [{"type": "text", "text": "prompt must be a nonempty string of at most 32768 characters"}], "isError": True}
    for key in ("model", "preprompt"):
        if key in args and not isinstance(args[key], str):
            return {"content": [{"type": "text", "text": key + " must be a string"}], "isError": True}
    if args.get("model") and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:-]{0,127}", args["model"]):
        return {"content": [{"type": "text", "text": "Invalid model identifier"}], "isError": True}
    cmd = [os.environ.get("AGENTICOS_TGPT_BIN", "tgpt"), "--config", "/dev/null", "--provider", "powerbrain", "--whole"]
    if args.get("model"):
        cmd += ["--model", args["model"]]
    if args.get("preprompt"):
        cmd += ["--preprompt", "Instructions: " + args["preprompt"]]
    cmd += ["--", "Question: " + args["prompt"]]
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
            env={k: v for k, v in os.environ.items() if k not in ("AI_ROTATE_PROVIDERS", "AI_API_KEY")},
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        if proc.returncode != 0:
            hint = ""
            if "429" in err or "rate" in err.lower():
                hint = " Provider rate limit; retry later. No automatic provider switch."
            return {
                "content": [{"type": "text", "text": f"tgpt failed: {err or out}.{hint}"}],
                "isError": True,
            }
        return {"content": [{"type": "text", "text": out or "(empty response)"}]}
    except subprocess.TimeoutExpired:
        return {"content": [{"type": "text", "text": "tgpt timed out after 60s"}], "isError": True}
    except FileNotFoundError:
        return {"content": [{"type": "text", "text": "tgpt binary not found in PATH"}], "isError": True}


def handle(req):
    if not isinstance(req, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    method = req.get("method", "")
    rid = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "tgpt-mcp", "version": "1.0.0"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = req.get("params", {})
        if params.get("name") != "tgpt_ask":
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "error": {"code": -32602, "message": f"Unknown tool: {params.get('name')}"},
            }
        return {"jsonrpc": "2.0", "id": rid, "result": run_tgpt(params.get("arguments", {}))}
    if method.startswith("notifications/"):
        return None
    if rid is not None:
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {"code": -32601, "message": f"Method not supported: {method}"},
        }
    return None


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            resp = handle(req)
        except (TypeError, ValueError, AttributeError, KeyError):
            resp = {"jsonrpc": "2.0", "id": req.get("id") if isinstance(req, dict) else None, "error": {"code": -32602, "message": "Invalid parameters"}}
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
