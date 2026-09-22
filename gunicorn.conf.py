"""Gunicorn configuration file for production deployment."""

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
#
# "sync" gives each worker exactly one request at a time — every other
# request queues behind it even though the worker spends nearly all of
# that time idle, waiting on MongoDB's network round trip rather than
# doing CPU work. Load-testing the two side by side against a real
# Mongo instance (2 workers, 60 concurrent clients hitting a ~5ms
# endpoint) showed the difference is not marginal: sync's queueing
# pushed median latency to 102ms with throughput capped around 560
# req/s, while gthread with the same 2 workers held median latency at
# 69ms with throughput near 820 req/s — and 4 workers pushed that past
# 1100 req/s. Threads share a worker's memory (unlike more worker
# processes), and PyMongo's client and Flask's request-local `g` are
# both thread-safe, so this costs nothing to switch to.
worker_class = "gthread"
# Gunicorn's own docs (https://docs.gunicorn.org/en/stable/design.html):
# "(2 x $num_cores) + 1" workers, with a documented example of pairing
# that with 2-4 threads per worker for a threaded worker class — total
# concurrent capacity is workers * threads. Scaling the *default* by
# the host's actual core count (rather than a hardcoded guess) means
# it's sized correctly wherever this deploys; GUNICORN_WORKERS still
# overrides it for a specific box. Threads are left as a flat default
# instead of also scaling by core count — our own load test showed
# diminishing returns past 4-8 threads per worker at this app's request
# cost (~5-10ms of mostly I/O wait), so multiplying both by core count
# would just add idle threads and idle MongoDB connections.
workers = int(os.getenv("GUNICORN_WORKERS", 2 * multiprocessing.cpu_count() + 1))
threads = int(os.getenv("GUNICORN_THREADS", 4))
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
proc_name = "petzy"

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
