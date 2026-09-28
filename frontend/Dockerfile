# Build stage
FROM node:20-alpine AS builder
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy source code
COPY . .

# Sentry for the browser (src/utils/observability.ts): baked into the
# build, empty means off. docker-compose passes them from .env.
ARG VITE_SENTRY_DSN=""
ARG VITE_SENTRY_RELEASE=""
ARG VITE_SENTRY_ENVIRONMENT="production"
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN VITE_SENTRY_RELEASE=$VITE_SENTRY_RELEASE VITE_SENTRY_ENVIRONMENT=$VITE_SENTRY_ENVIRONMENT

# Build the application
RUN npm run build

# Production stage - copy files to mounted volume
FROM alpine:latest

# Copy built files from builder
COPY --from=builder /app/dist /static

# Copy files to mounted volume on startup
# The volume is mounted at /usr/share/nginx/html
CMD ["sh", "-c", "cp -r /static/* /usr/share/nginx/html/ && tail -f /dev/null"]

