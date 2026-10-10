# Explicit source endpoint profile

Use `output_profile: openapi31-explicit-v1` when every nonblank source line declares an HTTP operation:

```text
GET /users/{user_id} -> 200 | Retrieve user
POST /users -> 201 | Create user
HEAD /users -> 200 | Inspect users
```

Upload and commit the UTF-8 text through the existing artifact flow, create a requirement set from its SHA-256, resolve open high-impact ambiguities, then generate the revision. The generator preserves each declaration's method, path and status response and links its operation to the source requirement and pending acceptance case. Multiple methods can share an exact path. Duplicate operations and equivalent templates with different parameter names are rejected without persisting a partial revision/job.

Supported syntax is deliberately strict: uppercase HTTP method, ASCII absolute path with literal segments or `{parameter_name}`, one HTTP response status from 100–599, ` | ` separator and a nonempty description. Query strings, URLs, traversal segments and guessed natural-language operations are rejected. Placeholder names begin with a letter and contain letters, digits or underscores.

Request/response schemas, authentication, parameter serialization and implementation behavior are unspecified. Path parameters are declared with empty schemas and explicit review annotations; no type or security policy is invented. `x-schema-review-required` remains true until future schema support and stakeholder acceptance exist. Traceability VERIFIED means links are complete, not that the endpoint is implemented or the requirement is semantically satisfied. Acceptance cases remain PENDING.

The older `openapi31` profile remains a placeholder review skeleton. Unknown profiles now return a typed 422 rather than silently using that skeleton.

Download exact output bytes from `GET /v1/spec-revisions/{id}/openapi` using active membership and `spec:read`. The route checks the immutable revision SHA-256, returns `X-Spec-SHA256`/ETag and disables cache storage. Missing and cross-tenant revisions return 404; altered stored bytes return 409. Reading a historical revision is permitted, but neither a download nor a generated document grants approval.
