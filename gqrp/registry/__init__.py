"""Trial registry — the statistical spine (spec §6, decision D4).

Append-only. Immutability is *structural*, not policy: DB-level triggers reject
UPDATE/DELETE, the writer exposes no mutate path, and the read-only client can
never write (that same client is what a Phase-2 agent would get). Cumulative
weighted N is computed live from rows, never stored as a mutable counter.
"""
