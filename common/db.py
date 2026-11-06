"""Connection to PostgreSQL, shared by the loader, the dashboard and the benchmark.

The settings come from the .env file, which docker compose passes to every container.
Inside docker compose the database host is "db" (the service name), not "localhost":
inside a container, localhost is the container itself.
"""
import os
import time

import psycopg


def connect(retries: int = 30):
    """Open a connection, trying again once a second if the database is not ready yet."""
    for attempt in range(retries):
        try:
            return psycopg.connect(
                host=os.environ.get("POSTGRES_HOST", "db"),
                port=int(os.environ.get("POSTGRES_PORT", 5432)),
                dbname=os.environ["POSTGRES_DB"],
                user=os.environ["POSTGRES_USER"],
                password=os.environ["POSTGRES_PASSWORD"],
            )
        except psycopg.OperationalError:
            if attempt == retries - 1:
                raise
            time.sleep(1)
