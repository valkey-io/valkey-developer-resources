#!/usr/bin/env python3
"""Promptfoo provider/grader bridge for CLI-based LLM tools."""

import base64
import json
import re
import subprocess
import sys
import tempfile
from typing import Any, Optional

ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')


def build_claude_cmd(
    prompt: str, model: str, is_grader: bool, system_msg: Optional[str]
) -> tuple[list[str], Optional[str]]:
    """Returns (args, stdin_input) for claude CLI."""
    args = ["claude", "--model", model, "-p", "-"]
    if is_grader and system_msg:
        args = ["claude", "--model", model, "--system-prompt", system_msg, "-p", "-"]
    return args, prompt


def build_kiro_cmd(
    prompt: str, model: str, is_grader: bool, system_msg: Optional[str]
) -> tuple[list[str], Optional[str]]:
    """Returns (args, stdin_input) for kiro CLI.

    Kiro doesn't support stdin and chokes on prompts starting with dashes.
    We write to a temp file and instruct kiro to read it.
    """
    input_text = prompt
    if is_grader and system_msg:
        input_text = f"{system_msg}\n\n---\n\n{input_text}"
    # Write prompt to temp file
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
    tmp.write(input_text)
    tmp.close()
    wrapper = (
        f"Read the file at {tmp.name} and respond to the question inside it. "
        f"The file contains a skill context followed by a user question."
    )
    args = ["kiro-cli", "chat", "--model", model, "--no-interactive", "--trust-all-tools", wrapper]
    return args, None


BACKENDS: dict[str, Any] = {
    "claude": build_claude_cmd,
    "kiro": build_kiro_cmd,
}

AUTH_ERROR_MARKERS = [
    "Not logged in",
    "Please run /login",
    "authentication required",
    "unauthorized",
    "session expired",
]


def detect_grader_mode(prompt: str) -> tuple[bool, Optional[str], str]:
    """Detect if prompt is a grader JSON array. Returns (is_grader, system_msg, user_msg)."""
    try:
        messages = json.loads(prompt)
        if isinstance(messages, list) and messages and "role" in messages[0]:
            system_msg = next(
                (m["content"] for m in messages if m["role"] == "system"), None
            )
            user_msg = next(
                (m["content"] for m in messages if m["role"] == "user"), prompt
            )
            return True, system_msg, user_msg
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return False, None, prompt


def parse_config(options_json: str) -> tuple[str, str]:
    """Extract backend and model from promptfoo options JSON."""
    backend = "claude"
    model = "sonnet"
    try:
        opts = json.loads(options_json)
        config = opts.get("config", {})
        backend = config.get("backend", backend)
        model = config.get("model", model)
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return backend, model


def check_auth_error(output: str) -> bool:
    """Check if CLI output indicates an authentication problem."""
    lower = output.lower()
    return any(marker.lower() in lower for marker in AUTH_ERROR_MARKERS)


def main() -> None:
    prompt = sys.argv[1] if len(sys.argv) > 1 else ""
    options_json = sys.argv[2] if len(sys.argv) > 2 else "{}"

    backend_name, model = parse_config(options_json)

    if backend_name not in BACKENDS:
        print(
            f"Unknown backend: '{backend_name}'. Available: {list(BACKENDS.keys())}",
            file=sys.stderr,
        )
        sys.exit(1)

    is_grader, system_msg, user_prompt = detect_grader_mode(prompt)
    build_cmd = BACKENDS[backend_name]
    args, stdin_input = build_cmd(user_prompt, model, is_grader, system_msg)

    result = subprocess.run(
        args,
        input=stdin_input,
        capture_output=True,
        text=True,
    )

    combined_output = (result.stdout or "") + (result.stderr or "")

    if check_auth_error(combined_output):
        print(
            f"Authentication error: '{backend_name}' CLI is not logged in. "
            f"Please authenticate before running evals.",
            file=sys.stderr,
        )
        sys.exit(2)

    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        sys.exit(result.returncode)

    print(ANSI_ESCAPE.sub('', result.stdout), end="")


if __name__ == "__main__":
    main()
