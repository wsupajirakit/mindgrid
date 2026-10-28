"""Events: one neutral outbound pipeline for every module and project. A change records
its event in the same transaction (outbox); the database fans it out to the subscriptions
that want it and to one-shot callbacks; the worker delivers CloudEvents JSON signed per
Standard Webhooks, one in-flight delivery per receiver, retried, with a dead-letter state."""
