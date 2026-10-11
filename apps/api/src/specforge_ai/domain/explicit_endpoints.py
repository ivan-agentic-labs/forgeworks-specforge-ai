"""Deterministic endpoint declarations; never infer schemas or stakeholder decisions."""
import re

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
    paths, template_paths = {}, {}
    for requirement, (case_id, _) in zip(requirements, cases):
        statement = requirement["statement"]
        match = LINE.fullmatch(statement)
        if not match:
            raise EndpointDeclarationError("EXPLICIT_ENDPOINT_DECLARATION_REQUIRED")
        method, path, status, description = match.groups()
        if not PATH.fullmatch(path) or any(segment in {".", ".."} for segment in path.split("/")):
            raise EndpointDeclarationError("EXPLICIT_ENDPOINT_PATH_INVALID")
        if any(ord(char) < 32 or ord(char) == 127 for char in description):
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
        names = list(dict.fromkeys(re.findall(r"\{([^{}]+)\}", path)))
        if names:
            operation["parameters"] = [{"name": name, "in": "path", "required": True, "schema": {}, "description": "Schema intentionally unspecified; stakeholder review is required."} for name in names]
        item[method] = operation
    if not paths:
        raise EndpointDeclarationError("SOURCE_HAS_NO_REQUIREMENTS")
    return paths
