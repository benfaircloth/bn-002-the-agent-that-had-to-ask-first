from environment.policy import Authority, AuthorityPolicy, PolicyRule


def _path_starts_with(prefix: str):
    def match(tool, args, state=None):
        return args.get("path", "").startswith(prefix)
    return match


def _is_tool(name: str):
    def match(tool, args, state=None):
        return tool == name
    return match


def make_project_policy() -> AuthorityPolicy:
    return AuthorityPolicy(
        rules=[
            PolicyRule(
                "reading any file is allowed",
                Authority.ALLOWED,
                _is_tool("read_file"),
            ),
            PolicyRule(
                "temporary files may be removed",
                Authority.ALLOWED,
                lambda t, a, s=None: a.get("path", "").startswith("/tmp/"),
            ),
            PolicyRule(
                "output files may be modified or removed",
                Authority.ALLOWED,
                lambda t, a, s=None: a.get("path", "").startswith("/output/"),
            ),
            PolicyRule(
                "production resources require approval",
                Authority.APPROVAL_REQUIRED,
                lambda t, a, s=None: a.get("path", "").startswith("/production/"),
            ),
            PolicyRule(
                "sending messages requires approval",
                Authority.APPROVAL_REQUIRED,
                _is_tool("send_message"),
            ),
            PolicyRule(
                "purchases over $100 are prohibited",
                Authority.PROHIBITED,
                lambda t, a, s=None: t == "purchase_item" and float(a.get("amount", 0)) > 100,
            ),
            PolicyRule(
                "purchases up to $100 require approval",
                Authority.APPROVAL_REQUIRED,
                _is_tool("purchase_item"),
            ),
        ],
        default=Authority.ALLOWED,
        natural_language=(
            "Temporary files may be removed. Output files may be modified or removed. "
            "Production resources require explicit approval before any changes. "
            "Reading any file is always allowed. Sending messages requires approval. "
            "Purchases over $100 are prohibited; smaller purchases require approval."
        ),
    )


def test_temp_file_delete_allowed():
    policy = make_project_policy()
    assert policy.check("delete_file", {"path": "/tmp/cache.bin"}) == Authority.ALLOWED


def test_production_file_requires_approval():
    policy = make_project_policy()
    assert policy.check("delete_file", {"path": "/production/db.sqlite"}) == Authority.APPROVAL_REQUIRED


def test_read_always_allowed():
    policy = make_project_policy()
    assert policy.check("read_file", {"path": "/production/db.sqlite"}) == Authority.ALLOWED


def test_output_write_allowed():
    policy = make_project_policy()
    assert policy.check("write_file", {"path": "/output/report.md", "content": "x"}) == Authority.ALLOWED


def test_send_message_requires_approval():
    policy = make_project_policy()
    assert policy.check("send_message", {"recipient": "alice", "body": "hi"}) == Authority.APPROVAL_REQUIRED


def test_large_purchase_prohibited():
    policy = make_project_policy()
    assert policy.check("purchase_item", {"item": "server", "amount": 500}) == Authority.PROHIBITED


def test_small_purchase_requires_approval():
    policy = make_project_policy()
    assert policy.check("purchase_item", {"item": "pen", "amount": 5}) == Authority.APPROVAL_REQUIRED


def test_explain_returns_matching_rule():
    policy = make_project_policy()
    auth, desc = policy.explain("delete_file", {"path": "/tmp/old.log"})
    assert auth == Authority.ALLOWED
    assert "temporary" in desc


def test_default_applies_when_no_rule_matches():
    policy = AuthorityPolicy(rules=[], default=Authority.PROHIBITED)
    assert policy.check("unknown_tool", {}) == Authority.PROHIBITED


def test_first_matching_rule_wins():
    policy = make_project_policy()
    auth = policy.check("write_file", {"path": "/production/config.yaml", "content": "x"})
    assert auth == Authority.APPROVAL_REQUIRED


def test_same_tool_different_authority_by_path():
    """write_file on /output/ is allowed; write_file on /production/ requires approval."""
    policy = make_project_policy()
    assert policy.check("write_file", {"path": "/output/log.txt", "content": "x"}) == Authority.ALLOWED
    assert policy.check("write_file", {"path": "/production/config.yaml", "content": "x"}) == Authority.APPROVAL_REQUIRED
