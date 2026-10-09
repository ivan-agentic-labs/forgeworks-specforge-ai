# SpecForge review console

This directory contains a provider-free static review UI served by the API at `/`. It calls the explicit `/v1` endpoints for requirements, ambiguities, stakeholder decisions, deterministic revision generation, traceability, and approval.

The API base URL can be entered in the connection panel, supplied as `?api_base=https://api.example.invalid`, or set before the script loads with `window.SPECFORGE_API_BASE`. The entered value is stored in browser local storage only. If the UI is hosted on a different origin, configure the API's allowed CORS origin in the deployment layer.

The console visibly blocks generation while HIGH or CRITICAL ambiguities are open and renders typed `OPEN_AMBIGUITY`, `STALE_VERSION`, and `DIGEST_MISMATCH` problem responses. It does not call an AI provider or upload/download artifact bytes; artifact quarantine remains API-enforced and fail-closed.
