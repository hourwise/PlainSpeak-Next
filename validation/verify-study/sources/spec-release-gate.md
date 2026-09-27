# Release gate

A release may be promoted to production only if every required check has
passed. The error rate on the canary must stay below 0.5% for 2 hours before
promotion.

If the p99 latency exceeds 800 ms, the release must be rolled back. Rollbacks
do not require approval; promotions require approval from the on-call engineer.
