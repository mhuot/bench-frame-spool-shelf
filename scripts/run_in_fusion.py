#!/usr/bin/env python3
"""Run a Fusion 360 script file through the local Fusion MCP server.

Usage:
    python3 scripts/run_in_fusion.py scripts/build_rod_bracket.py
    python3 scripts/run_in_fusion.py scripts/build_rod_bracket.py --variant gauge

The MCP server (http://127.0.0.1:27182/mcp) executes the script text inside
Fusion's long-lived Python interpreter, calling its `run(context)` entry
point. `--variant` injects `BUILD_VARIANT = "<value>"` ahead of the script
text; the build script picks it up via `globals().get(...)`.

Standard library only — no venv needed for this one.
"""

import argparse
import json
import pathlib
import sys
import urllib.request

MCP_URL = "http://127.0.0.1:27182/mcp"


def _post(payload, session_id=None):
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        request_headers["MCP-Session-Id"] = session_id
    request = urllib.request.Request(
        MCP_URL, data=json.dumps(payload).encode(), headers=request_headers
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        body = response.read().decode()
        returned_session = response.headers.get("MCP-Session-Id")
    parsed = json.loads(body) if body.strip() else None
    return parsed, returned_session


def open_session():
    """Perform the MCP initialize handshake; return the session id."""
    _, session_id = _post(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "run-in-fusion", "version": "1.0"},
            },
        }
    )
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, session_id)
    return session_id


def run_script_text(script_text):
    """Execute script text inside Fusion; return the tool-call result dict."""
    session_id = open_session()
    result, _ = _post(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "fusion_mcp_execute",
                "arguments": {
                    "featureType": "script",
                    "object": {"script": script_text},
                },
            },
        },
        session_id,
    )
    return result


def main():
    """Parse arguments, run the script in Fusion, print its output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script_path", type=pathlib.Path)
    parser.add_argument(
        "--variant",
        default=None,
        help='injected as BUILD_VARIANT (e.g. "gauge")',
    )
    arguments = parser.parse_args()

    script_text = arguments.script_path.read_text()
    if arguments.variant:
        script_text = f'BUILD_VARIANT = "{arguments.variant}"\n' + script_text

    result = run_script_text(script_text)
    try:
        inner = json.loads(result["result"]["content"][0]["text"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        print(json.dumps(result, indent=2))
        sys.exit(1)
    print(inner.get("message", ""))
    if not inner.get("success", False):
        print("--- script FAILED ---", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
