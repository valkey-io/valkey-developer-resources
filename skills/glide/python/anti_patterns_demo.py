#!/usr/bin/env python3
"""
Python GLIDE Anti-Pattern Demonstrations
Based on: https://medium.com/@BuildShift/10-python-anti-patterns-ruining-your-code-and-what-to-do-instead-e304c457bc98
"""

import asyncio
import os
from glide import GlideClient, GlideClientConfiguration, NodeAddress


# ============================================================================
# ANTI-PATTERN 1: Exceptions as Control Flow
# ============================================================================

async def fetch_from_primary_api_anti(key: str, client: GlideClient) -> dict:
    """Anti-pattern: Raises exception for control flow"""
    value = await client.get(key)
    if value is None:
        raise ValueError("Primary API failed")
    return {"status": "ok", "data": value}


async def get_data_anti_pattern(client: GlideClient) -> dict:
    """Anti-pattern: Using try/except for normal logic"""
    try:
        return await fetch_from_primary_api_anti("primary:key", client)
    except ValueError:
        try:
            return await fetch_from_primary_api_anti("backup:key", client)
        except ValueError:
            return {"status": "error", "msg": "Both APIs failed"}


async def fetch_from_api_correct(key: str, client: GlideClient) -> dict:
    """Correct: Returns status dict"""
    value = await client.get(key)
    if value is None:
        return {"status": "error", "msg": f"Key {key} not found"}
    return {"status": "ok", "data": value}


async def get_data_correct(client: GlideClient) -> dict:
    """Correct: Status-based returns"""
    result = await fetch_from_api_correct("primary:key", client)
    if result["status"] == "error":
        result = await fetch_from_api_correct("backup:key", client)
    return result


# ============================================================================
# ANTI-PATTERN 2: Static Method-Only Classes
# ============================================================================

class CacheUtilsAntiPattern:
    """Anti-pattern: Class with only static methods"""
    
    @staticmethod
    async def get_user(client: GlideClient, user_id: str) -> str:
        return await client.get(f"user:{user_id}")
    
    @staticmethod
    async def set_user(client: GlideClient, user_id: str, data: str):
        await client.set(f"user:{user_id}", data)


# Correct: Just use module-level functions
async def get_user(client: GlideClient, user_id: str) -> str:
    """Correct: Module-level function"""
    return await client.get(f"user:{user_id}")


async def set_user(client: GlideClient, user_id: str, data: str):
    """Correct: Module-level function"""
    await client.set(f"user:{user_id}", data)


# ============================================================================
# ANTI-PATTERN 3: Tight Coupling (No Abstraction)
# ============================================================================

class UserServiceAntiPattern:
    """Anti-pattern: Tightly coupled to GlideClient"""
    
    def __init__(self, host: str, port: int):
        self.config = GlideClientConfiguration([NodeAddress(host, port)])
        self.client = None
    
    async def connect(self):
        self.client = await GlideClient.create(self.config)
    
    async def get_user(self, user_id: str) -> str:
        return await self.client.get(f"user:{user_id}")


# Correct: Use Protocol for abstraction
from typing import Protocol


class CacheClient(Protocol):
    """Protocol defining cache interface"""
    async def get(self, key: str) -> str: ...
    async def set(self, key: str, value: str): ...


class UserService:
    """Correct: Depends on abstraction"""
    
    def __init__(self, cache: CacheClient):
        self.cache = cache
    
    async def get_user(self, user_id: str) -> str:
        return await self.cache.get(f"user:{user_id}")


# ============================================================================
# ANTI-PATTERN 4: Wildcard Imports
# ============================================================================

# ❌ ANTI-PATTERN (commented out to avoid actual import)
# from glide import *
# client = GlideClient.create(...)  # Where did GlideClient come from?

# ✅ CORRECT
# from glide import GlideClient, GlideClientConfiguration, NodeAddress


# ============================================================================
# Main Demo
# ============================================================================

async def main():
    print("Python GLIDE Anti-Pattern Demonstrations")
    print("=" * 50)
    
    host = os.getenv("VALKEY_HOST", "localhost")
    config = GlideClientConfiguration([NodeAddress(host, 6379)])
    client = await GlideClient.create(config)
    
    try:
        # Setup test data
        await client.set("primary:key", "primary_data")
        await client.set("backup:key", "backup_data")
        
        # 1. Exceptions as Control Flow
        print("\n=== ANTI-PATTERN: Exceptions as Control Flow ===")
        result = await get_data_anti_pattern(client)
        print(f"Result: {result}")
        
        print("\n=== CORRECT: Status-Based Returns ===")
        result = await get_data_correct(client)
        print(f"Result: {result}")
        
        # 2. Static Method-Only Classes
        print("\n=== ANTI-PATTERN: Static Method-Only Class ===")
        await CacheUtilsAntiPattern.set_user(client, "123", "Alice")
        user = await CacheUtilsAntiPattern.get_user(client, "123")
        print(f"User from static class: {user}")
        
        print("\n=== CORRECT: Module-Level Functions ===")
        await set_user(client, "456", "Bob")
        user = await get_user(client, "456")
        print(f"User from function: {user}")
        
        # 3. Tight Coupling
        print("\n=== ANTI-PATTERN: Tight Coupling ===")
        service_anti = UserServiceAntiPattern(host, 6379)
        await service_anti.connect()
        user = await service_anti.get_user("123")
        print(f"User from tightly coupled service: {user}")
        
        print("\n=== CORRECT: Protocol-Based Abstraction ===")
        service = UserService(client)  # client implements CacheClient protocol
        user = await service.get_user("456")
        print(f"User from abstracted service: {user}")
        
        # 4. Wildcard Imports
        print("\n=== ANTI-PATTERN: Wildcard Imports ===")
        print("# from glide import *  # ❌ Namespace pollution")
        
        print("\n=== CORRECT: Explicit Imports ===")
        print("# from glide import GlideClient, GlideClientConfiguration  # ✅ Clear")
        
        print("\n=== All demonstrations completed ===")
        
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
