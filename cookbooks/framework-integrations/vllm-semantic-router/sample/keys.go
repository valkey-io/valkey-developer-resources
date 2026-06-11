package main

import (
	"context"
	"fmt"
	"strings"

	glide "github.com/valkey-io/valkey-glide/go/v2"
)

// specialChars are the punctuation/whitespace characters the valkey-search TAG
// query tokenizer treats as separators; they must be backslash-escaped to be
// matched literally inside @field:{value}. This matches the router's
// escapeTagValue helper.
const specialChars = " \t,.<>{}[]\"':;!@#$%^&*()-+=~|/\\"

// escapeTagValue backslash-escapes special characters so a value can be used
// literally inside a TAG query expression.
func escapeTagValue(s string) string {
	var b strings.Builder
	b.Grow(len(s) + 8)
	for _, c := range s {
		if strings.ContainsRune(specialChars, c) {
			b.WriteByte('\\')
		}
		b.WriteRune(c)
	}
	return b.String()
}

// deleteByPrefix removes all keys matching prefix* using cursor-based SCAN +
// DEL. It never uses KEYS, which is O(N) and blocks the server. This mirrors
// the router's deleteKeysByPrefix cleanup.
func deleteByPrefix(ctx context.Context, client *glide.Client, prefix string) {
	cursor := "0"
	pattern := prefix + "*"
	for {
		result, err := client.CustomCommand(ctx, []string{"SCAN", cursor, "MATCH", pattern, "COUNT", "100"})
		if err != nil {
			return
		}
		arr, ok := result.([]interface{})
		if !ok || len(arr) < 2 {
			return
		}
		cursor = fmt.Sprint(arr[0])

		var keys []string
		if keyList, ok := arr[1].([]interface{}); ok {
			for _, k := range keyList {
				if s, ok := k.(string); ok {
					keys = append(keys, s)
				}
			}
		}
		if len(keys) > 0 {
			_, _ = client.Del(ctx, keys)
		}
		if cursor == "0" {
			return
		}
	}
}
