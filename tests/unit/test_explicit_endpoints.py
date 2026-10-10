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
