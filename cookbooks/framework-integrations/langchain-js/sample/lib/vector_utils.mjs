/**
 * Shared vector utilities for LangChain.js + Valkey cookbook sample.
 */

/** Convert a number array to a Buffer of Float32 bytes for Valkey vector storage. */
export function vectorToBuffer(vector) {
  return Buffer.from(new Float32Array(vector).buffer);
}

/**
 * Standard vector field schema for FT.CREATE.
 * @param {object} options
 * @param {string} [options.name="embedding"] - Field name
 * @param {string} [options.algorithm="HNSW"] - HNSW or FLAT
 * @param {string} [options.distanceMetric="COSINE"] - COSINE, L2, or IP
 * @param {number} [options.dimensions=4] - Vector dimensions
 */
export function vectorFieldSchema({
  name = "embedding",
  algorithm = "HNSW",
  distanceMetric = "COSINE",
  dimensions = 4,
} = {}) {
  return {
    type: "VECTOR",
    name,
    alias: name,
    attributes: {
      algorithm,
      distanceMetric,
      type: "FLOAT32",
      dimensions,
    },
  };
}
