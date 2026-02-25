FROM php:8.3-cli

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    make \
    autoconf \
    pkg-config \
    libssl-dev \
    libprotobuf-c-dev \
    protobuf-c-compiler \
    python3 \
    unzip \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install cbindgen
RUN cargo install cbindgen

# Install protobuf compiler
RUN PB_REL="https://github.com/protocolbuffers/protobuf/releases" && \
    curl -LO $PB_REL/download/v3.20.3/protoc-3.20.3-linux-x86_64.zip && \
    unzip protoc-3.20.3-linux-x86_64.zip -d /usr/local && \
    rm protoc-3.20.3-linux-x86_64.zip

# Clone and build valkey-glide-php from source
RUN git clone --recurse-submodules https://github.com/valkey-io/valkey-glide-php.git /tmp/valkey-glide-php && \
    cd /tmp/valkey-glide-php && \
    git checkout v1.0.0 && \
    python3 utils/patch_proto_and_rust.py && \
    cd valkey-glide/ffi && \
    cargo build --release && \
    cd /tmp/valkey-glide-php && \
    phpize && \
    ./configure --enable-valkey-glide && \
    make && \
    make install && \
    cd / && \
    rm -rf /tmp/valkey-glide-php

# Enable the extension
RUN echo "extension=valkey_glide" > /usr/local/etc/php/conf.d/valkey_glide.ini

# Verify installation
RUN php -m | grep valkey_glide

WORKDIR /app

CMD ["php", "-a"]
