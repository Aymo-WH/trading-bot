# trading-bot: two generations of a systematic trading research pipeline

This repo holds two attempts at the same question: can a small, carefully validated
pipeline find a tradable edge in liquid ETFs? `v1/` is the first attempt, a
directional ML system. `v2/` is the rebuild, designed around what v1 got wrong.
Both are research code. Neither has been traded with real money.

## v1: directional meta-labeling (`v1/`)

**Problem.** Predict short-horizon direction on hourly data for 7 assets (sector ETFs,
crypto majors, TQQQ/VXX), then size bets with RL.

**Approach.** López de Prado's toolkit: information-driven dollar bars, fractional
differentiation (FFD), point-in-time PCA, triple-barrier labels, an XGBoost direction
classifier feeding a PPO bet-sizing agent, and PBO via CSCV as the deployment gate.
Details and the module map are in [v1/README.md](v1/README.md); the write-up of the
engineering failures and fixes is `v1/docs/methodology.tex`.

**Result (negative).**

| Experiment | OOS 15-bar net EV | OOS win rate |
|---|---|---|
| 4 microstructural features, random split | −0.19% | 50.8% |
| + purged temporal split + regularization | −1.12% | 49.2% |
| + price/momentum/vol/FFD enrichment (11 features) | −0.94% | 42.7% |

Replacing the random split with a purged, embargoed temporal split dropped the
*in-sample* win rate from 63.6% to 53.7%: most of the apparent edge was leakage. PBO
came out at 0.65 (fail).

**What v1 taught me** (from a line-by-line audit of the v1 code, `v2/research/v1_forensics.md`):
- The overfitting gate itself ran on the quarantined test set, and its "trials" were a
  confidence-threshold grid on one model, which understates selection bias.
- FFD's `d` was chosen by an ADF test on the full series, test dates included.
- The RL gym was long-only by construction (`Box(0, 1)` actions), its risk-penalty
  coefficients were all 0, and the reward paid a +50% bonus on positive returns.
- Live inference could not have run: it fed 4 features to a scaler fit on 11.
- The gym used the module-level `random`, so seeding was a no-op and parallel workers
  replayed identical episodes.
- 1 bp/side costs were optimistic.
- The deeper lesson: besides the code defects, nothing in the process stopped me from
  looking at test data, re-running, and counting only the runs I liked. v2 fixes the
  process first.

## v2: pre-registered, market-neutral cross-sectional research (`v2/`)

**Problem.** Rank 70 liquid ETFs (bonds, broad US, sectors, styles, countries,
commodities, REITs, FX) by expected 5-day return, weekly, in a dollar- and beta-neutral
book. Ranking, not direction.

**Approach.** I built the referee before any alpha work, froze it, and made every
result go through it.

- **Validation referee (`v2/validation/`).** Vectorized panel backtester, CPCV (N=8,
  k=2, purge 5d, embargo 10d), CSCV/PBO (S=16, 12,870 combinations), Deflated Sharpe
  with effective trial count, and a canary suite (within-date label shuffle, row-block
  time shuffle, ±26-week feature shift, synthetic null panel, planted-signal panel).
  The referee has to pass a pre-registered self-test (size and power on synthetic
  data, 53/53) before it is frozen (`validation/.frozen`).
- **Trial ledger.** Every entry point appends to `research/experiments.jsonl`. DSR uses
  the true trial count, discards included, against a 250-trial budget.
- **Pre-registration (`v2/specs/`).** Each experiment's construction, pass rule and
  kill criteria are frozen before any real data is scored. A spec is never edited,
  only superseded by a new versioned file.
- **Lockbox holdout.** The 2022-01-01 to 2026-06-30 holdout (~17% of the sample) was
  encrypted with Fernet when the panel was cut; the plaintext never touched disk.
  The key file is the only copy of the key and lives outside the repo, so development
  code *cannot* see holdout data, rather than merely being told not to. `final_eval.py`
  is the only reader: it needs the key at run time, refuses to run twice (result-bundle
  marker plus an audit-log RUN line), refuses unless the referee is frozen and the
  ledger non-empty, and logs every attempt. I sealed it once and it opens once. The
  encrypted files are not in this repo; the tests run on synthetic lockboxes.
- **Decisions log (`v2/research/decisions.md`).** Every choice that could move a
  result is logged with its reason when it is made (D1–D40), including the ones that
  made results worse.

**Key design choices.**
- *ETF panel, not single stocks:* no survivorship-free point-in-time membership was
  available for stocks. The residual ETF closure bias is stated, not hidden.
- *Honest breadth:* measured on pre-holdout data, the panel has ~10–20 effective bets,
  not 50–100, so I set expectations at net Sharpe 0.3–0.8 and treated > 1.2 as a leak
  audit trigger and > 1.5 as a presumed bug.
- *ML must earn its place:* the baseline is an equal-weight z-score composite (M0).
  XGBoost and PPO are admitted only if they beat it on CPCV by a pre-registered margin.
- *Dropped before testing:* short-term reversal and lead-lag, which the literature
  contradicts at index level after costs.

**Results (train/validation only; the holdout has not been opened).**

| Experiment | Result |
|---|---|
| EXP-001 Tier-1 signal IC | S1 momentum and S2 time-series trend graduate (mean IC 0.038/0.031, Newey-West t 3.92/3.16). S3 low-beta fails in the wrong direction (t = −3.06); S4 seasonality is null (t = −0.22). |
| EXP-002 M0 combiner (S1+S2) | Net Sharpe 0.214 at 5 bps/side, 0.135 at 10 bps; max drawdown −38.6%; CPCV median 0.211 (5–95%: −0.47 to 0.76); DSR 0.85; time-shift canary fails. **Fails the gates** (target 0.5, MaxDD ≤ 20%). |
| EXP-003 static vs timing split | S1 timing passes marginally (t = 2.37); S2 timing misses (t = 1.75). Most of the edge is a static tilt, not timing. |
| EXP-004 Tier-2 carry | Graduates (mean IC 0.100, t = 5.75), but a *constant* per-name ordering reproduces 98% of its IC. It is a static risky-over-safe tilt, the ordering the 2022+ holdout is known to have inverted. |

The honest reading: S1, S2 and carry largely load on one static risk-premium axis
(S1/S2 correlation 0.796, effective breadth ≈ 1.11 per D25). The combined book does
not reach the target. A few things did work as designed: a pre-audit rank check caught a
units bug in the carry construction before review, the time-shift canary caught smuggled beta in M0, and a data
source (FRED's ICE BofA OAS series, which only has ~3 years of history) was found to be
unusable *before* any trial was spent on it.

Three things about the numbers:
- EXP-002 has only 2 stored trials, so PBO could not be computed (it needs ≥ 10).
- The M0 number is after dropping a no-trade band that caused cap violations. That
  made Sharpe *worse* (0.2228 → 0.2139). I logged it anyway (D26).
- The universe is 70 names, not the 69 my design doc first stated. The frozen rule
  gives 70, and the 69 was an arithmetic slip (D16).

## Charter rules referenced in the code

Comments and specs cite section numbers from my v2 research charter:
§2 success contract (the gates above) · §3.1 no strategy performance computed on the
holdout · §3.3b clean-checkout reproducibility · §3.3d synthetic null/known-edge
calibration and canaries · §3.3f Sharpe > 1.5 presumed bug · §3.3h/§3.3i lockbox and
one-shot final eval · §3.4 nothing runs uncounted · §3.7 alternatives logged with
reasons · §5 phase plan · §8 don't shave the ruler (no loosening the referee to pass).

## Layout

```
v1/                 directional meta-labeling system (archived)
  src/, config/     pipeline, gym, PBO gate
  docs/             LaTeX write-up of the architecture and its failures
v2/                 cross-sectional rebuild
  validation/       frozen referee
  src/              signals, decomposition, M0 combiner, panel builder (+ v1 code reused)
  specs/            pre-registered experiment specs
  research/         design, decisions log, evidence briefs, runners + results
  data/panel/       SHA-256 manifest of the frozen train/val panel (prices not redistributed)
  tests/            fast, data-integrity and referee-calibration suites
```

The research ran on a frozen panel of daily adjusted closes, volumes and an eligibility
mask for 70 ETFs, downloaded from Yahoo Finance. I don't redistribute the vendor data, so
only `v2/data/panel/MANIFEST.json` is committed: it freezes the universe, the split and the
SHA-256 of every panel file. `src/panel_factory.py` rebuilds the panel (move the committed
manifest aside first; the builder refuses to overwrite one). A re-download is never
bit-identical, so a rebuilt panel will not match the committed hashes exactly, and the
committed `results.json` files remain the record of what the frozen panel produced. The
panel-integrity tests skip when the panel is absent.

## Running it

```bash
git clone https://github.com/Aymo-WH/trading-bot.git
cd trading-bot/v2
pip install -r requirements.lock.txt
python -m pytest tests/fast tests/data -q     # unit + panel-integrity tests, seconds
python -m pytest tests/referee -q             # referee calibration, slow
python research/exp001_signal_ic/run_exp001.py  # re-run an experiment (needs the rebuilt panel)
```

EXP-004 needs a `FRED_API_KEY` environment variable. `v1/` has its own steps in
[v1/README.md](v1/README.md). `v2/research/phase4_screens/gordian_colab_screen.ipynb`
is a scratch notebook for exploratory screens on the frozen panel. It logs nothing.

## License

MIT. See [LICENSE](LICENSE).
