"""Full pipeline demo: connection test → ingest → search → monitoring."""

import os
import subprocess
import sys

SAMPLE_PDF = os.getenv("SAMPLE_PDF", "sample.pdf")


def run_script(name: str):
    """Run a sample script as a subprocess."""
    result = subprocess.run([sys.executable, name], capture_output=False)
    if result.returncode != 0:
        print(f"  Script {name} exited with code {result.returncode}")
    return result.returncode


def main():
    print("=== Step 1: Connection Test ===\n")
    run_script("01_getting_started.py")
    print()

    if not os.path.exists(SAMPLE_PDF):
        print(f"=== Step 2: Skipped (no '{SAMPLE_PDF}' found) ===")
        print(f"Place a PDF in this directory or set SAMPLE_PDF env var.\n")
    else:
        print("=== Step 2: Document Ingestion & Search ===\n")
        run_script("02_ingestion_and_search.py")
        print()

    print("=== Step 3: Production ===\n")
    run_script("03_production.py")


if __name__ == "__main__":
    main()
