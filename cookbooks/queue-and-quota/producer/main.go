// Command producer submits inference jobs to llm-d's async batch queue in Valkey
// and (optionally) reads their results back. It is a thin wrapper around llm-d's
// public producer library — github.com/llm-d/llm-d-async/producer — so the jobs
// that land in Valkey are exactly what the real async processor expects.
//
// Build and run it as a container (see the cookbook README); the reader does not
// need a Go toolchain to run the cookbook.
//
// Flags only — no positional subcommand (a leading positional would make Go's
// flag package stop parsing before the flags).
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/llm-d/llm-d-async/api"
	"github.com/llm-d/llm-d-async/producer"
)

func main() {
	redisURL := flag.String("redis-url", "redis://valkey:6379", "Valkey/Redis URL")
	queue := flag.String("request-queue", "request-sortedset", "request sorted set name")
	resultQueue := flag.String("result-queue", "result-list", "result list name")
	n := flag.Int("n", 3, "number of jobs to submit")
	model := flag.String("model", "test-model", "model name for the request payload")
	userid := flag.String("userid", "", "if set, store it in each job's metadata[userid] so the quota gate keys on it")
	readResults := flag.Bool("read-results", false, "after submitting, block and print each result")
	flag.Parse()

	p, err := producer.NewRedisSortedSetProducer(producer.RedisSortedSetConfig{
		RedisURL:         *redisURL,
		RequestQueueName: *queue,
		ResultQueueName:  *resultQueue,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "new producer: %v\n", err)
		os.Exit(1)
	}
	defer p.Close() //nolint:errcheck

	ctx := context.Background()
	now := time.Now()
	for i := 0; i < *n; i++ {
		id := fmt.Sprintf("req-%d-%d", now.Unix(), i)
		payload, _ := json.Marshal(map[string]any{
			"model":      *model,
			"prompt":     fmt.Sprintf("hello from job %d", i),
			"max_tokens": 8,
		})
		req := &api.RequestMessage{
			ID:       id,
			Created:  now.Unix(),
			Deadline: now.Add(5 * time.Minute).Unix(),
			Payload:  payload,
			Endpoint: "/v1/completions",
			Model:    *model,
		}
		// The quota gate keys on a request attribute (default "userid"). A job
		// with no such metadata is always admitted, so set it to exercise the gate.
		if *userid != "" {
			req.Metadata = map[string]string{"userid": *userid}
		}
		if err := p.SubmitRequest(ctx, req); err != nil {
			fmt.Fprintf(os.Stderr, "submit %s: %v\n", id, err)
			os.Exit(1)
		}
		fmt.Printf("submitted %s\n", id)
	}

	if !*readResults {
		return
	}
	for i := 0; i < *n; i++ {
		rctx, cancel := context.WithTimeout(ctx, 60*time.Second)
		res, err := p.GetResult(rctx)
		cancel()
		if err != nil {
			fmt.Fprintf(os.Stderr, "get result: %v\n", err)
			os.Exit(1)
		}
		fmt.Printf("result: id=%s status=%d body=%.120s\n", res.ID, res.StatusCode, string(res.Payload))
	}
}
