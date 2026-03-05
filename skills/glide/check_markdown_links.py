#!/usr/bin/env python3
"""Check for broken local file links in Markdown files."""

import re
import sys
from pathlib import Path

def find_local_links(markdown_content):
    """Extract local file links from markdown content."""
    # Match [text](path) and [text](path "title")
    pattern = r'\[([^\]]+)\]\(([^)]+?)(?:\s+"[^"]*")?\)'
    links = []
    for match in re.finditer(pattern, markdown_content):
        link = match.group(2)
        # Skip URLs (http://, https://, mailto:, etc.)
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', link):
            # Remove anchor fragments
            link = link.split('#')[0]
            if link:  # Skip empty links (pure anchors)
                links.append(link)
    return links

def check_markdown_file(markdown_path):
    """Check all local links in a markdown file."""
    markdown_path = Path(markdown_path)
    
    if not markdown_path.exists():
        print(f"Error: {markdown_path} does not exist")
        return False
    
    content = markdown_path.read_text(encoding='utf-8')
    links = find_local_links(content)
    
    if not links:
        print(f"✓ {markdown_path}: No local links found")
        return True
    
    broken = []
    for link in links:
        # Resolve relative to the markdown file's directory
        target = (markdown_path.parent / link).resolve()
        if not target.exists():
            broken.append(link)
    
    if broken:
        print(f"✗ {markdown_path}: {len(broken)} broken link(s)")
        for link in broken:
            print(f"  - {link}")
        return False
    else:
        print(f"✓ {markdown_path}: All {len(links)} link(s) valid")
        return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_markdown_links.py <markdown_file> [<markdown_file> ...]")
        sys.exit(1)
    
    all_valid = True
    for file_path in sys.argv[1:]:
        if not check_markdown_file(file_path):
            all_valid = False
    
    sys.exit(0 if all_valid else 1)
