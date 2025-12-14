"""Gunicorn configuration file for production deployment."""

import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
# Default to 2 workers (can be overridden via GUNICORN_WORKERS env var)
workers = int(os.getenv("GUNICORN_WORKERS", 2))
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"  # Log to stderr
# Use LOG_LEVEL from environment, convert to lowercase for Gunicorn (default: info)
log_level = os.getenv("LOG_LEVEL", "INFO").lower()
loglevel = log_level if log_level in ["debug", "info", "warning", "error", "critical"] else "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "cat-health-control"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (uncomment if using SSL)
# keyfile = None
# certfile = None

# Performance
preload_app = True
max_requests = 1000
max_requests_jitter = 50

