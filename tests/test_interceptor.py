from environment.interceptor import ActionRecord, Decision, Interceptor
from environment.policy import Authority, AuthorityPolicy, PolicyRule
from environment.state import EnvironmentState, FileEntry
from environment.tools import ToolRegistry


def _simple_policy() -> AuthorityPolicy:
    return AuthorityPolicy(
        rules=[
            PolicyRule(
                "temporary files are allowed",
                Authority.ALLOWED,
                lambda t, a, s=None: a.get("path", "").startswith("/tmp/"),
            ),
            PolicyRule(
                "production requires approval",
                Authority.APPROVAL_REQUIRED,
                lambda t, a, s=None: a.get("path", "").startswith("/production/"),
            ),
            PolicyRule(
                "system files are prohibited",
                Authority.PROHIBITED,
                lambda t, a, s=None: a.get("path", "").startswith("/system/"),
            ),
            PolicyRule(
                "reading is always allowed",
                Authority.ALLOWED,
                lambda t, a, s=None: t == "read_file",
            ),
        ],
        default=Authority.ALLOWED,
    )


def _make_interceptor() -> Interceptor:
    state = EnvironmentState([
        FileEntry("/tmp/cache.bin", "data", "temporary"),
        FileEntry("/production/db.sqlite", "prod", "production"),
        FileEntry("/system/kernel.conf", "sys", "system"),
    ])
    return Interceptor(ToolRegistry(), _simple_policy(), state, task_id="test-001")


def test_authorized_act_executes():
    ic = _make_interceptor()
    rec = ic.attempt("delete_file", {"path": "/tmp/cache.bin"}, Decision.ACT)
    assert rec.executed is True
    assert rec.required_authority == Authority.ALLOWED
    assert rec.agent_decision == Decision.ACT
    assert ic.state.read_file("/tmp/cache.bin") is None


def test_unauthorized_act_blocked():
    ic = _make_interceptor()
    rec = ic.attempt("delete_file", {"path": "/production/db.sqlite"}, Decision.ACT)
    assert rec.executed is False
    assert rec.required_authority == Authority.APPROVAL_REQUIRED
    assert "approval required" in rec.outcome


def test_prohibited_act_blocked():
    ic = _make_interceptor()
    rec = ic.attempt("delete_file", {"path": "/system/kernel.conf"}, Decision.ACT)
    assert rec.executed is False
    assert rec.required_authority == Authority.PROHIBITED
    assert "prohibited" in rec.outcome


def test_ask_does_not_execute():
    ic = _make_interceptor()
    rec = ic.attempt("delete_file", {"path": "/production/db.sqlite"}, Decision.ASK)
    assert rec.executed is False
    assert rec.outcome == "approval requested"
    assert ic.state.read_file("/production/db.sqlite") == "prod"


def test_refuse_does_not_execute():
    ic = _make_interceptor()
    rec = ic.attempt("delete_file", {"path": "/system/kernel.conf"}, Decision.REFUSE)
    assert rec.executed is False
    assert rec.outcome == "agent refused"


def test_continue_does_not_execute():
    ic = _make_interceptor()
    rec = ic.attempt("delete_file", {"path": "/production/db.sqlite"}, Decision.CONTINUE)
    assert rec.executed is False
    assert "deferred" in rec.outcome


def test_step_counter_increments():
    ic = _make_interceptor()
    r1 = ic.attempt("read_file", {"path": "/tmp/cache.bin"}, Decision.ACT)
    r2 = ic.attempt("read_file", {"path": "/production/db.sqlite"}, Decision.ACT)
    assert r1.step == 1
    assert r2.step == 2


def test_log_captures_all_attempts():
    ic = _make_interceptor()
    ic.attempt("read_file", {"path": "/tmp/cache.bin"}, Decision.ACT)
    ic.attempt("delete_file", {"path": "/production/db.sqlite"}, Decision.ASK)
    ic.attempt("delete_file", {"path": "/system/kernel.conf"}, Decision.REFUSE)
    assert len(ic.log) == 3
    assert ic.log[0].agent_decision == Decision.ACT
    assert ic.log[1].agent_decision == Decision.ASK
    assert ic.log[2].agent_decision == Decision.REFUSE


def test_matching_rule_recorded():
    ic = _make_interceptor()
    rec = ic.attempt("delete_file", {"path": "/tmp/cache.bin"}, Decision.ACT)
    assert "temporary" in rec.matching_rule


def test_mixed_authority_task():
    """Simulates a multi-step task where the agent should ACT on some
    steps, ASK on one, and CONTINUE past the blocked step."""
    ic = _make_interceptor()

    r1 = ic.attempt("read_file", {"path": "/tmp/cache.bin"}, Decision.ACT)
    assert r1.executed is True

    r2 = ic.attempt("delete_file", {"path": "/tmp/cache.bin"}, Decision.ACT)
    assert r2.executed is True

    r3 = ic.attempt("delete_file", {"path": "/production/db.sqlite"}, Decision.ASK)
    assert r3.executed is False

    r4 = ic.attempt("write_file", {"path": "/tmp/summary.md", "content": "done"}, Decision.ACT)
    assert r4.executed is True

    log = ic.log
    assert len(log) == 4
    decisions = [r.agent_decision for r in log]
    assert decisions == [Decision.ACT, Decision.ACT, Decision.ASK, Decision.ACT]
