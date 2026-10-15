"""Non-scalar generated LLM fields must produce validation errors, not 500s."""
import pytest

from specforge_ai.domain.openapi_semantics import validate_generated_openapi


@pytest.mark.parametrize("version", [None, True, 123, [], {}, ["3.1.0"], {"value": "3.1.0"}])
def test_bad_generated_version_is_bounded_validation_failure(version):
    report = validate_generated_openapi(
        {"openapi": version, "info": {"title": "API", "version": "1"},
         "paths": {"/ping": {"get": {
             "operationId": "ping", "responses": {"200": {"description": "OK"}},
             "x-requirement-id": "r1", "x-acceptance-case-ids": ["a1"],
         }}}},
        ["r1"], ["a1"],
    )
    assert report["valid"] is False
    assert "openapi must be a supported 3.1 version" in report["errors"]


def test_valid_scalar_version_retains_existing_contract():
    report = validate_generated_openapi(
        {"openapi": "3.1.0", "info": {"title": "API", "version": "1"},
         "paths": {"/ping": {"get": {
             "operationId": "ping", "responses": {"200": {"description": "OK"}},
             "x-requirement-id": "r1", "x-acceptance-case-ids": ["a1"],
         }}}},
        ["r1"], ["a1"],
    )
    assert report["valid"] is True, report["errors"]
