"""Independent semantic checks for generated OpenAPI documents.

The validator deliberately does not call a provider or a network service.  It is
small enough to run in the API process and its report is canonical JSON whose
SHA-256 can be recorded alongside the revision.
"""
from __future__ import annotations

import json
import hashlib
import re
from collections import Counter
from typing import Any, Iterable


_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
_TEMPLATE = re.compile(r"\{([^{}\/]+)\}")


def _report(errors: Iterable[str], warnings: Iterable[str] = ()) -> dict[str, Any]:
    errors = sorted(set(errors))
    warnings = sorted(set(warnings))
    return {
        "validator": "specforge.openapi.semantic.v1",
        "deterministic": True,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def _declared_path_parameters(raw: Any, location: str, errors: list[str]) -> set[str]:
    """Validate effective OpenAPI path bindings, rejecting ambiguous duplicates."""
    if not isinstance(raw, list):
        errors.append(f"{location}: parameters must be an array")
        return set()
    names: set[str] = set()
    seen: set[tuple[str, str]] = set()
    for index, param in enumerate(raw):
        prefix = f"{location}: parameter {index}"
        if not isinstance(param, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name, scope = param.get("name"), param.get("in")
        if not isinstance(name, str) or not name or not isinstance(scope, str):
            errors.append(f"{prefix} requires a name and location")
            continue
        identity = (scope, name)
        if identity in seen:
            errors.append(f"{location}: duplicate parameter {scope}:{name}")
        seen.add(identity)
        if scope == "path":
            names.add(name)
            if param.get("required") is not True:
                errors.append(f"{prefix}: path parameter must be required")
            if not isinstance(param.get("schema"), dict):
                errors.append(f"{prefix}: path parameter schema must be an object")
    return names


def validate_generated_openapi(spec: dict[str, Any], requirement_ids: Iterable[str], acceptance_ids: Iterable[str]) -> dict[str, Any]:
    """Return a stable report for structural and requirement trace semantics."""
    requirement_ids = set(requirement_ids)
    acceptance_ids = set(acceptance_ids)
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(spec, dict):
        return _report(["document must be an object"])
    if spec.get("openapi") not in {"3.1.0", "3.1.1", "3.1.2"}:
        errors.append("openapi must be a supported 3.1 version")
    if not isinstance(spec.get("info"), dict) or not spec["info"].get("title") or not spec["info"].get("version"):
        errors.append("info.title and info.version are required")
    paths = spec.get("paths")
    if not isinstance(paths, dict) or not paths:
        errors.append("paths must contain at least one path")
        paths = {}

    # Distinct template variable names do not make two otherwise identical
    # OpenAPI paths distinguishable. Track normalized route signatures.
    route_signatures: dict[str, str] = {}
    operation_ids: list[str] = []
    linked_requirements: list[str] = []
    linked_acceptance: list[str] = []
    for path, item in sorted(paths.items()):
        if not isinstance(path, str) or not path.startswith("/"):
            errors.append(f"invalid path: {path!r}")
            continue
        if not isinstance(item, dict):
            errors.append(f"{path}: path item must be an object")
            continue
        matches = list(_TEMPLATE.finditer(path))
        # Reject malformed/unbalanced braces rather than silently treating
        # them as literal path segments.
        remainder = _TEMPLATE.sub("", path)
        if "{" in remainder or "}" in remainder:
            errors.append(f"{path}: invalid path template syntax")
        signature = _TEMPLATE.sub("{}", path)
        if matches and signature in route_signatures:
            errors.append(f"{path}: indistinguishable templated paths: {route_signatures[signature]}")
        else:
            route_signatures[signature] = path
        placeholders = {match.group(1) for match in matches}
        if len(placeholders) != len(matches):
            errors.append(f"{path}: duplicate path template variable")
        path_params = _declared_path_parameters(item.get("parameters", []), path, errors)
        for method, operation in sorted(item.items()):
            if method.startswith("x-") or method in {"summary", "description", "parameters", "servers"}:
                continue
            if method not in _METHODS:
                errors.append(f"{path}: unsupported path item {method}")
                continue
            if not isinstance(operation, dict):
                errors.append(f"{path} {method}: operation must be an object")
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                errors.append(f"{path} {method}: operationId is required")
            else:
                operation_ids.append(operation_id)
            responses = operation.get("responses")
            if not isinstance(responses, dict) or not responses:
                errors.append(f"{path} {method}: responses are required")
            req_id = operation.get("x-requirement-id")
            if req_id is not None:
                if not isinstance(req_id, str) or req_id not in requirement_ids:
                    errors.append(f"{path} {method}: unknown x-requirement-id")
                else:
                    linked_requirements.append(req_id)
            case_ids = operation.get("x-acceptance-case-ids", [])
            if not isinstance(case_ids, list) or any(not isinstance(case_id, str) or case_id not in acceptance_ids for case_id in case_ids):
                errors.append(f"{path} {method}: x-acceptance-case-ids contains an unknown case")
            elif len(set(case_ids)) != len(case_ids):
                errors.append(f"{path} {method}: duplicate acceptance case reference")
            else:
                linked_acceptance.extend(case_ids)
            operation_params = _declared_path_parameters(operation.get("parameters", []), f"{path} {method}", errors)
            declared = path_params | operation_params
            if placeholders != declared:
                errors.append(f"{path} {method}: path parameter mismatch")

    duplicates = [name for name, count in Counter(operation_ids).items() if count > 1]
    if duplicates:
        errors.append("duplicate operationId: " + ",".join(sorted(duplicates)))
    missing = sorted(requirement_ids - set(linked_requirements))
    duplicate_requirements = sorted(name for name, count in Counter(linked_requirements).items() if count > 1)
    if missing:
        errors.append("unlinked requirements: " + ",".join(missing))
    if duplicate_requirements:
        errors.append("requirements linked more than once: " + ",".join(duplicate_requirements))
    missing_cases = sorted(acceptance_ids - set(linked_acceptance))
    if missing_cases:
        errors.append("unlinked acceptance cases: " + ",".join(missing_cases))
    # A case must bind to one operation exactly. Reusing the same case on
    # distinct operations yields an apparently complete but misleading audit.
    duplicate_cases = sorted(name for name, count in Counter(linked_acceptance).items() if count > 1)
    if duplicate_cases:
        errors.append("acceptance cases linked more than once: " + ",".join(duplicate_cases))
    if spec.get("x-deterministic-output") is not True:
        warnings.append("document does not explicitly label deterministic output")
    return _report(errors, warnings)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
