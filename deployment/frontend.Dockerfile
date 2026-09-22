# ── Frontend Dockerfile ─────────────────────────────────────────────
# Multi-stage: build with Node, serve with Nginx
# Build context: project root (../)
# ────────────────────────────────────────────────────────────────────

# ---------- Stage 1: build ----------
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first for better layer caching
COPY frontend/package.json frontend/package-lock.json ./

RUN npm ci --production=false

# Copy frontend source
COPY frontend/ .

# Set the API URL at build time (can be overridden via build-arg)
ARG VITE_API_URL=http://localhost:8000/api/v1
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# ---------- Stage 2: serve ----------
FROM nginx:1.25-alpine AS runtime

LABEL maintainer="Automotive UDS AI Team"
LABEL description="React frontend for Automotive UDS Diagnostics Assistant"

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config from deployment folder (context is project root)
COPY deployment/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose HTTP port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
