Milestone 1 — Data Pipeline ✅

Built and validated the core QuantForge OHLCV data layer for clean, reproducible market-data handling.

Implemented:

CSV loading and column normalization
Date parsing, indexing, sorting, and deduplication
OHLC/volume validation
NaN cleanup
Parquet caching
SHA-256 dataset fingerprinting

Test data: 100 business-day OHLCV bars from 2010-01-01, stored in data/raw/toy.csv.

Validation: Full pipeline successfully executed from CSV → validation → Parquet cache → reproducibility hash.

Dataset hash: 5f90961780fc

Key design decision: Invalid OHLC rows are currently dropped with warnings rather than terminating the run. This can later become a configurable data-quality policy.

Status: 🟢 Milestone 1 Complete