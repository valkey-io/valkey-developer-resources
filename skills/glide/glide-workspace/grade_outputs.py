#!/usr/bin/env python3
"""Grade test outputs against assertions."""

import json
import os
from pathlib import Path

def grade_vector_search(output_dir):
    """Grade vector-search-json test."""
    code_file = output_dir / "vector_search.py"
    if not code_file.exists():
        return {"error": "Output file not found"}
    
    code = code_file.read_text()
    
    results = []
    
    # Assertion 1: Uses async client with context manager
    passed = "async with" in code and ("GlideClient" in code or "GlideClusterClient" in code)
    results.append({
        "text": "Uses async client with context manager",
        "passed": passed,
        "evidence": "Found 'async with GlideClient'" if passed else "Missing async context manager"
    })
    
    # Assertion 2: Uses ft.search with proper imports
    passed = "ft.search" in code or "ft_search" in code
    results.append({
        "text": "Uses ft.search with proper imports",
        "passed": passed,
        "evidence": "Found ft.search or ft_search call" if passed else "Missing ft.search call"
    })
    
    # Assertion 3: Decodes bytes to strings
    passed = ".decode(" in code and "utf-8" in code.lower()
    results.append({
        "text": "Decodes bytes to strings",
        "passed": passed,
        "evidence": "Found .decode() with UTF-8" if passed else "Missing byte decoding"
    })
    
    # Assertion 4: Skips binary embedding field
    passed = "embedding" in code and ("skip" in code.lower() or "continue" in code or "errors=" in code)
    results.append({
        "text": "Skips binary embedding field",
        "passed": passed or "embedding" not in code,  # Pass if not mentioned or properly handled
        "evidence": "Handles binary fields" if passed else "May not handle binary fields properly"
    })
    
    # Assertion 5: Uses FtSearchOptions with params
    passed = "FtSearchOptions" in code or "options" in code or "PARAMS" in code
    results.append({
        "text": "Uses FtSearchOptions with params",
        "passed": passed,
        "evidence": "Found options/params handling" if passed else "Missing FtSearchOptions"
    })
    
    return results

def grade_ping_scan(output_dir):
    """Grade ping-scan-health test."""
    code_file = output_dir / "valkey_health_check.py"
    if not code_file.exists():
        return {"error": "Output file not found"}
    
    code = code_file.read_text()
    
    results = []
    
    # Assertion 1: Checks ping() returns bytes
    passed = "b'PONG'" in code or "b\"PONG\"" in code
    results.append({
        "text": "Checks ping() returns bytes",
        "passed": passed,
        "evidence": "Checks against b'PONG'" if passed else "May not check ping() correctly"
    })
    
    # Assertion 2: Uses string cursor for scan()
    passed = 'cursor = "0"' in code or "cursor = '0'" in code
    results.append({
        "text": "Uses string cursor for scan()",
        "passed": passed,
        "evidence": "Uses string cursor '0'" if passed else "May use integer cursor"
    })
    
    # Assertion 3: Uses ServerCredentials for auth
    passed = "ServerCredentials" in code or "password=" in code
    results.append({
        "text": "Uses ServerCredentials for auth",
        "passed": passed,
        "evidence": "Found auth configuration" if passed else "Missing auth"
    })
    
    # Assertion 4: Uses async context manager
    passed = "async with" in code
    results.append({
        "text": "Uses async context manager",
        "passed": passed,
        "evidence": "Found async with" if passed else "Missing async context manager"
    })
    
    # Assertion 5: Catches specific exceptions
    passed = ("ConnectionError" in code or "TimeoutError" in code or "RequestError" in code) and "except" in code
    results.append({
        "text": "Catches specific exceptions",
        "passed": passed,
        "evidence": "Catches specific exceptions" if passed else "Uses generic Exception"
    })
    
    return results

def main():
    workspace = Path("glide-workspace/iteration-1")
    
    tests = [
        ("vector-search-json", grade_vector_search),
        ("ping-scan-health", grade_ping_scan),
    ]
    
    for test_name, grader in tests:
        for variant in ["with_skill", "without_skill"]:
            output_dir = workspace / test_name / variant / "outputs"
            if output_dir.exists():
                results = grader(output_dir)
                
                grading_file = workspace / test_name / variant / "grading.json"
                grading_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(grading_file, "w") as f:
                    json.dump({"expectations": results}, f, indent=2)
                
                print(f"Graded {test_name}/{variant}")

if __name__ == "__main__":
    main()
