@AGENTS.md

## Claude-specific

**Doc-driven project.** "continue" / "resume" with no other context = read `docs/STATE.md` and do its next concrete step. Update `docs/STATE.md` before finishing; new architectural decision → `docs/decisions.md` (numbered) + reference it.

**Model routing (per global config):**
- Opus for: registry immutability design, universe/data-model work, the statistical-gate math — anything load-bearing and hard to reverse.
- Sonnet/Haiku for: mechanical implementation of already-designed functions, tests, wrappers, formatting.

**Session split rule:** data/universe work, registry work, and backtest/metrics work each get their own session — they're the three heavy, semi-independent tracks.

**Verification:** never say "done" without evidence. For the registry, prove immutability (show an UPDATE being rejected). For the universe, prove a delisted asset stays until its delisting date. For metrics, show DSR matching the reference implementation.
