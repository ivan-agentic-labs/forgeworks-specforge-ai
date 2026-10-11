import pytest
from concurrent.futures import ThreadPoolExecutor

from specforge_ai.infrastructure.store import Store, TENANT


def insert_job(store, state, attempts, due='2000-01-01T00:00:00Z'):
    with store.conn() as db:
        db.execute('INSERT INTO jobs(tenant_id,id,revision_id,state,created_at,state_version,attempt_count,max_attempts,next_attempt_at,last_error_code,last_error_message,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                   (TENANT, 'job', 'missing-revision', state, due, 7, attempts, 3, due, None, None, due))


@pytest.mark.parametrize('attempts', [1, 3])
def test_running_job_is_not_processed_without_acquiring_it(tmp_path, attempts):
    store = Store(str(tmp_path / 'jobs.db'))
    insert_job(store, 'RUNNING', attempts)
    before = dict(store.job(TENANT, 'job'))
    assert store.run_job(TENANT, 'job') == 'RUNNING'
    assert dict(store.job(TENANT, 'job')) == before


@pytest.mark.parametrize('state', ['PENDING', 'FAILED_RETRYABLE'])
def test_exhausted_job_never_starts_an_extra_attempt(tmp_path, state):
    store = Store(str(tmp_path / 'jobs.db'))
    insert_job(store, state, 3)
    assert store.run_job(TENANT, 'job') == 'FAILED_TERMINAL'
    job = store.job(TENANT, 'job')
    assert job['attempt_count'] == 3 and job['state_version'] == 8
    assert job['last_error_code'] == 'MAX_ATTEMPTS_EXCEEDED'
    assert job['next_attempt_at'] is None


@pytest.mark.parametrize('state', ['SUCCEEDED', 'FAILED_TERMINAL', 'CANCELLED'])
def test_terminal_job_is_unchanged(tmp_path, state):
    store = Store(str(tmp_path / 'jobs.db'))
    insert_job(store, state, 3)
    before = dict(store.job(TENANT, 'job'))
    assert store.run_job(TENANT, 'job') == state
    assert dict(store.job(TENANT, 'job')) == before


@pytest.mark.parametrize('state', ['PENDING', 'FAILED_RETRYABLE'])
def test_backoff_is_unchanged(tmp_path, state):
    store = Store(str(tmp_path / 'jobs.db'))
    insert_job(store, state, 1, '2999-01-01T00:00:00Z')
    before = dict(store.job(TENANT, 'job'))
    assert store.run_job(TENANT, 'job') == state
    assert dict(store.job(TENANT, 'job')) == before


def test_independent_adapters_consume_only_one_attempt(tmp_path):
    path = str(tmp_path / 'jobs.db')
    store = Store(path)
    insert_job(store, 'PENDING', 0)
    peers = [Store(path), Store(path)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda peer: peer.run_job(TENANT, 'job'), peers))
    assert results == ['FAILED_TERMINAL', 'FAILED_TERMINAL']
    final = store.job(TENANT, 'job')
    assert final['attempt_count'] == 1 and final['state_version'] == 9
    assert final['last_error_code'] == 'REVISION_NOT_FOUND'
