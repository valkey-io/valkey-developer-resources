package main

import (
	"context"
	"fmt"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
)

// Go GLIDE AWS IAM Authentication Demo
//
// Demonstrates AWS ElastiCache/MemoryDB IAM authentication configuration.
// This demo validates the configuration compiles and runs without AWS-specific errors.
//
// Note: Actual connection will fail without valid AWS credentials and ElastiCache cluster.
//
// Usage:
//   cd go/demos
//   go run authentication/iam_auth_demo.go

func main() {
	fmt.Println("Go GLIDE AWS IAM Authentication Demo\n")

	if err := testIamAuth(); err != nil {
		fmt.Println("\n⚠ IAM auth demo completed (connection expected to fail without AWS)")
		fmt.Printf("  Error: %v\n", err)
		
		// Check if it's a connection error (expected)
		errStr := err.Error()
		if contains(errStr, "Connection") || contains(errStr, "refused") || contains(errStr, "not known") {
			fmt.Println("✓ Configuration is valid (connection failure is expected)")
		}
	}
}

func testIamAuth() error {
	fmt.Println("=== Testing AWS IAM Authentication ===")

	// AWS ElastiCache IAM configuration
	iamConfig := config.NewIamAuthConfig("my-cluster", config.ElastiCache, "us-east-1")

	credentials, err := config.NewServerCredentialsWithIam("myUser", iamConfig)
	if err != nil {
		return fmt.Errorf("failed to create credentials: %w", err)
	}

	fmt.Println("✓ IAM configuration created successfully")
	fmt.Println("  Cluster: my-cluster")
	fmt.Println("  Service: ElastiCache")
	fmt.Println("  Region: us-east-1")
	fmt.Println("  Username: myUser")

	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: "my-cluster.cache.amazonaws.com", Port: 6379}).
		WithUseTLS(true). // IAM auth requires TLS
		WithCredentials(credentials).
		WithRequestTimeout(5000)

	// Attempt connection (will fail without actual AWS infrastructure)
	client, err := glide.NewClient(cfg)
	if err != nil {
		return err
	}
	defer client.Close()

	ctx := context.Background()

	// Test operations
	_, err = client.Set(ctx, "iam_test", "Hello from IAM!")
	if err != nil {
		return err
	}

	value, err := client.Get(ctx, "iam_test")
	if err != nil {
		return err
	}

	fmt.Printf("✓ IAM auth works: %s\n", value.Value())
	return nil
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > len(substr) && 
		(s[:len(substr)] == substr || s[len(s)-len(substr):] == substr || 
		findSubstring(s, substr)))
}

func findSubstring(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
