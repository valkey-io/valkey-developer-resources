# Decode Docs
Decodes documents from the search results, bytes to strings, because GLIDE returns bytes.

```python
from typing import Any


def _decode_docs(results) -> list[dict[str, Any]]:
    """Decode documents from the search results."""

    count = results[0]
    docs = []
    # Iterates results; decodes fields; skips binary embeddings
    if count > 0 and len(results) > 1:
        for key, fields in results[1].items():
            str_key = key.decode() if isinstance(key, bytes) else key
            str_fields = {}
            for field_key, field_value in fields.items():
                str_field_key = field_key.decode() if isinstance(field_key, bytes) else field_key
                # Skip binary fields (like vector embeddings)
                if str_field_key == "embedding":
                    continue
                try:
                    str_field_value = field_value.decode() if isinstance(field_value, bytes) else field_value
                    str_fields[str_field_key] = str_field_value
                except (UnicodeDecodeError, AttributeError):
                    pass  # Skip binary fields
            docs.append({"key": str_key, **str_fields})
    return docs
```
