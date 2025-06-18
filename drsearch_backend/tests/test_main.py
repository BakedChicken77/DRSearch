import builtins
import types
import pytest


def test_main_runs(monkeypatch):
    # Patch get_settings to return a dummy settings object
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: types.SimpleNamespace(debug=False, auth_enabled=True),
    )

    # Patch create_app to return a dummy ASGI app
    monkeypatch.setattr(
        "app.main.create_app", lambda: lambda scope, receive, send: None
    )

    # Patch uvicorn.Server and its serve method
    dummy_server = types.SimpleNamespace(serve=lambda: None)
    monkeypatch.setattr("uvicorn.Server", lambda config: dummy_server)

    # Patch asyncio loop to skip real async server startup
    class DummyLoop:
        def add_signal_handler(self, *_, **__):
            pass

        def run_until_complete(self, _):
            pass

    monkeypatch.setattr("asyncio.new_event_loop", lambda: DummyLoop())
    monkeypatch.setattr("asyncio.set_event_loop", lambda loop: None)

    # Import and run the main function
    from app.main import main

    main()
