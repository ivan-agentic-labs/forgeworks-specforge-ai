from uuid import uuid4
import pytest
from specforge_ai.domain.explicit_endpoints import EndpointDeclarationError, explicit_paths
from specforge_ai.domain.openapi_semantics import validate_generated_openapi


def generate(lines):
    requirements = [{"id": str(uuid4()), "statement": line} for line in lines]
    cases = [(str(uuid4()), requirement["id"]) for requirement in requirements]
    return explicit_paths(requirements, cases), requirements, cases


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"])
def test_explicit_operation_preserves_source(method):
    paths, reqs, cases = generate([method + ' /users/{user_id} -> 200 | Retrieve the declared resource'])
    op = paths['/users/{user_id}'][method.lower()]
    assert op['parameters'][0] == {'name':'user_id','in':'path','required':True,'schema':{},'description':'Schema intentionally unspecified; stakeholder review is required.'}
    assert list(op['responses']) == ['200']
    assert op['x-requirement-id'] == reqs[0]['id']
    assert op['x-acceptance-case-ids'] == [cases[0][0]]
    spec = {'openapi':'3.1.0','info':{'title':'synthetic','version':'1'},'paths':paths}
    assert validate_generated_openapi(spec, [r['id'] for r in reqs], [c[0] for c in cases])['valid']


@pytest.mark.parametrize("line", ['Retrieve users', 'get /users -> 200 | retrieve', 'GET /users?secret=x -> 200 | retrieve', 'GET https://test.invalid -> 200 | retrieve', 'GET /../users -> 200 | retrieve', 'GET /users -> 999 | retrieve', 'GET /users -> 200 | ', 'GET /users/{bad-name} -> 200 | retrieve', 'GET /users -> 200 | bad\x00description'])
def test_ambiguous_or_invalid_declaration_is_rejected(line):
    with pytest.raises(EndpointDeclarationError): generate([line])


def test_duplicate_operation_is_not_overwritten():
    with pytest.raises(EndpointDeclarationError, match='EXPLICIT_ENDPOINT_DUPLICATE'):
        generate(['GET /users -> 200 | one', 'GET /users -> 201 | two'])


def test_template_aliases_are_rejected():
    with pytest.raises(EndpointDeclarationError, match='EXPLICIT_ENDPOINT_TEMPLATE_COLLISION'):
        generate(['GET /users/{id} -> 200 | one', 'POST /users/{name} -> 201 | two'])


def test_methods_can_share_exact_path():
    paths, _, _ = generate(['GET /users -> 200 | list', 'POST /users -> 201 | create'])
    assert set(paths['/users']) == {'get', 'post'}


def test_root_path_is_supported():
    assert '/' in generate(['GET / -> 200 | readiness'])[0]


def test_missing_or_extra_acceptance_case_does_not_silently_truncate_output():
    _, requirements, cases = generate([
        "GET /one -> 200 | First endpoint",
        "GET /two -> 200 | Second endpoint",
    ])
    for changed in (cases[:-1], cases + [(str(uuid4()), str(uuid4()))]):
        with pytest.raises(EndpointDeclarationError, match="EXPLICIT_ENDPOINT_CASE_ALIGNMENT_INVALID"):
            explicit_paths(requirements, changed)


def test_out_of_order_case_bindings_cannot_mislabel_operations():
    _, requirements, cases = generate([
        "GET /one -> 200 | First endpoint",
        "GET /two -> 200 | Second endpoint",
    ])
    with pytest.raises(EndpointDeclarationError, match="EXPLICIT_ENDPOINT_CASE_ALIGNMENT_INVALID"):
        explicit_paths(requirements, list(reversed(cases)))


def test_duplicate_case_ids_cannot_appear_in_generated_traceability():
    _, requirements, cases = generate([
        "GET /one -> 200 | First endpoint",
        "GET /two -> 200 | Second endpoint",
    ])
    duplicate = [(cases[0][0], cases[0][1]), (cases[0][0], cases[1][1])]
    with pytest.raises(EndpointDeclarationError, match="EXPLICIT_ENDPOINT_CASE_DUPLICATE"):
        explicit_paths(requirements, duplicate)


@pytest.mark.parametrize("hidden", [
    "\u200b", "\u200d", "\u202e", "\u2066", "\u2028", "\u2029", "\ufeff", "\u0085",
])
def test_generated_requirement_summary_rejects_invisible_unicode_spoofing(hidden):
    with pytest.raises(EndpointDeclarationError, match="EXPLICIT_ENDPOINT_DESCRIPTION_INVALID"):
        generate(["GET /audit -> 200 | Reviewed" + hidden + "status"])


def test_visible_non_ascii_human_summary_is_preserved():
    paths, _, _ = generate(["GET /audit -> 200 | Résumé de l'audit"])
    assert paths["/audit"]["get"]["summary"] == "Résumé de l'audit"

def test_repeated_path_parameter_cannot_be_silently_deduplicated():
    with pytest.raises(EndpointDeclarationError, match="EXPLICIT_ENDPOINT_PATH_PARAMETER_REPEATED"):
        generate(["GET /customers/{id}/orders/{id} -> 200 | Conflicting path parameter identity"])


def test_distinct_path_parameters_preserve_complete_bindings():
    paths, _, _ = generate(["GET /customers/{customer_id}/orders/{order_id} -> 200 | View order"])
    params = paths["/customers/{customer_id}/orders/{order_id}"]["get"]["parameters"]
    assert [parameter["name"] for parameter in params] == ["customer_id", "order_id"]

def test_duplicate_requirement_ids_never_generate_duplicate_operation_ids():
    _, requirements, cases = generate([
        "GET /customers -> 200 | List customers",
        "POST /orders -> 201 | Create order",
    ])
    duplicated = [{**requirements[0]}, {**requirements[1], "id": requirements[0]["id"]}]
    aligned = [(cases[0][0], duplicated[0]["id"]), (cases[1][0], duplicated[1]["id"])]
    with pytest.raises(EndpointDeclarationError, match="EXPLICIT_ENDPOINT_REQUIREMENT_DUPLICATE"):
        explicit_paths(duplicated, aligned)

def test_distinct_source_ids_cannot_collapse_to_same_openapi_operation_id():
    requirements = [
        {"id": "ab-c", "statement": "GET /customer -> 200 | Find customer"},
        {"id": "abc", "statement": "POST /orders -> 201 | Add order"},
    ]
    cases = [("acceptance-a", "ab-c"), ("acceptance-b", "abc")]
    with pytest.raises(EndpointDeclarationError, match="EXPLICIT_ENDPOINT_OPERATION_ID_COLLISION"):
        explicit_paths(requirements, cases)
