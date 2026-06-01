# Changelog

## 0.1.0 - 2026-06-01

- Initial public release.
- Adds typed Pydantic v2 contracts for EDA-Mahn payloads.
- Adds outbound encoders for KEZI 01, 07, 08, 10, 20, 25, 29, and 30.
- Adds inbound parsers for KEZI 03, 05, 16, 18, 20, 22, and 90.
- Preserves the EDA CP-858 charset and fixed-width 128-byte record contract.
- Leaves transport, signing, beA, EGVP, billing, storage, and product workflow integration to host applications.
