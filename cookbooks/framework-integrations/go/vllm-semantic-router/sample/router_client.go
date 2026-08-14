package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

const (
	defaultRouterURL = "http://localhost:8888"
	cacheHitAttempts = 4
)

type RouterClient struct {
	baseURL string
	model   string
	http    *http.Client
}

type ChatResult struct {
	Content  string
	CacheHit bool
}

type chatRequest struct {
	Model    string `json:"model"`
	Messages []struct {
		Role    string `json:"role"`
		Content string `json:"content"`
	} `json:"messages"`
}

type chatResponse struct {
	Choices []struct {
		Message struct {
			Content string `json:"content"`
		} `json:"message"`
	} `json:"choices"`
}

func NewRouterClient(baseURL, model string) (*RouterClient, error) {
	if baseURL == "" {
		baseURL = defaultRouterURL
	}
	if !strings.HasPrefix(baseURL, "http://") && !strings.HasPrefix(baseURL, "https://") {
		return nil, fmt.Errorf("SEMANTIC_ROUTER_URL must be an http(s) URL")
	}
	if model == "" {
		return nil, fmt.Errorf("SEMANTIC_ROUTER_MODEL is required")
	}
	return &RouterClient{
		baseURL: strings.TrimRight(baseURL, "/"),
		model:   model,
		http:    &http.Client{Timeout: 60 * time.Second},
	}, nil
}

func (c *RouterClient) Chat(ctx context.Context, prompt string) (ChatResult, error) {
	if strings.TrimSpace(prompt) == "" {
		return ChatResult{}, fmt.Errorf("prompt must not be empty")
	}
	request := chatRequest{Model: c.model}
	request.Messages = append(request.Messages, struct {
		Role    string `json:"role"`
		Content string `json:"content"`
	}{Role: "user", Content: prompt})
	body, err := json.Marshal(request)
	if err != nil {
		return ChatResult{}, fmt.Errorf("marshal chat request: %w", err)
	}

	httpRequest, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/v1/chat/completions", bytes.NewReader(body))
	if err != nil {
		return ChatResult{}, fmt.Errorf("create router request: %w", err)
	}
	httpRequest.Header.Set("Content-Type", "application/json")
	response, err := c.http.Do(httpRequest)
	if err != nil {
		return ChatResult{}, fmt.Errorf("send request to Semantic Router: %w", err)
	}
	defer response.Body.Close()
	responseBody, err := io.ReadAll(response.Body)
	if err != nil {
		return ChatResult{}, fmt.Errorf("read router response: %w", err)
	}
	if response.StatusCode != http.StatusOK {
		return ChatResult{}, fmt.Errorf("Semantic Router returned %s: %s", response.Status, strings.TrimSpace(string(responseBody)))
	}

	var payload chatResponse
	if err := json.Unmarshal(responseBody, &payload); err != nil {
		return ChatResult{}, fmt.Errorf("decode router response: %w", err)
	}
	if len(payload.Choices) == 0 {
		return ChatResult{}, fmt.Errorf("Semantic Router returned no chat choices")
	}
	return ChatResult{
		Content:  payload.Choices[0].Message.Content,
		CacheHit: response.Header.Get("x-vsr-cache-hit") == "true",
	}, nil
}

func waitForCacheHit(ctx context.Context, client *RouterClient, prompt string, sleep func(time.Duration)) (ChatResult, error) {
	var result ChatResult
	for attempt := 1; attempt <= cacheHitAttempts; attempt++ {
		sleep(time.Duration(attempt) * time.Second)
		var err error
		result, err = client.Chat(ctx, prompt)
		if err != nil {
			if attempt == cacheHitAttempts {
				return ChatResult{}, err
			}
			continue
		}
		if result.CacheHit {
			return result, nil
		}
	}
	return result, fmt.Errorf("Semantic Router did not report a cache hit after %d attempts", cacheHitAttempts)
}
