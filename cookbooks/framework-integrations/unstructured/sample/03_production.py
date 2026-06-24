"""03 — Production: TLS connection, TTL, index monitoring."""

from glide_sync import (
    GlideClient,
    GlideClientConfiguration,
    NodeAddress,
    ft,
)

VALKEY_HOST = "localhost"
VALKEY_PORT = 6379
INDEX_NAME = "documents_index"


def check_index():
    """Monitor index health via FT.INFO."""
    config = GlideClientConfiguration(
        addresses=[NodeAddress(VALKEY_HOST, VALKEY_PORT)],
        request_timeout=10000,
    )
    client = GlideClient.create(config)

    try:
        info = ft.info(client, INDEX_NAME)
        num_docs = info.get(b"num_docs", b"0").decode()
        indexing = info.get(b"indexing", b"0").decode()
        print(f"Index: {INDEX_NAME}")
        print(f"  Documents: {num_docs}")
        print(f"  Indexing: {'backfilling' if indexing == '1' else 'idle'}")
    except Exception as e:
        print(f"Index '{INDEX_NAME}' not found — no documents ingested yet.")
        print(f"  (Error: {e})")
        print("  This is expected if you haven't ingested any documents.")

    client.close()


def demo_ttl_config():
    """Show TTL configuration for auto-expiring documents."""
    from unstructured_ingest.processes.connectors.valkey import (
        ValkeyAccessConfig,
        ValkeyConnectionConfig,
        ValkeyUploader,
        ValkeyUploaderConfig,
    )

    uploader = ValkeyUploader(
        connection_config=ValkeyConnectionConfig(
            host=VALKEY_HOST,
            port=VALKEY_PORT,
            ssl=False,
            access_config=ValkeyAccessConfig(),
            request_timeout=60000,  # higher for cloud
        ),
        upload_config=ValkeyUploaderConfig(
            batch_size=100,
            key_prefix="doc:ephemeral:",
            index_name="ephemeral_index",
            ttl_seconds=86400,  # 24h auto-expiry
        ),
    )
    print("\nTTL config example:")
    print(f"  key_prefix: {uploader.upload_config.key_prefix}")
    print(f"  ttl_seconds: {uploader.upload_config.ttl_seconds}")
    print(f"  request_timeout: {uploader.connection_config.request_timeout}ms")


def demo_uri_connection():
    """Show URI-based connection (for cloud deployments)."""
    from unstructured_ingest.processes.connectors.valkey import (
        ValkeyAccessConfig,
        ValkeyConnectionConfig,
    )

    # Example URI formats:
    uris = [
        "valkey://localhost:6379",              # local, no TLS
        "valkeys://host:6379",                  # TLS
        "valkey://user:pass@host:6379",         # with auth
        "valkeys://default:token@cluster:6379", # ElastiCache
    ]

    print("\nURI connection examples:")
    for uri in uris:
        scheme = uri.split("://")[0]
        tls = "TLS" if scheme == "valkeys" else "plain"
        print(f"  {uri} ({tls})")


def main():
    check_index()
    demo_ttl_config()
    demo_uri_connection()


if __name__ == "__main__":
    main()
