# 2026-10-11 staged HTTP request budget

## Exact code and acceptance boundary
- Release source SHA: `7054dc93bedd591a91214325ba0ec6ce710fa276`.
- Railway staging deployment: `e0453a39-783a-4886-a0ef-11d1f91dc1c4`, observed `SUCCESS` with one running, zero crashed replica at checkpoint.
- Request budget: 8 MiB actual/declared body; maximum 16,384 chunks; malformed/oversized Content-Length bounded; invalid requests return 400/413.
- Tests are synthetic TestClient/pure-ASGI, not measured external attack traffic or rate-limiting proof.
- Railway source is explicitly pinned to this SHA; documentation-only commits after it need not be deployed.

## Exact CI receipts
- G1 Contract Verification: **success**, https://github.com/ivan-agentic-labs/forgeworks-specforge-ai/actions/runs/38087967190
- SpecForge MVP Application CI: **success**, https://github.com/ivan-agentic-labs/forgeworks-specforge-ai/actions/runs/38087967243
- SpecForge PostgreSQL Runtime Proof: **success**, https://github.com/ivan-agentic-labs/forgeworks-specforge-ai/actions/runs/38087967236

## Scope and remaining evidence
All listed CI checks were `success` for the pinned source. Staging deployment `SUCCESS` confirms startup/health gates according to Railway, not full product functionality. External `/readyz` and authenticated business workflow tests could not be independently completed from this execution environment; owner/tenant membership provisioning and all G3-G6 acceptance remain OPEN.
