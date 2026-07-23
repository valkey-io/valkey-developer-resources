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


def query_flow(question: str) -> str:
    """Send a query to a Langflow flow and return the response text."""
    base_url = os.environ["LANGFLOW_BASE_URL"]
    flow_id = os.environ["LANGFLOW_FLOW_ID"]
    api_key = os.environ["LANGFLOW_API_KEY"]

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
    return data["outputs"][0]["outputs"][0]["results"]["message"]["data"]["text"]


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/query_flow.py <question>", file=sys.stderr)
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    answer = query_flow(question)
    print(f"Q: {question}")
    print(f"A: {answer}")


if __name__ == "__main__":
    main()
