package main

import (
	"context"
	"fmt"
	"os"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
)

func main() {
	ctx := context.Background()

	// Create client configuration
	cfg := config.NewClientConfiguration().
		WithAddress(&config.NodeAddress{Host: os.Getenv("VALKEY_HOST"), Port: 6379}).
		WithRequestTimeout(10000)

	// Connect to Valkey
	client, err := glide.NewClient(cfg)
	if err != nil {
		fmt.Println("Connection error:", err)
		return
	}
	defer client.Close()

	// Set and get
	_, err = client.Set(ctx, "hello", "world")
	if err != nil {
		fmt.Println("Set error:", err)
		return
	}

	value, err := client.Get(ctx, "hello")
	if err != nil {
		fmt.Println("Get error:", err)
		return
	}
	fmt.Println("GET hello:", value)

	// Error handling - wrong type operation
	_, err = client.Set(ctx, "mykey", "string_value")
	if err != nil {
		fmt.Println("Set error:", err)
		return
	}

	_, err = client.LPop(ctx, "mykey")
	if err != nil {
		fmt.Println("Expected error (WRONGTYPE):", err)
	}

	fmt.Println("Basic operations completed")
}
