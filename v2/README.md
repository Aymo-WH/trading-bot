# Gordian v2 — market-neutral cross-sectional ETF research

The overview, results and design reasoning are in the [root README](../README.md).
This file is only the map of this folder.

| Path | What it is |
|---|---|
| `validation/` | The referee: backtester, CPCV, CSCV/PBO, DSR, canaries, trial ledger, lockbox, one-shot final eval. Frozen after its self-test (`validation/.frozen`). |
| `src/signals.py`, `src/decomposition.py`, `src/portfolio_m0.py`, `src/panel_factory.py` | v2 strategy side: Tier-1 signals, static/timing split, M0 combiner, panel builder |
| `src/core/`, other `src/*.py` | v1 code carried on the v2 branch for reuse (see `research/v1_forensics.md`) |
| `specs/` | Pre-registered, frozen experiment specs. A spec is never edited; it is superseded by a new versioned file |
| `research/decisions.md` | Append-only design decisions log (D1–D40) |
| `research/design.md` | The v2 design, with the evidence briefs it cites |
| `research/exp00*/`, `research/phase3_m0/` | Experiment runners and their committed `results.json` |
| `research/experiments.jsonl` | The trial ledger (every counted trial, including discards) |
| `data/panel/` | SHA-256 manifest of the frozen train/validation panel (through 2021-12-31); the prices are not redistributed |
| `tests/` | `fast/` unit tests, `data/` panel integrity, `referee/` calibration of the referee |

```bash
pip install -r requirements.lock.txt
python -m pytest tests/fast tests/data -q      # seconds
python -m pytest tests/referee -q              # slow: full-battery calibration
```
