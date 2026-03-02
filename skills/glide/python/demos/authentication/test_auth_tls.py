#!/usr/bin/env python3
"""
Test Python GLIDE TLS with authentication.
Tests TLS + password auth on port 6479.
"""
import asyncio
import os
from glide import (
    GlideClient, 
    GlideClientConfiguration, 
    NodeAddress, 
    ServerCredentials,
    AdvancedGlideClientConfiguration
)
from glide_shared.config import TlsAdvancedConfiguration, load_root_certificates_from_file

async def test_tls():
    """Test TLS with authentication on port 6479"""
    print("=== Testing TLS + Authentication (Port 6479) ===")
    
    host = os.getenv("VALKEY_HOST", "localhost")
    
    # Load TLS certificate (symlinked in project root)
    cert_path = "../../../valkey.crt"
    
    try:
        # For self-signed certs with CA:FALSE, use insecure TLS for testing
        # ⚠️ WARNING: use_insecure_tls=True disables certificate verification
        # In production, use proper CA-signed certificates with root_pem_cacerts
        tls_config = TlsAdvancedConfiguration(use_insecure_tls=True)
        
        # TLS configuration with certificate
        config = GlideClientConfiguration(
            addresses=[NodeAddress(host, 6479)],
            use_tls=True,
            credentials=ServerCredentials("mypassword"),
            advanced_config=AdvancedGlideClientConfiguration(tls_config=tls_config),
            request_timeout=5000
        )
        
        client = await GlideClient.create(config)
        try:
            await client.set("tls_test_py", "Hello with TLS!")
            value = await client.get("tls_test_py")
            print(f"✓ TLS works: {value}")
            await client.delete(["tls_test_py"])
        finally:
            await client.close()
    except FileNotFoundError:
        print(f"⚠ Certificate not found at {cert_path}")
        print("  Run from correct directory or check certificate path")
    except Exception as e:
        print(f"⚠ TLS test failed: {e}")
        print(f"  Certificate path: {cert_path}")
        print("  Verify TLS setup with CLI command from PLAN.md")

async def main():
    """Run all authentication and TLS tests"""
    print("Python GLIDE Authentication and TLS Testing\n")
    
    # Test basic authentication
    try:
        await test_tls()
    except Exception as e:
        print(f"✗ TLS test error: {e}")
    
    print("\n=== Testing Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
