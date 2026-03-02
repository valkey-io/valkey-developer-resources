package main

import (
	"context"
	"fmt"
	"os"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
)

// Go GLIDE TLS + Authentication Test
//
// Tests TLS connectivity with password authentication on port 6479.
//
// Usage:
//   export VALKEY_HOST=localhost
//   cd go/demos
//   go run authentication/tls_auth_demo.go

func main() {
	fmt.Println("Go GLIDE TLS + Authentication Testing\n")

	if err := testTlsWithAuth(); err != nil {
		fmt.Printf("✗ TLS test error: %v\n", err)
		os.Exit(1)
	}
}

func testTlsWithAuth() error {
	fmt.Println("=== Testing TLS + Authentication (Port 6479) ===")

	host := os.Getenv("VALKEY_HOST")
	if host == "" {
		host = "localhost"
	}

	// For self-signed certificates (testing only)
	// ⚠️ WARNING: WithInsecureTLS disables certificate verification
	// In production, use proper CA-signed certificates
	tlsConfig := config.NewTlsConfiguration().WithInsecureTLS(true)
	advancedConfig := config.NewAdvancedClientConfiguration().WithTlsConfiguration(tlsConfig)
	
	clientConfig := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: host, Port: 6479}).
		WithUseTLS(true).
		WithCredentials(config.NewServerCredentials("", "mypassword")).
		WithRequestTimeout(5000).
		WithAdvancedConfiguration(advancedConfig)

	client, err := glide.NewClient(clientConfig)
	if err != nil {
		return fmt.Errorf("failed to create client: %w", err)
	}
	defer client.Close()

	ctx := context.Background()

	// Test operations
	_, err = client.Set(ctx, "tls_test_go", "Hello with TLS!")
	if err != nil {
		return fmt.Errorf("set failed: %w", err)
	}

	value, err := client.Get(ctx, "tls_test_go")
	if err != nil {
		return fmt.Errorf("get failed: %w", err)
	}

	fmt.Printf("✓ TLS works: %s\n", value.Value())

	// Cleanup
	_, err = client.Del(ctx, []string{"tls_test_go"})
	if err != nil {
		return fmt.Errorf("cleanup failed: %w", err)
	}

	fmt.Println("\n=== Testing Complete ===")
	return nil
}
