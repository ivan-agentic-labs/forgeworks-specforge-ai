from specforge_ai.infrastructure.store import Store


def operation(operation_id, requirement_id=None, case_ids=None):
    value = {"operationId": operation_id}
    if requirement_id is not None:
        value["x-requirement-id"] = requirement_id
    if case_ids is not None:
        value["x-acceptance-case-ids"] = case_ids
    return value


def test_traceability_reports_linkage_numerators_denominators_and_ratios():
    requirements = [{"id": "req-1"}, {"id": "req-2"}]
    cases = [("case-1", "req-1"), ("case-2", "req-2")]
    spec = {
        "paths": {
            "/one": {"get": operation("getOne", "req-1", ["case-1"])},
            "/two": {"post": operation("createTwo", "req-2", ["case-2"])},
        }
    }

    report = Store._trace_report(requirements, spec, cases, [])

    assert report["status"] == "VERIFIED"
    assert report["operation_coverage"] == {"linked": 2, "total": 2, "ratio": 1.0}
    assert report["requirement_coverage"] == {"linked": 2, "total": 2, "ratio": 1.0}


def test_traceability_reports_partial_links_without_marking_them_verified():
    requirements = [{"id": "req-1"}, {"id": "req-2"}]
    cases = [("case-1", "req-1"), ("case-2", "req-2")]
    spec = {
        "paths": {
            "/one": {"get": operation("getOne", "req-1", ["case-1"])},
            "/two": {"post": operation("createTwo", case_ids=["case-2"])},
        }
    }

    report = Store._trace_report(requirements, spec, cases, [])

    assert report["status"] == "INCOMPLETE"
    assert report["operation_coverage"] == {"linked": 1, "total": 2, "ratio": 0.5}
    assert report["requirement_coverage"] == {"linked": 1, "total": 2, "ratio": 0.5}
    assert report["unlinked_operation_ids"] == ["createTwo"]


def test_zero_denominators_report_zero_coverage_and_fail_closed():
    report = Store._trace_report([], {"paths": {}}, [], [])

    assert report["status"] == "INCOMPLETE"
    assert report["operation_coverage"] == {"linked": 0, "total": 0, "ratio": 0.0}
    assert report["requirement_coverage"] == {"linked": 0, "total": 0, "ratio": 0.0}
