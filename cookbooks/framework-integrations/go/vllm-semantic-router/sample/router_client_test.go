package main

import (
	"bufio"
	"context"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

func TestNewRouterClientRequiresModel(t *testing.T) {
	if _, err := NewRouterClient("http://localhost:8888", ""); err == nil {
		t.Fatal("NewRouterClient() accepted an empty model")
	}
}

func TestNewRouterClientRejectsInvalidURL(t *testing.T) {
	if _, err := NewRouterClient("localhost:8888", "demo-model"); err == nil {
		t.Fatal("NewRouterClient() accepted a URL without a scheme")
	}
}

func TestChatParsesSemanticRouterResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/chat/completions" {
			t.Fatalf("path = %q", r.URL.Path)
		}
		if r.Method != http.MethodPost {
			t.Fatalf("method = %q", r.Method)
		}
		w.Header().Set("x-vsr-cache-hit", "true")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"choices":[{"message":{"content":"Paris"}}]}`))
	}))
	defer server.Close()

	client, err := NewRouterClient(server.URL, "demo-model")
	if err != nil {
		t.Fatal(err)
	}
	result, err := client.Chat(context.Background(), "What is the capital of France?")
	if err != nil {
		t.Fatal(err)
	}
	if !result.CacheHit || result.Content != "Paris" {
		t.Fatalf("result = %#v", result)
	}
}

func TestChatRejectsEmptyPrompt(t *testing.T) {
	client, err := NewRouterClient("http://localhost:8888", "demo-model")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := client.Chat(context.Background(), " "); err == nil {
		t.Fatal("Chat() accepted an empty prompt")
	}
}

func TestWaitForCacheHitRetriesAsynchronousCacheWrites(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if requests == 2 {
			w.Header().Set("x-vsr-cache-hit", "true")
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"choices":[{"message":{"content":"Paris"}}]}`))
	}))
	defer server.Close()

	client, err := NewRouterClient(server.URL, "demo-model")
	if err != nil {
		t.Fatal(err)
	}
	var waits []time.Duration
	result, err := waitForCacheHit(context.Background(), client, "What is the capital of France?", func(wait time.Duration) {
		waits = append(waits, wait)
	})
	if err != nil {
		t.Fatal(err)
	}
	if !result.CacheHit || requests != 2 {
		t.Fatalf("result = %#v, requests = %d", result, requests)
	}
	if len(waits) != 2 || waits[0] != time.Second || waits[1] != 2*time.Second {
		t.Fatalf("waits = %v", waits)
	}
}

func TestLiveSemanticRouterCache(t *testing.T) {
	url := os.Getenv("SEMANTIC_ROUTER_URL")
	model := os.Getenv("SEMANTIC_ROUTER_MODEL")
	if url == "" || model == "" {
		t.Skip("set SEMANTIC_ROUTER_URL and SEMANTIC_ROUTER_MODEL to run against a real Semantic Router")
	}
	client, err := NewRouterClient(url, model)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := client.Chat(context.Background(), "What is the capital of France?"); err != nil {
		t.Fatal(err)
	}
	result, err := waitForCacheHit(context.Background(), client, "What is the capital of France?", time.Sleep)
	if err != nil {
		t.Fatal(err)
	}
	if !result.CacheHit {
		t.Fatal("second router response did not include x-vsr-cache-hit: true")
	}
}

func TestReleasedConfigSelectsValkeySemanticCache(t *testing.T) {
	contents, err := os.ReadFile("config.yaml")
	if err != nil {
		t.Fatal(err)
	}
	config := string(contents)
	for _, required := range []string{
		"semantic_cache:", "backend_type: valkey", "similarity_threshold: 0.85",
		"ttl_seconds: 3600", "embedding_model: bert", "host: host.docker.internal",
	} {
		if !strings.Contains(config, required) {
			t.Errorf("config.yaml is missing %q", required)
		}
	}
}

func TestConfiguredValkeyEndpointRespondsToPing(t *testing.T) {
	host := os.Getenv("VALKEY_HOST")
	if host == "" {
		t.Skip("set VALKEY_HOST to PING the Valkey service used by Semantic Router")
	}
	connection, err := net.DialTimeout("tcp", net.JoinHostPort(host, "6379"), 2*time.Second)
	if err != nil {
		t.Fatalf("connect to Valkey at %s:6379: %v", host, err)
	}
	defer connection.Close()
	if _, err := fmt.Fprint(connection, "*1\r\n$4\r\nPING\r\n"); err != nil {
		t.Fatalf("execute PING against Valkey at %s:6379: %v", host, err)
	}
	response, err := bufio.NewReader(connection).ReadString('\n')
	if err != nil {
		t.Fatalf("read PING response from Valkey at %s:6379: %v", host, err)
	}
	if strings.HasPrefix(response, "-") {
		t.Fatalf("PING failed at Valkey endpoint %s:6379: %s", host, strings.TrimSpace(response))
	}
	if response != "+PONG\r\n" {
		t.Fatalf("unexpected PING response from Valkey at %s:6379: %q; want %q", host, response, "+PONG\\r\\n")
	}
}
