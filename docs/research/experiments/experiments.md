# QuantForge Research Experiment Log

This document tracks experimental changes to the QuantForge
backtesting engine.

The files in `engine/` represent the baseline implementation.

Experimental implementations must not overwrite the baseline
until they have been tested and validated.

---

## Experiment Status

| ID | Experiment | Component | Dataset | Result | Decision |
|---|---|---|---|---|---|
| E001 | OHLC without volume | Data Pipeline | NIFTY 5M | ✅ Successful | Adopted experimentally |
| E002 | Target-weight accounting | Core Engine | NIFTY 5M | ⏳ Pending | Pending |
| E003 | Long → Short execution | Core Engine | NIFTY 5M | ⏳ Pending | Pending |
| E004 | 5M session validation | Data Pipeline | NIFTY 5M | ⏳ Pending | Pending |
| E005 | ORB 30-minute opening range | Strategy | NIFTY 5M | ⏳ Pending | Pending |

---

# E001 — OHLC Dataset Without Volume

**Component:** Data Pipeline

**Dataset:** `master_5min.csv`

### Question

Can QuantForge process OHLC data without requiring a volume column?

### Original behavior

The original data pipeline required:

```text
open
high
low
close
volume