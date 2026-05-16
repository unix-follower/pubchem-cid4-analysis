# ==========================================
# Stage 1: Build the C Extension Binaries
# ==========================================
FROM postgres:18.4 AS builder

# Install compilation tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    postgresql-server-dev-18 \
    libreadline-dev \
    zlib1g-dev \
    bison \
    flex \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# 1. Install pgvector
RUN git clone --depth 1 https://github.com/pgvector/pgvector.git && \
    cd pgvector && \
    make && \
    make install DESTDIR=/build/output

# 2. Install Apache AGE
RUN git clone --depth 1 https://github.com/apache/age.git && \
    cd age && \
    make && \
    make install DESTDIR=/build/output


# ==========================================
# Stage 2: Build the Final Database Image
# ==========================================
FROM postgres:18.4

# Copy compiled extension libraries
COPY --from=builder /build/output /

# To automate extension loading
COPY ./init-extensions.sql /docker-entrypoint-initdb.d/

EXPOSE 5432
