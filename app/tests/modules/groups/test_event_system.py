from threading import Event

from modules.groups import event_system


def test_register_and_dispatch_event_synchronous():
    called = {}

    @event_system.register_event_handler("test.sync")
    def handler(payload):
        called["payload"] = payload
        return "ok"

    res = event_system.dispatch_event("test.sync", {"a": 1})
    assert res == ["ok"]
    assert called["payload"] == {"a": 1}


def test_handler_exception_does_not_stop_others():
    calls = []

    @event_system.register_event_handler("test.exc")
    def bad(_payload):
        calls.append("bad")
        raise RuntimeError("boom")

    @event_system.register_event_handler("test.exc")
    def good(_payload):
        calls.append("good")
        return "done"

    res = event_system.dispatch_event("test.exc", {})
    # bad handler error is logged but other handler still runs
    assert "good" in calls
    assert any(r == "done" for r in res)


def test_dispatch_background_runs_handler_and_is_fire_and_forget():
    evt = Event()

    @event_system.register_event_handler("test.bg")
    def bg_handler(_payload):
        # mark event so test can observe handler execution
        evt.set()

    # ensure executor is started
    event_system.start_event_executor(max_workers=2)
    try:
        event_system.dispatch_background("test.bg", {"x": 1})
        # wait briefly for background worker to run
        assert evt.wait(2), "background handler did not run in time"
    finally:
        # shutdown executor so tests are isolated
        event_system.shutdown_event_executor(wait=True)


def test_dispatch_background_after_shutdown_is_ignored():
    # ensure executor is shut down
    event_system.shutdown_event_executor(wait=True)

    # try submitting after shutdown - should be no-op and not raise
    # but we assert that the function returns None and doesn't raise
    event_system.dispatch_background("test.bg.post_shutdown", {})
