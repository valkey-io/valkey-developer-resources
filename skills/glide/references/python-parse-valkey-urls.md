# Connection URL Format
For parsing Valkey connection URLs, use the `_parse_valkey_url` function.

```python
def _parse_valkey_url(url: str) -> tuple[str, int]:
    """Parse Valkey URL to extract host and port."""
    # Remove protocol (valkey://, valkeyss://)
    if "://" in url:
        url = url.split("://", 1)[1]

    # Remove credentials if present
    if "@" in url:
        url = url.split("@", 1)[1]

    # Extract host and port
    if ":" in url:
        host, port_str = url.rsplit(":", 1)
        port_str = port_str.split("/")[0]  # Remove path
        port = int(port_str)
    else:
        host = url
        port = 6379

    return host, port
```

**Supported formats:**
- `valkey://localhost:6379`
- `valkeyss://host:6379` (SSL)
- `valkey://user:pass@host:6379`
- `valkey://host:6379/0` (with database number)

