"""Deterministic endpoint declarations; never infer schemas or stakeholder decisions."""
import re
import unicodedata

LINE = re.compile(r"(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE) (\S+) -> ([1-5][0-9]{2}) \| (\S.*)")
SEGMENT = r"(?:[A-Za-z0-9._~-]+|\{[A-Za-z][A-Za-z0-9_]*\})"
PATH = re.compile(r"/(?:" + SEGMENT + r"(?:/" + SEGMENT + r")*)?")


class EndpointDeclarationError(ValueError):
    pass


def explicit_paths(requirements, cases):
    # Never silently discard requirements via zip() or attach another
    # requirement's acceptance case to an emitted operation.
    if len(requirements) != len(cases):
        raise EndpointDeclarationError("EXPLICIT_ENDPOINT_CASE_ALIGNMENT_INVALID")
    if any(
        not isinstance(case, (tuple, list))
        or len(case) != 2
        or case[1] != requirement["id"]
        for requirement, case in zip(requirements, cases)
    ):
        raise EndpointDeclarationError("EXPLICIT_ENDPOINT_CASE_ALIGNMENT_INVALID")
    if len({case[0] for case in cases}) != len(cases):
        raise EndpointDeclarationError("EXPLICIT_ENDPOINT_CASE_DUPLICATE")
    # operationId and x-requirement-id are durable traceability bindings.
    # Reusing a requirement ID on two distinct routes can create duplicate
    # operationIds even when each path/method pair is individually valid.
    ids = [requirement["id"] for requirement in requirements]
    if len(set(ids)) != len(ids):
        raise EndpointDeclarationError("EXPLICIT_ENDPOINT_REQUIREMENT_DUPLICATE")
    paths, template_paths = {}, {}
    for requirement, (case_id, _) in zip(requirements, cases):
        statement = requirement["statement"]
        match = LINE.fullmatch(statement)
        if not match:
            raise EndpointDeclarationError("EXPLICIT_ENDPOINT_DECLARATION_REQUIRED")
        method, path, status, description = match.groups()
        if not PATH.fullmatch(path) or any(segment in {".", ".."} for segment in path.split("/")):
            raise EndpointDeclarationError("EXPLICIT_ENDPOINT_PATH_INVALID")
        # Keep source-to-OpenAPI reviewer labels visually auditable. Unicode
        # bidi overrides, zero-width controls and separators can falsify the
        # apparent endpoint semantics while preserving different raw bytes.
        if any(unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in description):
            raise EndpointDeclarationError("EXPLICIT_ENDPOINT_DESCRIPTION_INVALID")
        template = re.sub(r"\{[^{}]+\}", "{}", path)
        if template in template_paths and template_paths[template] != path:
            raise EndpointDeclarationError("EXPLICIT_ENDPOINT_TEMPLATE_COLLISION")
        template_paths[template] = path
        item = paths.setdefault(path, {})
        method = method.lower()
        if method in item:
            raise EndpointDeclarationError("EXPLICIT_ENDPOINT_DUPLICATE")
        operation = {"operationId": "requirement_" + requirement["id"].replace("-", ""), "summary": description,
                     "x-requirement-id": requirement["id"], "x-acceptance-case-ids": [case_id],
                     "x-source-declaration": statement, "x-schema-review-required": True,
                     "responses": {status: {"description": description}}}
        extracted_names = re.findall(r"\{([^{}]+)\}", path)
        names = list(dict.fromkeys(extracted_names))
        if len(names) != len(extracted_names):
            raise EndpointDeclarationError("EXPLICIT_ENDPOINT_PATH_PARAMETER_REPEATED")
        if names:
            operation["parameters"] = [{"name": name, "in": "path", "required": True, "schema": {}, "description": "Schema intentionally unspecified; stakeholder review is required."} for name in names]
        item[method] = operation
    if not paths:
        raise EndpointDeclarationError("SOURCE_HAS_NO_REQUIREMENTS")
    return paths
