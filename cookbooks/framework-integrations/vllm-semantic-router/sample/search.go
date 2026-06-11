package main

import "strconv"

// parseSearchDocs extracts the per-document field maps from a valkey-glide
// FT.SEARCH response. The Go GLIDE client (v2) returns results as:
//
//	[totalCount, map[docKey]map[field]value, ...]
//
// where the first element is the total match count and subsequent elements are
// maps of document key → field map. This is the same shape the router parses in
// its parseSearchResults / valkeyIterateSearchDocs helpers.
func parseSearchDocs(result any) []map[string]interface{} {
	arr, ok := result.([]interface{})
	if !ok || len(arr) < 1 {
		return nil
	}
	if toInt64(arr[0]) == 0 {
		return nil
	}

	var docs []map[string]interface{}
	for i := 1; i < len(arr); i++ {
		docMap, ok := arr[i].(map[string]interface{})
		if !ok {
			continue
		}
		for _, docValue := range docMap {
			if fields, ok := docValue.(map[string]interface{}); ok {
				docs = append(docs, fields)
			}
		}
	}
	return docs
}

// toInt64 normalizes the numeric types valkey-glide may return for the
// FT.SEARCH total-count header.
func toInt64(v interface{}) int64 {
	switch val := v.(type) {
	case int64:
		return val
	case float64:
		return int64(val)
	case string:
		n, _ := strconv.ParseInt(val, 10, 64)
		return n
	default:
		return 0
	}
}
