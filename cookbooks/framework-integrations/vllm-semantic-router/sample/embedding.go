package main

import (
	"encoding/binary"
	"math"
	"strings"
)

// embedDim is the dimension of the deterministic stub embeddings used by this
// sample. The real vLLM Semantic Router uses 384 (BERT), 768 (Gemma), or 1024
// (Qwen3) dimensional model embeddings; here we use a small, dependency-free
// vector so the sample runs anywhere without a GPU or model download.
const embedDim = 256

// stubEmbedding produces a deterministic, normalized vector from text using
// character-trigram hashing. Texts that share substrings (e.g. paraphrases)
// land close together in cosine space, which is enough to demonstrate the
// Valkey vector-search mechanics the router relies on. It is NOT a substitute
// for a real semantic embedding model.
func stubEmbedding(text string) []float32 {
	vec := make([]float32, embedDim)
	s := strings.ToLower(strings.TrimSpace(text))
	if len(s) < 3 {
		s = s + "__" // pad so at least one trigram exists
	}
	runes := []rune(s)
	for i := 0; i+3 <= len(runes); i++ {
		trigram := string(runes[i : i+3])
		idx := fnv32(trigram) % embedDim
		vec[idx] += 1.0
	}
	return normalize(vec)
}

// normalize scales a vector to unit length so cosine similarity reduces to a
// dot product. A zero vector is returned unchanged to avoid division by zero.
func normalize(vec []float32) []float32 {
	var sum float64
	for _, v := range vec {
		sum += float64(v) * float64(v)
	}
	if sum == 0 {
		return vec
	}
	norm := float32(math.Sqrt(sum))
	for i := range vec {
		vec[i] /= norm
	}
	return vec
}

// fnv32 is the 32-bit FNV-1a hash, used to map trigrams to vector dimensions.
func fnv32(s string) int {
	const (
		offset = 2166136261
		prime  = 16777619
	)
	h := uint32(offset)
	for i := 0; i < len(s); i++ {
		h ^= uint32(s[i])
		h *= prime
	}
	// Mask the sign bit so the result is always non-negative: on 32-bit
	// targets a bare int(uint32) can wrap negative, which would panic a
	// caller indexing vec[idx].
	return int(h & 0x7FFFFFFF)
}

// float32ToBytes encodes a float32 slice as little-endian bytes, the wire
// format the valkey-search module expects for VECTOR fields. This matches the
// router's float32SliceToBytes helper.
func float32ToBytes(floats []float32) []byte {
	buf := make([]byte, len(floats)*4)
	for i, f := range floats {
		binary.LittleEndian.PutUint32(buf[i*4:], math.Float32bits(f))
	}
	return buf
}

// cosineDistanceToSimilarity converts the valkey-search COSINE distance (range
// [0, 2], 0 = identical) into a similarity score in [0, 1], mirroring the
// router's distanceToSimilarity helper (1 - d/2).
func cosineDistanceToSimilarity(distance float64) float64 {
	return 1.0 - distance/2.0
}
