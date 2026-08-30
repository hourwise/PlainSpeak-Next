# Connection pooling

A connection pool keeps a small number of database connections open and hands
them out on request. Opening a connection is expensive: a TCP handshake, an
authentication round trip, and often a TLS negotiation on top. Reusing one
avoids all of that.

Size the pool to the database, not to the application. A server configured for
100 connections will not go faster because forty application instances each
opened twenty. It will go slower, and then it will start refusing connections.

Two failure modes are worth planning for.

The first is exhaustion. Every connection is checked out, and the next caller
waits. If the wait has no timeout, a slow query in one place becomes a stalled
request everywhere. Set one.

The second is the stale connection. A pooled connection that has been idle for
an hour may have been closed by a firewall without either side noticing. A
liveness check on checkout costs a round trip and saves a confusing error much
later.

Neither problem is subtle once you have seen it. Both are invisible in testing,
where the pool is never under pressure and nothing is idle for long.
