# Multi-stage Dockerfile: Valkey 9.1.0 + ValkeySearch module
#
# Stage 1 (builder): Clones and compiles ValkeySearch from source.
# Stage 2 (runtime): Minimal Valkey image with only the compiled module.
#
# Build: docker compose up -d (or docker build -f Dockerfile.valkey-search -t flicenjoyer-valkey .)
# NOTE: ValkeySearch compilation is memory-hungry. Jobs capped at 8 to avoid OOM.

# --- Builder stage: compile ValkeySearch ---
FROM debian:trixie-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git pkg-config ninja-build \
    libssl-dev libsystemd-dev autoconf automake libtool ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Clone ValkeySearch — shallow clone for speed
ARG VALKEY_SEARCH_REPO=https://github.com/valkey-io/valkey-search.git
ARG VALKEY_SEARCH_BRANCH=main
RUN git clone --depth 1 --branch ${VALKEY_SEARCH_BRANCH} ${VALKEY_SEARCH_REPO}

WORKDIR /build/valkey-search

# Submodules change less often than source — separate layer for caching
RUN git submodule update --init --recursive

# Configure and build (jobs capped to limit memory usage)
# Disable unit tests to reduce memory — test compilation OOMs on <8GB Docker
ARG BUILD_JOBS=4
RUN sed -i 's/-DBUILD_UNIT_TESTS=ON/-DBUILD_UNIT_TESTS=OFF/' build.sh
RUN ./build.sh --configure --jobs=${BUILD_JOBS}
RUN ./build.sh --jobs=${BUILD_JOBS}

# --- Runtime stage: minimal Valkey with ValkeySearch module ---
FROM valkey/valkey:9.1.0-rc1

# Copy only the compiled module from builder
COPY --from=builder /build/valkey-search/.build-release/libsearch.so /usr/lib/valkey/libsearch.so

# Run as the default valkey user (non-root, inherited from base image)
EXPOSE 6379

HEALTHCHECK --interval=5s --timeout=3s --retries=3 \
    CMD ["valkey-cli", "PING"]

CMD ["valkey-server", "--loadmodule", "/usr/lib/valkey/libsearch.so"]
