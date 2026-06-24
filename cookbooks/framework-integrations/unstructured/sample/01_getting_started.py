"""01 — Getting Started: connect to Valkey and verify the connector works."""

from unstructured_ingest.processes.connectors.valkey import (
    ValkeyAccessConfig,
    ValkeyConnectionConfig,
    ValkeyUploader,
    ValkeyUploaderConfig,
)

VALKEY_HOST = "localhost"
VALKEY_PORT = 6379


def main():
    connection_config = ValkeyConnectionConfig(
        host=VALKEY_HOST,
        port=VALKEY_PORT,
        ssl=False,
        access_config=ValkeyAccessConfig(),
    )

    upload_config = ValkeyUploaderConfig(
        batch_size=50,
        key_prefix="doc:unstructured:",
        index_name="documents_index",
    )

    uploader = ValkeyUploader(
        connection_config=connection_config,
        upload_config=upload_config,
    )

    # Verify connection
    uploader.precheck()
    print(f"Connected to Valkey at {VALKEY_HOST}:{VALKEY_PORT}")
    print("Precheck passed — ready to ingest documents.")


if __name__ == "__main__":
    main()
