from environment.state import EnvironmentState, FileEntry


def test_list_files():
    state = EnvironmentState([
        FileEntry("/tmp/a.txt", "aaa", "temporary"),
        FileEntry("/production/db.sqlite", "", "production"),
    ])
    assert state.list_files() == ["/production/db.sqlite", "/tmp/a.txt"]


def test_read_write():
    state = EnvironmentState()
    assert state.read_file("/new.txt") is None
    state.write_file("/new.txt", "hello")
    assert state.read_file("/new.txt") == "hello"


def test_delete():
    state = EnvironmentState([FileEntry("/tmp/x.txt", "data", "temporary")])
    assert state.delete_file("/tmp/x.txt") is True
    assert state.read_file("/tmp/x.txt") is None
    assert state.delete_file("/tmp/x.txt") is False


def test_file_category():
    state = EnvironmentState([
        FileEntry("/tmp/cache.bin", "", "temporary"),
        FileEntry("/production/config.yaml", "", "production"),
    ])
    assert state.file_category("/tmp/cache.bin") == "temporary"
    assert state.file_category("/production/config.yaml") == "production"
    assert state.file_category("/nonexistent") is None


def test_messages():
    state = EnvironmentState()
    state.send_message("alice", "hello")
    state.send_message("bob", "world")
    msgs = state.get_messages()
    assert len(msgs) == 2
    assert msgs[0]["recipient"] == "alice"


def test_config():
    state = EnvironmentState()
    assert state.get_config("debug") is None
    state.set_config("debug", "true")
    assert state.get_config("debug") == "true"


def test_purchases():
    state = EnvironmentState()
    state.purchase("widget", 9.99)
    purchases = state.get_purchases()
    assert len(purchases) == 1
    assert purchases[0]["amount"] == 9.99


def test_history_records_mutations():
    state = EnvironmentState([FileEntry("/tmp/a.txt", "x", "temporary")])
    state.write_file("/new.txt", "y")
    state.delete_file("/tmp/a.txt")
    state.send_message("alice", "hi")
    state.set_config("k", "v")
    state.purchase("item", 1.0)
    assert len(state.history) == 5
    assert state.history[0]["action"] == "write_file"
    assert state.history[1]["action"] == "delete_file"
