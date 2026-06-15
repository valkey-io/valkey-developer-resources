package main

import (
	"context"
	"strings"

	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/models"
	"github.com/valkey-io/valkey-glide/go/v2/options"
)

// specialChars are the punctuation/whitespace characters the valkey-search TAG
// query tokenizer treats as separators; they must be backslash-escaped to be
// matched literally inside @field:{value}. This matches the router's
// escapeTagValue helper, with the backtick added as defense-in-depth since
// valkey-search also treats it as an alternate quoting character inside TAG
// queries.
const specialChars = " \t,.<>{}[]\"':;!@#$%^&*()-+=~|/\\`"

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
// DEL. It uses the native typed Scan API (never KEYS, which is O(N) and blocks
// the server). This mirrors the router's deleteKeysByPrefix cleanup.
func deleteByPrefix(ctx context.Context, client *glide.Client, prefix string) {
	cursor := models.NewCursor()
	scanOpts := *options.NewScanOptions().SetMatch(prefix + "*").SetCount(100)
	for {
		result, err := client.ScanWithOptions(ctx, cursor, scanOpts)
		if err != nil {
			return
		}
		if len(result.Data) > 0 {
			_, _ = client.Del(ctx, result.Data)
		}
		cursor = result.Cursor
		if cursor.IsFinished() {
			return
		}
	}
}
