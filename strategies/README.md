# NY 30M ORB Variations — QuantForge

## Timezone contract

The XAUUSD 5M CSV is interpreted as **UTC+3**.

All session logic is performed after conversion to:

    America/New_York

The ORB is always:

    09:30 <= NY time < 10:00

That means six 5-minute bars.

Do NOT hard-code 16:30 or 17:30 into strategy logic. New York DST changes
the equivalent UTC+3 source time automatically.

## Variants

| File | Hypothesis |
|---|---|
| 17_ny_orb_breakout.py | Pure first close outside ORB |
| 18_ny_orb_retest.py | Breakout + immediate retest + continuation |
| 19_ny_orb_retest_rejection.py | Retest must reject ORB boundary |
| 20_ny_orb_quality.py | Confirmation requires strong body + strong CLV |
| 21_ny_orb_clv.py | Confirmation CLV filter only |
| 22_ny_orb_atr_range.py | ORB range must be reasonable vs ATR |
| 23_ny_orb_atr_regime.py | Pre-breakout ATR must be above its historical median |

## Signal timing

The strategy emits a signal at the close of the qualifying 5M candle.

The existing QuantForge engine then executes at the next 5M bar open.

## Important limitation

These scripts are compatible with the current `generate_signals(df)` contract.
They do NOT implement per-trade stop-loss, take-profit, or 2%/2.5%/3% risk sizing.

Those belong in the separate price-action trade-plan/execution layer.

## Research order

1. 17 pure breakout
2. 18 breakout + retest
3. 19 retest + rejection
4. 20 quality
5. 21 CLV independently
6. 22 ORB/ATR
7. 23 ATR regime

Do not optimize all parameters simultaneously. Measure each incremental filter
against the same baseline, then validate out-of-sample.

## Conservative data assumption

If a future stop/target engine is added using 5M OHLC only and both SL and TP
are touched inside one bar, resolve the ambiguity conservatively as SL-first
until 1M data is used to determine intrabar ordering.
