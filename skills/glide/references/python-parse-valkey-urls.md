# Connection URL Format
For parsing Valkey connection URLs, use the `_parse_valkey_url` function.

```python
def _parse_valkey_url(url: str) -> tuple[str, int, bool, str | None, str | None]:
    """Parse Valkey URL to extract host, port, TLS flag, and credentials."""
    use_tls = False
    username = None
    password = None
    
    # Extract protocol
    if "://" in url:
        protocol, url = url.split("://", 1)
        use_tls = protocol.endswith("ss")  # valkeyss or rediss
    
    # Extract credentials if present
    if "@" in url:
        credentials, url = url.split("@", 1)
        if ":" in credentials:
            username, password = credentials.split(":", 1)
        else:
            password = credentials
    
    # Extract host and port
    if ":" in url:
        host, port_str = url.rsplit(":", 1)
        port_str = port_str.split("/")[0]
        port = int(port_str)
    else:
        host = url.split("/")[0]
        port = 6379
    
    return host, port, use_tls, username, password
```

**Return values:**
- `host`: Hostname or IP address
- `port`: Port number (default: 6379)
- `use_tls`: True if protocol ends with "ss" (valkeyss://, rediss://)
- `username`: Username from credentials (optional)
- `password`: Password from credentials (optional)

**Supported formats:**
- `valkey://localhost:6379` → `("localhost", 6379, False, None, None)`
- `valkeyss://host:6379` → `("host", 6379, True, None, None)`
- `valkey://user:pass@host:6379` → `("host", 6379, False, "user", "pass")`
- `valkey://:pass@host:6379` → `("host", 6379, False, None, "pass")`
- `valkey://host:6379/0` → `("host", 6379, False, None, None)` (path ignored)

**Usage with credentials:**
```python
from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress, ServerCredentials

host, port, use_tls, username, password = _parse_valkey_url(valkey_url)
addresses = [NodeAddress(host, port)]

config_kwargs = {}
if use_tls:
    config_kwargs["use_tls"] = True
if username and password:
    config_kwargs["credentials"] = ServerCredentials(password, username)

config = GlideClientConfiguration(addresses=addresses, **config_kwargs)
client = GlideClient.create(config)
```

