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
