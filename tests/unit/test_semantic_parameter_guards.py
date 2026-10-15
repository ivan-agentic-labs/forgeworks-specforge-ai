"""Semantic validation must fail closed for ambiguous OpenAPI declarations."""
from copy import deepcopy

import pytest

from specforge_ai.domain.openapi_semantics import validate_generated_openapi


def valid_spec():
    return {
        "openapi": "3.1.0",
        "info": {"title": "Synthetic", "version": "1"},
        "x-deterministic-output": True,
        "paths": {
            "/records/{record_id}": {
                "get": {
                    "operationId": "getRecord",
                    "x-requirement-id": "req-1",
                    "x-acceptance-case-ids": ["case-1"],
                    "parameters": [{
                        "name": "record_id", "in": "path", "required": True,
                        "schema": {"type": "string"},
                    }],
                    "responses": {"200": {"description": "OK"}},
                },
            },
        },
    }


def report(spec):
    return validate_generated_openapi(spec, {"req-1"}, {"case-1"})


def test_valid_generated_path_parameter_profile_passes():
    assert report(valid_spec())["valid"] is True


@pytest.mark.parametrize("mutation,reason", [
    (lambda spec: spec["paths"]["/records/{record_id}"]["get"]["parameters"][0].update(required=False), "path parameter must be required"),
    (lambda spec: spec["paths"]["/records/{record_id}"]["get"]["parameters"][0].pop("schema"), "path parameter schema must be an object"),
    (lambda spec: spec["paths"]["/records/{record_id}"]["get"].update(parameters="record_id"), "parameters must be an array"),
    (lambda spec: spec["paths"]["/records/{record_id}"]["get"]["parameters"].append({"name": "record_id", "in": "path", "required": True, "schema": {}}), "duplicate parameter path:record_id"),
    (lambda spec: spec["paths"]["/records/{record_id}"].update(parameters={"name": "record_id"}), "parameters must be an array"),
    (lambda spec: spec["paths"]["/records/{record_id}"]["get"].update(**{"x-acceptance-case-ids": ["case-1", "case-1"]}), "duplicate acceptance case reference"),
    (lambda spec: spec["paths"]["/records/{record_id}"]["get"].update(**{"x-acceptance-case-ids": [{"case": "case-1"}]}), "contains an unknown case"),
    (lambda spec: spec["paths"]["/records/{record_id}"]["get"].update(**{"x-requirement-id": ["req-1"]}), "unknown x-requirement-id"),
])
def test_semantic_boundary_rejects_invalid_input_without_throwing(mutation, reason):
    spec = deepcopy(valid_spec())
    mutation(spec)
    result = report(spec)
    assert result["valid"] is False
    assert any(reason in error for error in result["errors"]), result


def test_inherited_path_parameter_satisfies_operation_placeholder():
    spec = valid_spec()
    declared = spec["paths"]["/records/{record_id}"]["get"].pop("parameters")
    spec["paths"]["/records/{record_id}"]["parameters"] = declared
    assert report(spec)["valid"] is True


def test_missing_path_binding_fails_even_when_operation_exists():
    spec = valid_spec()
    spec["paths"]["/records/{record_id}"]["get"]["parameters"] = []
    result = report(spec)
    assert result["valid"] is False
    assert any("path parameter mismatch" in error for error in result["errors"])


def test_composite_path_template_matches_two_bound_parameters():
    spec = valid_spec()
    operation = spec["paths"].pop("/records/{record_id}")["get"]
    operation["parameters"].append({
        "name": "format", "in": "path", "required": True,
        "schema": {"type": "string"},
    })
    spec["paths"]["/records/{record_id}.{format}"] = {"get": operation}
    assert report(spec)["valid"] is True


def test_indistinguishable_templated_paths_fail_closed():
    spec = valid_spec()
    additional = deepcopy(spec["paths"]["/records/{record_id}"]["get"])
    additional["operationId"] = "getAlternateRecord"
    additional["x-acceptance-case-ids"] = []
    additional["x-requirement-id"] = None
    additional["parameters"][0]["name"] = "name"
    spec["paths"]["/records/{name}"] = {"get": additional}
    result = report(spec)
    assert result["valid"] is False
    assert any("indistinguishable templated paths" in error for error in result["errors"])


@pytest.mark.parametrize("path", ["/records/{record_id", "/records/record_id}", "/records/{}", "/records/{record_id}/{record_id}"])
def test_malformed_or_repeated_path_template_is_rejected(path):
    spec = valid_spec()
    item = spec["paths"].pop("/records/{record_id}")
    spec["paths"][path] = item
    result = report(spec)
    assert result["valid"] is False
    assert any("path template" in error for error in result["errors"])


def test_uppercase_operation_method_is_not_silently_accepted():
    spec = valid_spec()
    operation = spec["paths"]["/records/{record_id}"].pop("get")
    spec["paths"]["/records/{record_id}"]["GET"] = operation
    result = report(spec)
    assert result["valid"] is False
    assert any("unsupported path item GET" in error for error in result["errors"])


def test_case_referenced_by_distinct_operations_is_not_valid_traceability():
    spec = valid_spec()
    second = deepcopy(spec["paths"]["/records/{record_id}"]["get"])
    second["operationId"] = "updateRecord"
    second["x-requirement-id"] = "req-2"
    second["x-acceptance-case-ids"] = ["case-1", "case-2"]
    spec["paths"]["/records/{record_id}"]["post"] = second
    result = validate_generated_openapi(spec, {"req-1", "req-2"}, {"case-1", "case-2"})
    assert result["valid"] is False
    assert any("acceptance cases linked more than once: case-1" in error for error in result["errors"])


def test_unique_case_to_operation_traceability_remains_accepted():
    spec = valid_spec()
    second = deepcopy(spec["paths"]["/records/{record_id}"]["get"])
    second["operationId"] = "updateRecord"
    second["x-requirement-id"] = "req-2"
    second["x-acceptance-case-ids"] = ["case-2"]
    spec["paths"]["/records/{record_id}"]["post"] = second
    result = validate_generated_openapi(spec, {"req-1", "req-2"}, {"case-1", "case-2"})
    assert result["valid"] is True, result["errors"]


@pytest.mark.parametrize("omit", ["x-requirement-id", "x-acceptance-case-ids", "empty-cases"])
def test_generated_operation_cannot_escape_requirement_and_case_traceability(omit):
    spec = valid_spec()
    # An additional generated endpoint must not escape provenance checks merely
    # because all required IDs are already linked by another operation.
    operation = {
        "operationId": "untrackedOperation",
        "responses": {"204": {"description": "No content"}},
        "x-requirement-id": "req-2",
        "x-acceptance-case-ids": ["case-2"],
    }
    if omit == "empty-cases":
        operation["x-acceptance-case-ids"] = []
    else:
        operation.pop(omit)
    spec["paths"]["/shadow"] = {"post": operation}
    result = validate_generated_openapi(spec, {"req-1", "req-2"}, {"case-1", "case-2"})
    assert result["valid"] is False, result
    expected = ("x-requirement-id is required" if omit == "x-requirement-id"
                else "at least one linked acceptance case is required")
    assert any(expected in error for error in result["errors"]), result


def test_all_generated_operations_with_unique_requirement_and_case_links_pass():
    spec = valid_spec()
    spec["paths"]["/shadow"] = {"post": {
        "operationId": "trackedOperation",
        "responses": {"201": {"description": "Created"}},
        "x-requirement-id": "req-2",
        "x-acceptance-case-ids": ["case-2"],
    }}
    result = validate_generated_openapi(spec, {"req-1", "req-2"}, {"case-1", "case-2"})
    assert result["valid"] is True, result

@pytest.mark.parametrize("omitted", ["x-requirement-id", "x-acceptance-case-ids", "empty"])
def test_every_generated_operation_requires_trace_links(omitted):
    spec = valid_spec()
    extra = {
        "operationId": "secondOperation",
        "responses": {"204": {"description": "OK"}},
        "x-requirement-id": "req-2",
        "x-acceptance-case-ids": ["case-2"],
    }
    if omitted == "empty":
        extra["x-acceptance-case-ids"] = []
    else:
        extra.pop(omitted)
    spec["paths"]["/second"] = {"post": extra}
    report = validate_generated_openapi(spec, {"req-1", "req-2"}, {"case-1", "case-2"})
    assert report["valid"] is False
    reason = "x-requirement-id is required" if omitted == "x-requirement-id" else "at least one linked acceptance case is required"
    assert any(reason in error for error in report["errors"])


def test_two_operations_with_distinct_trace_links_are_valid():
    spec = valid_spec()
    spec["paths"]["/second"] = {"post": {
        "operationId": "secondOperation",
        "responses": {"201": {"description": "Created"}},
        "x-requirement-id": "req-2",
        "x-acceptance-case-ids": ["case-2"],
    }}
    report = validate_generated_openapi(spec, {"req-1", "req-2"}, {"case-1", "case-2"})
    assert report["valid"] is True, report


@pytest.mark.parametrize("status,response,reason", [
    ("999", {"description": "impossible"}, "invalid response status"),
    ("20", {"description": "short code"}, "invalid response status"),
    ("200OK", {"description": "nonstandard"}, "invalid response status"),
    ("6XX", {"description": "outside HTTP range"}, "invalid response status"),
    ("200", {}, "requires a description"),
    ("200", {"description": 42}, "requires a description"),
    ("200", "malformed response", "requires a description"),
    (200, {"description": "numeric key"}, "invalid response status"),
])
def test_invalid_response_declarations_are_reported_not_accepted(status,response,reason):
    spec = valid_spec()
    spec["paths"]["/records/{record_id}"]["get"]["responses"] = {status: response}
    report = validate_generated_openapi(spec, {"req-1"}, {"case-1"})
    assert report["valid"] is False, report
    assert any(reason in error for error in report["errors"])


@pytest.mark.parametrize("status", ["default", "200", "404", "2XX", "5XX"])
def test_supported_response_keys_with_explicit_descriptions_are_valid(status):
    spec = valid_spec()
    spec["paths"]["/records/{record_id}"]["get"]["responses"] = {
        status: {"description": ""}
    }
    report = validate_generated_openapi(spec, {"req-1"}, {"case-1"})
    assert report["valid"] is True, report


@pytest.mark.parametrize("bad_key", [None, 200, False, ("dynamic",)])
def test_nonstring_generated_path_keys_report_invalid_path_without_crashing(bad_key):
    spec = valid_spec()
    spec["paths"][bad_key] = {"get": {"operationId": "synthetic"}}
    first = report(spec)
    second = report(spec)
    assert first == second
    assert first["valid"] is False
    assert any("invalid path:" in error for error in first["errors"])


@pytest.mark.parametrize("bad_key", [None, 200, False, ("dynamic",)])
def test_nonstring_generated_method_keys_fail_closed_not_server_error(bad_key):
    spec = valid_spec()
    spec["paths"]["/records/{record_id}"][bad_key] = {"operationId": "shadow"}
    result = report(spec)
    assert result["valid"] is False
    assert any("path item key must be a string" in error for error in result["errors"])


@pytest.mark.parametrize("invalid_location", ["body", "formData", "matrix", ""])
def test_openapi_parameter_location_must_be_supported(invalid_location):
    spec = valid_spec()
    spec["paths"]["/records/{record_id}"]["get"]["parameters"][0]["in"] = invalid_location
    result = report(spec)
    assert result["valid"] is False
    assert any("unsupported parameter location" in error for error in result["errors"])


def test_supported_query_parameter_does_not_need_a_path_placeholder():
    spec = valid_spec()
    spec["paths"]["/records/{record_id}"]["get"]["parameters"].append({
        "name": "include", "in": "query", "schema": {"type": "string"},
    })
    result = report(spec)
    assert result["valid"] is True, result["errors"]
