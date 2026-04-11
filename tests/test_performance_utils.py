from types import SimpleNamespace

import pytest

import ui.performance_utils as performance_utils


def test_profile_window_operation_records_elapsed_history(monkeypatch):
    timestamps = iter([10.0, 10.25])
    monkeypatch.setattr(performance_utils, "perf_counter", lambda: next(timestamps))

    window = SimpleNamespace()

    with performance_utils.profile_window_operation(
        window,
        "editor.batch_property_change",
        note_count=3,
        ignored=None,
    ):
        pass

    assert len(window._ui_profile_history) == 1
    entry = window._ui_profile_history[0]
    assert entry["operation"] == "editor.batch_property_change"
    assert entry["outcome"] == "ok"
    assert entry["details"] == {"note_count": 3}
    assert entry["elapsed_ms"] == pytest.approx(250.0)


def test_finish_profile_span_returns_none_for_unknown_token():
    window = SimpleNamespace()

    assert performance_utils.finish_profile_span(window, 999, outcome="cancelled") is None
