package com.example.springaivalkey;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Random;

/**
 * Shared utility methods for vector operations in tests and simulation scripts.
 */
public final class VectorTestUtils {

    private static final Random random = new Random(42);

    private VectorTestUtils() {
        // Utility class
    }

    /**
     * Generate a random float vector of the given dimension.
     */
    public static float[] randomVector(int dimension) {
        float[] vec = new float[dimension];
        for (int i = 0; i < dimension; i++) {
            vec[i] = random.nextFloat();
        }
        return vec;
    }

    /**
     * Normalize a vector to unit length. Returns unchanged if magnitude is near zero.
     */
    public static float[] normalizeVector(float[] vector) {
        float magnitude = 0.0f;
        for (float v : vector) {
            magnitude += v * v;
        }
        magnitude = (float) Math.sqrt(magnitude);
        if (magnitude < 1e-10f) {
            return vector;
        }
        float[] normalized = new float[vector.length];
        for (int i = 0; i < vector.length; i++) {
            normalized[i] = vector[i] / magnitude;
        }
        return normalized;
    }

    /**
     * Convert a float array to little-endian bytes for Valkey VECTOR fields.
     */
    public static byte[] floatArrayToBytes(float[] floats) {
        ByteBuffer buffer = ByteBuffer.allocate(floats.length * 4)
            .order(ByteOrder.LITTLE_ENDIAN);
        for (float f : floats) {
            buffer.putFloat(f);
        }
        return buffer.array();
    }
}
