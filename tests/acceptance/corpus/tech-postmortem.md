# Incident 2026-081: checkout latency

## Summary

Between 09:12 and 10:47 UTC on 3 September 2026, checkout requests took up to 14 seconds. About 2,300 customers were affected. No payments were lost.

## Cause

A configuration change deployed at 09:05 reduced the database connection pool from 50 to 5. Under normal morning load the pool was exhausted and requests queued.

## Resolution

The change was reverted at 10:41. Latency returned to normal within six minutes.

## Actions

The deployment pipeline will now reject pool sizes below 20. Additionally, an alert will fire when the queue exceeds 100 requests for more than 60 seconds.
