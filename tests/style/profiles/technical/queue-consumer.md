# Queue consumer: behaviour specification

This document specifies the behaviour of the ingest queue consumer. It is
normative for the consumer implementation and for anything that depends on the
consumer's delivery guarantees.

The consumer reads messages from the ingest queue, applies the transform
pipeline, and writes the result to the document store. It is the only component
permitted to acknowledge a message on the ingest queue.

## Terminology

- **Message** — one unit of work on the ingest queue. A message carries a
  document identifier, a revision number and a payload digest.
- **Lease** — the period during which a message is invisible to other consumers
  after being received. Lease duration is 300 seconds.
- **Attempt** — one delivery of a message to one consumer. Attempts are counted
  per message and are not reset by a lease expiry.
- **Terminal state** — a message state from which no further attempt is made.
  The terminal states are `acknowledged` and `dead-lettered`.

The terms above are used with these meanings throughout. Where a term appears
without qualification it carries the meaning defined here.

## Delivery guarantees

The consumer provides at-least-once delivery. It does not provide exactly-once
delivery and no part of the system may assume that it does.

A message may be delivered more than once when:

1. The consumer receives a message and completes processing, but fails before
   acknowledging it.
2. The lease expires before processing completes.
3. The broker redelivers after a partition change.

Because a message may be delivered more than once, the transform pipeline must be
idempotent with respect to the document identifier and revision number. The store
write is a conditional put on the revision number, so a repeated delivery of the
same revision is a no-op rather than a duplicate.

## Processing sequence

For each received message the consumer performs the following steps in order:

1. Validate the message envelope. Reject malformed envelopes immediately; see
   *Rejection* below.
2. Verify the payload digest against the payload. A digest mismatch is a
   rejection, not a retry: the payload will not become correct on a second
   attempt.
3. Load the current revision for the document identifier from the store.
4. If the current revision is greater than or equal to the message revision,
   acknowledge and stop. This is the idempotent path.
5. Apply the transform pipeline.
6. Write the result with a conditional put on the current revision.
7. If the conditional put fails, return to step 3. Retry the compare-and-set at
   most three times, then treat the message as contended; see *Contention*.
8. Acknowledge the message.

The consumer must not acknowledge before step 8. Acknowledging earlier converts
at-least-once delivery into at-most-once delivery, silently.

## Rejection

A rejected message is dead-lettered on the first attempt. Rejection is used only
where a further attempt cannot succeed:

- malformed envelope
- payload digest mismatch
- unknown document identifier namespace
- payload larger than 8 MiB

Rejection is not used for transform failures, store failures or timeouts. Those
are retried.

## Retry

A message that fails for a retryable reason is returned to the queue with an
incremented attempt count. Backoff is exponential with jitter:

```
delay = min(2 ** attempt, 900) * (0.5 + random())
```

After 8 attempts the message is dead-lettered. The attempt count is carried on
the message and is not reset by a lease expiry, so a message that repeatedly
times out is dead-lettered rather than retried indefinitely.

## Contention

Contention is the case where the conditional put fails three times because
another writer is advancing the same document identifier.

A contended message is returned to the queue with backoff but does not increment
the attempt count. Contention is a property of concurrent load, not of the
message, and counting it against the attempt limit would dead-letter valid
messages during a busy period.

Contention is recorded on the `ingest_contention_total` counter, labelled by
namespace.

## Lease handling

The lease duration is 300 seconds. The consumer extends the lease every 120
seconds while processing continues.

If lease extension fails, the consumer abandons processing immediately and does
not write to the store. A consumer that continues after losing its lease may
write a stale revision over a newer one, which the conditional put is designed to
prevent but which should not be relied upon as the only defence.

The consumer does not extend a lease more than 10 times. A message requiring more
than 20 minutes of processing is treated as stuck and is dead-lettered.

## Shutdown

On receiving SIGTERM the consumer:

1. Stops receiving new messages.
2. Continues processing in-flight messages.
3. Waits up to 45 seconds for in-flight messages to reach a terminal state.
4. Abandons any remaining in-flight messages without acknowledging them.
5. Exits with status 0.

Abandoned messages become visible again when their lease expires. They are not
lost.

## Configuration

| Setting | Default | Range |
|---|---|---|
| `lease_seconds` | 300 | 60–900 |
| `extension_interval_seconds` | 120 | 30–450 |
| `max_extensions` | 10 | 1–30 |
| `max_attempts` | 8 | 1–20 |
| `contention_retries` | 3 | 1–10 |
| `shutdown_grace_seconds` | 45 | 5–120 |
| `prefetch` | 16 | 1–256 |

`extension_interval_seconds` must be less than half of `lease_seconds`. The
consumer refuses to start if it is not.

## Metrics

The consumer exports:

- `ingest_messages_received_total`
- `ingest_messages_acknowledged_total`
- `ingest_messages_dead_lettered_total`, labelled by reason
- `ingest_contention_total`
- `ingest_processing_seconds`, a histogram
- `ingest_lease_extensions_total`
- `ingest_lease_extension_failures_total`

A rising `ingest_lease_extension_failures_total` alongside a flat
`ingest_messages_acknowledged_total` indicates broker connectivity loss rather
than a transform problem, and should be triaged against the broker.

## Out of scope

This specification does not cover the transform pipeline, the store schema, the
producer, or the dead-letter drain. The dead-letter drain is specified separately
and is not part of the consumer.

## Interaction with the dead-letter queue

Dead-lettered messages are written to the dead-letter queue with the original
envelope intact and three additional headers: the terminal reason, the attempt
count at the point of dead-lettering, and the identifier of the consumer instance
that made the decision.

The consumer never reads from the dead-letter queue. Replaying a dead-lettered
message is the drain's responsibility and requires an operator action, because a
message that failed eight times is more likely to indicate a defect than a
transient fault, and automatic replay would hide it.

## Ordering

The consumer makes no ordering guarantee.

Messages for the same document identifier may be processed concurrently by
different consumer instances, and may be processed out of the order in which they
were produced. The conditional put in step 6 is what makes this safe: a message
carrying an older revision than the store already holds takes the idempotent path
at step 4 and is acknowledged without a write.

Producers that require ordering must encode it in the revision number. They must
not rely on queue order, prefetch size or consumer count, none of which is
specified here and all of which change under load.

## Startup

On start the consumer:

1. Reads its configuration and validates it. Invalid configuration is a startup
   failure, not a warning.
2. Establishes a broker connection. A connection failure is retried with the
   same backoff used for messages.
3. Registers with the store and verifies that the transform pipeline version it
   carries matches the version the store expects.
4. Begins receiving.

Step 3 is the one that matters operationally. A consumer whose pipeline version
disagrees with the store refuses to start rather than writing documents in a
format the store will later reject.
