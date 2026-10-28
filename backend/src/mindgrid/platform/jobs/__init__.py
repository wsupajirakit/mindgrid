"""Background jobs in PostgreSQL: enqueued in the same transaction as the change that needs
them, claimed with SKIP LOCKED, retried with backoff, run as the account that queued them."""
