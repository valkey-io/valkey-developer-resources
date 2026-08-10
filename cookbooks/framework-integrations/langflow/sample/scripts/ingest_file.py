"""Upload and ingest a file into a Langflow RAG flow.

Usage:
    export LANGFLOW_BASE_URL=http://127.0.0.1:7860
    export LANGFLOW_API_KEY=your-key
    export LANGFLOW_FLOW_ID=your-ingestion-flow-id
    python scripts/ingest_file.py document.pdf File-XXXXX
"""

import os
import sys
from pathlib import Path

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


def upload_file(base_url: str, api_key: str, file_path: Path) -> str:
    """Upload a file to the Langflow server and return the server path."""
    with open(file_path, "rb") as f:
        response = requests.post(
            f"{base_url}/api/v2/files/",
            headers={"x-api-key": api_key},
            files={"file": (file_path.name, f)},
            timeout=60,
        )
    response.raise_for_status()
    return response.json()["path"]


def run_ingestion(
    base_url: str,
    api_key: str,
    flow_id: str,
    uploaded_path: str,
    file_component_id: str,
) -> dict:
    """Trigger the ingestion flow with the uploaded file path."""
    response = requests.post(
        f"{base_url}/api/v1/run/{flow_id}",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
        json={
            "input_value": "Ingest this document",
            "output_type": "chat",
            "input_type": "text",
            "tweaks": {
                file_component_id: {
                    "path": uploaded_path,
                }
            },
        },
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "Usage: python scripts/ingest_file.py <file_path> <file_component_id>",
            file=sys.stderr,
        )
        sys.exit(1)

    file_path = Path(sys.argv[1])
    file_component_id = sys.argv[2]

    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    base_url = _require_env("LANGFLOW_BASE_URL")
    flow_id = _require_env("LANGFLOW_FLOW_ID")
    api_key = _require_env("LANGFLOW_API_KEY")

    print(f"Uploading {file_path.name}...")
    uploaded_path = upload_file(base_url, api_key, file_path)
    print(f"Uploaded to: {uploaded_path}")

    print("Running ingestion flow...")
    result = run_ingestion(base_url, api_key, flow_id, uploaded_path, file_component_id)
    print(f"Ingestion complete: {result.get('outputs', 'OK')}")


if __name__ == "__main__":
    main()
