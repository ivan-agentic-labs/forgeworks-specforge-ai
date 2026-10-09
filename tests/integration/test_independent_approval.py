from concurrent.futures import ThreadPoolExecutor
from specforge_ai.infrastructure.store import Store, TENANT, USER


def test_independent_adapters_one_decision_and_one_approval(tmp_path):
    store = Store(str(tmp_path / "commands.db")); store.seed()
    requirement_set = store.create_set(TENANT, "Synthetic evidence", "a" * 64, USER, "TBD: Return a response?")
    ambiguity = store.amb(TENANT, requirement_set["id"])[0]
    peers = [Store(store.path), Store(store.path)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        decisions = list(pool.map(lambda index: peers[index].decide(TENANT, ambiguity["id"], USER, "Return JSON", "synthetic://owner/1", 1)[1], range(2)))
    assert sorted(decisions) == ["OK", "STALE"]
    revision, status = store.revision(TENANT, requirement_set["id"], 1, "openapi31")
    assert status == "OK"
    with ThreadPoolExecutor(max_workers=2) as pool:
        approvals = list(pool.map(lambda index: peers[index].approve(TENANT, revision["id"], revision["spec_sha"], 1, f"synthetic-reviewer-{index}"), range(2)))
    assert sorted(result[1] for result in approvals) == ["OK", "STALE"]
    approved = next(result[0] for result in approvals if result[1] == "OK")
    assert approved["status"] == "APPROVED" and approved["version"] == 2
    assert store.get_revision(TENANT, revision["id"])["approver_id"] == approved["approver_id"]
