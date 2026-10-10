# ADR 0003 — Explicit source endpoint profile

Status: implemented engineering decision, 2026-10-11; external stakeholder/security acceptance remains open.

The existing deterministic profile emits requirement-ID placeholder endpoints. Add `openapi31-explicit-v1` for owner-authored HTTP declarations and reject unsupported syntax instead of guessing an API. Preserve source/provenance links, existing approval gates and pending acceptance states. Keep `openapi31` as the existing skeleton profile; reject unrecognized profiles with 422. The download route verifies exact stored bytes and tenant/scope visibility.

The additive endpoint/profile does not synthesize request/response schema or auth policy. Review annotations expose those remaining decisions. An unknown-profile request that previously received a skeleton now fails intentionally. No database migration is required. Rollback consists of reverting this commit and regenerating the SDK; immutable earlier output documents remain readable through the existing store.
