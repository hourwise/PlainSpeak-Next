# Runbook: rebuilding the search index

Use this runbook when the search index must be rebuilt from the document store.
A rebuild takes about 90 minutes for the current corpus and can be run against a
live system.

Do not run this runbook to fix a single stale document. Use the targeted reindex
endpoint instead.

## When to rebuild

Rebuild when any of the following is true:

- The analyser configuration has changed.
- The index mapping has changed in a way that cannot be applied in place.
- Index corruption has been confirmed by the consistency checker.
- The index is more than 48 hours behind the document store and the ingest
  backlog is empty.

Do not rebuild while the ingest backlog is non-empty. The rebuild reads from the
document store, so a non-empty backlog means the store itself is behind and the
rebuild would produce an index that is correct with respect to a stale source.

## Before you start

Confirm each of the following. Record the values; you will compare against them
at the end.

1. Ingest backlog is zero: `ingest_queue_depth` on the ingest dashboard.
2. Document count in the store: `SELECT count(*) FROM documents WHERE deleted_at
   IS NULL;`
3. Document count in the live index: `GET /_index/current/_count`.
4. Disk headroom on each index node is at least 2.5 times the current index size.
   A rebuild builds the new index alongside the old one.
5. No other rebuild is running: `GET /_admin/rebuilds` returns an empty list.

If step 4 fails, stop. There is no safe way to run a rebuild without headroom for
both indexes, and freeing space during a rebuild is worse than delaying it.

## Procedure

### 1. Create the target index

```
POST /_admin/index
{"name": "documents-{{date}}", "mapping": "current"}
```

The response contains a rebuild identifier. Record it. Every subsequent step
refers to this identifier.

### 2. Start the backfill

```
POST /_admin/rebuilds/{{id}}/start
```

The backfill reads the document store in primary key order and writes to the
target index. It runs at a fixed rate of 400 documents per second, which is
deliberately below capacity so that live traffic is unaffected.

### 3. Monitor

Watch three things:

- `rebuild_documents_written_total` should rise steadily. A flat counter for more
  than two minutes means the backfill has stalled.
- `search_query_latency_p99` on the live index should not change. If it rises by
  more than 20%, throttle the rebuild (see *Throttling*).
- `rebuild_errors_total` should stay at zero. Any non-zero value needs
  investigating before the cutover, not after.

Expect roughly 90 minutes. The progress endpoint gives an estimate:

```
GET /_admin/rebuilds/{{id}}
```

### 4. Let the tail catch up

The backfill reads a snapshot. Documents written after the snapshot are applied
from the change log once the backfill completes. This is automatic.

Wait until `rebuild_lag_seconds` is below 5. This usually takes two to three
minutes. Do not proceed while lag is above 30 seconds.

### 5. Verify before cutover

Run the verification job:

```
POST /_admin/rebuilds/{{id}}/verify
```

It compares document counts, samples 2,000 documents at random and checks that
each is present in the target index with a matching digest.

Verification must pass. A count mismatch of even one document means the rebuild
is not equivalent to the store, and cutting over would make that difference
permanent and invisible.

### 6. Cut over

```
POST /_admin/rebuilds/{{id}}/promote
```

Promotion is an alias switch. It is atomic and takes effect within one second on
all nodes. In-flight queries complete against whichever index they started on.

### 7. Confirm

Compare against the values you recorded before starting:

- Document count in the new live index should equal the store count, allowing for
  documents written during the rebuild.
- `search_query_latency_p99` should be at or below the pre-rebuild value.
- `search_results_empty_ratio` should not have risen. A rise here is the clearest
  signal that the analyser configuration did something unintended.

Watch for 15 minutes before considering the rebuild complete.

### 8. Retire the old index

Leave the old index in place for 24 hours. Then:

```
DELETE /_admin/index/{{old-name}}
```

Do not delete earlier. Rollback after promotion is an alias switch back, and it
is only available while the old index exists.

## Throttling

If live query latency rises during the backfill:

```
POST /_admin/rebuilds/{{id}}/rate {"documents_per_second": 150}
```

The rate can be changed at any time and takes effect within ten seconds. Rate
changes do not restart the backfill.

## Rollback

Before promotion, abort:

```
POST /_admin/rebuilds/{{id}}/abort
```

The target index is deleted. The live index is untouched throughout, so an abort
before promotion has no effect on service.

After promotion, and within 24 hours:

```
POST /_admin/index/{{old-name}}/promote
```

This switches the alias back. It is the same atomic operation as promotion.

After the old index has been deleted, there is no rollback. The remedy is another
rebuild.

## Known failure modes

**Backfill stalls at a fixed document count.** Usually a single document that the
analyser cannot process. Find it in the rebuild error log, fix or exclude it, and
resume with `POST /_admin/rebuilds/{{id}}/resume`.

**Verification fails on count but samples pass.** Almost always deleted documents
that the backfill included because the snapshot predates the delete. Re-run
verification; if it fails twice, abort.

**Lag never falls below 30 seconds.** The change log is being written faster than
it can be applied. Throttle ingest rather than the rebuild.

## Running against a replica

A rebuild can be run against a read replica of the document store rather than the
primary. Use this when the primary is under sustained load.

Set the source explicitly when creating the target index:

```
POST /_admin/index
{"name": "documents-{{date}}", "mapping": "current", "source": "replica"}
```

Two consequences follow. The snapshot is taken on the replica, so the tail
catch-up in step 4 will be longer by the replica lag at the time of the snapshot.
And the verification job in step 5 reads from the primary regardless of the
source, so a large replica lag can cause verification to fail on count.

Check replica lag before starting. Above 60 seconds, use the primary.

## Concurrent rebuilds

Only one rebuild may run at a time. The admin API refuses a second one.

This is a deliberate restriction rather than a technical limit. Two rebuilds
would compete for the same disk headroom, and the failure mode when headroom runs
out mid-rebuild is that both fail and the live index is left as the only copy.

If a rebuild is stuck and a new one is needed, abort the first explicitly. Do not
wait for a timeout; there is not one.

## Escalation

Escalate to the search team if:

- verification fails twice with a count mismatch
- `rebuild_errors_total` exceeds 50
- promotion returns a non-200 status
- query latency does not return to baseline within 30 minutes of promotion

Include the rebuild identifier in any escalation. Every log line for the rebuild
carries it.
