"""Metrics panel (spec §8).

`purgedcv` is isolated behind this package — no purgedcv type escapes it (the
same wrapper discipline as the vectorbt engine, architecture seam 6). The rest
of the system sees plain floats and a `MetricsPanel`.
"""
