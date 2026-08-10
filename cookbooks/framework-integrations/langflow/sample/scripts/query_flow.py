"""Query a Langflow flow via the REST API.

Usage:
    export LANGFLOW_BASE_URL=http://127.0.0.1:7860
    export LANGFLOW_API_KEY=your-key
    export LANGFLOW_FLOW_ID=your-flow-id
    python scripts/query_flow.py "What is Valkey?"
"""

import os
import sys

import requests


def _require_env(name: str) -> str:
    """Return the value of an environment variable or exit with a helpful message."""
    value = os.environ.get(name)
    if not value:
        print(
            f"Error: environment variable {name} is not set.\n"
            f"Set it with: export {name}=<value>",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def query_flow(
    question: str,
    *,
    base_url: str,
    flow_id: str,
    api_key: str,
) -> str:
    """Send a query to a Langflow flow and return the response text."""
    response = requests.post(
        f"{base_url}/api/v1/run/{flow_id}",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
        json={
            "input_value": question,
            "output_type": "chat",
            "input_type": "chat",
        },
        timeout=120,
    )
    response.raise_for_status()

    data = response.json()
    try:
        return data["outputs"][0]["outputs"][0]["results"]["message"]["data"]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(
            f"Unexpected response structure from Langflow: {data}"
        ) from exc


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/query_flow.py <question>", file=sys.stderr)
        sys.exit(1)

    base_url = _require_env("LANGFLOW_BASE_URL")
    flow_id = _require_env("LANGFLOW_FLOW_ID")
    api_key = _require_env("LANGFLOW_API_KEY")

    question = " ".join(sys.argv[1:])
    answer = query_flow(
        question,
        base_url=base_url,
        flow_id=flow_id,
        api_key=api_key,
    )
    print(f"Q: {question}")
    print(f"A: {answer}")


if __name__ == "__main__":
    main()
