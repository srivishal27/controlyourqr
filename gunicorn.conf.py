"""gunicorn configuration.

Tuned for a small VM serving a stateless, IO-light static site behind nginx.
"""

import multiprocessing
import os

# --- socket -------------------------------------------------------------- #
# Bound to loopback: nginx terminates TLS and proxies to us. The application
# port is never exposed to the internet.
bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8000")
backlog = 512

# --- workers ------------------------------------------------------------- #
workers = int(os.environ.get("WEB_CONCURRENCY", min(4, multiprocessing.cpu_count() * 2 + 1)))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", 4))
worker_tmp_dir = "/dev/shm"

timeout = 30
graceful_timeout = 30
keepalive = 5

# Recycle workers periodically as cheap insurance against slow leaks.
max_requests = 2000
max_requests_jitter = 200

# --- logging ------------------------------------------------------------- #
# journald captures stdout/stderr; systemd owns rotation and retention.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# Deliberately omits the query string and request body, and records no
# user-supplied content beyond the path.
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms "%(a)s"'

# --- process ------------------------------------------------------------- #
proc_name = "controlyourqr"
preload_app = True
forwarded_allow_ips = "127.0.0.1"
