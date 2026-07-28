"""
TestContainers Python + Valkey: Basic usage examples.

Demonstrates how to use ValkeyContainer for ephemeral Valkey instances
in integration tests. No external Valkey server needed — Docker handles it.

Requires: pip install "testcontainers[valkey]==4.14.3" valkey-glide-sync==1.3.4
"""

from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress, ServerCredentials

from testcontainers.community.valkey import ValkeyContainer


def basic_example():
    """Start a Valkey container, connect, and run basic operations."""
    print("=== Basic Example ===")
    with ValkeyContainer().with_bundle().with_image_tag("9.1.0") as valkey:
        host = valkey.get_host()
        port = valkey.get_exposed_port()
        print(f"Valkey running at {host}:{port}")
        print(f"Connection URL: {valkey.get_connection_url()}")

        config = GlideClientConfiguration([NodeAddress(host, port)])
        client = GlideClient.create(config)

        # PING
        pong = client.ping()
        print(f"PING: {pong.decode()}")

        # SET / GET
        client.set("greeting", "hello from testcontainers")
        value = client.get("greeting")
        print(f"GET greeting: {value.decode()}")

        # INCR
        client.set("counter", "0")
        client.incr("counter")
        client.incr("counter")
        client.incr("counter")
        count = client.get("counter")
        print(f"Counter after 3 increments: {count.decode()}")

        client.close()
    print("Container stopped and removed.\n")


def password_example():
    """Start a Valkey container with password authentication."""
    print("=== Password Example ===")
    with ValkeyContainer().with_password("my-secret") as valkey:
        host = valkey.get_host()
        port = valkey.get_exposed_port()
        print(f"Authenticated Valkey at {host}:{port}")
        print(f"Connection URL: {valkey.get_connection_url()}")

        config = GlideClientConfiguration(
            [NodeAddress(host, port)],
            credentials=ServerCredentials(password="my-secret"),
        )
        client = GlideClient.create(config)

        pong = client.ping()
        print(f"PING (authed): {pong.decode()}")

        client.close()
    print("Container stopped and removed.\n")


def version_pinning_example():
    """Demonstrate version pinning for reproducible tests."""
    print("=== Version Pinning Example ===")
    with ValkeyContainer().with_image_tag("8.1.1") as valkey:
        print(f"Image: {valkey.image}")
        host = valkey.get_host()
        port = valkey.get_exposed_port()

        config = GlideClientConfiguration([NodeAddress(host, port)])
        client = GlideClient.create(config)
        pong = client.ping()
        print(f"PING (v8.1.1): {pong.decode()}")
        client.close()
    print("Container stopped and removed.\n")


if __name__ == "__main__":
    basic_example()
    password_example()
    version_pinning_example()
    print("All examples completed successfully.")
