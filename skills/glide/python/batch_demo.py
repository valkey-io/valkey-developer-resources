#!/usr/bin/env python3
"""Valkey GLIDE Batch/Pipeline Demo"""

import asyncio
from glide import GlideClient, GlideClientConfiguration, NodeAddress, Batch


async def demo():
    config = GlideClientConfiguration([NodeAddress("localhost", 6379)])
    client = await GlideClient.create(config)

    # Pipeline (non-atomic): bulk independent operations
    pipeline = Batch(False)
    pipeline.set("user:1", "Alice")
    pipeline.set("user:2", "Bob")
    pipeline.get("user:1")
    pipeline.get("user:2")

    results = await client.exec(pipeline, raise_on_error=True)
    print(f"Pipeline: {results}")

    # Transaction (atomic): consistent multi-key update
    transaction = Batch(True)
    transaction.set("counter", "0")
    transaction.incr("counter")
    transaction.incr("counter")
    transaction.get("counter")

    results = await client.exec(transaction, raise_on_error=True)
    print(f"Transaction: {results}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(demo())
