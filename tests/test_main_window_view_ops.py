import pytest

from core.models import Track, TrackType
from ui.main_window_view_ops import (
    OSCILLOSCOPE_NO_ENABLED_TRACKS,
    OSCILLOSCOPE_NO_SELECTED_TRACK,
    OSCILLOSCOPE_SELECTED_TRACK_DISABLED,
    OSCILLOSCOPE_USER_SELECTION_DISABLED,
    get_enabled_tracks,
    resolve_oscilloscope_tracks,
)


def make_track(name: str, *, enabled: bool = True) -> Track:
    return Track(name=name, track_type=TrackType.NOTE_TRACK, enabled=enabled)


def test_get_enabled_tracks_respects_playback_overrides():
    lead = make_track("Lead", enabled=False)
    bass = make_track("Bass", enabled=True)
    pad = make_track("Pad", enabled=False)

    enabled_tracks = get_enabled_tracks(
        [lead, bass, pad],
        {
            id(lead): True,
            id(bass): False,
        },
    )

    assert enabled_tracks == [lead]


def test_resolve_oscilloscope_tracks_prefers_valid_user_selection():
    lead = make_track("Lead")
    bass = make_track("Bass")

    tracks_to_render, issue_code = resolve_oscilloscope_tracks(
        [lead, bass],
        user_selected_tracks=[bass],
        selected_track=lead,
    )

    assert tracks_to_render == [bass]
    assert issue_code is None


@pytest.mark.parametrize(
    ("enabled_tracks", "user_selected_tracks", "selected_track", "expected_issue"),
    [
        ([], [], None, OSCILLOSCOPE_NO_ENABLED_TRACKS),
        ([make_track("Lead")], [], None, OSCILLOSCOPE_NO_SELECTED_TRACK),
        (
            [make_track("Lead")],
            [make_track("Ghost")],
            make_track("Lead"),
            OSCILLOSCOPE_USER_SELECTION_DISABLED,
        ),
        (
            [make_track("Lead")],
            [],
            make_track("Bass"),
            OSCILLOSCOPE_SELECTED_TRACK_DISABLED,
        ),
    ],
)
def test_resolve_oscilloscope_tracks_reports_invalid_states(
    enabled_tracks,
    user_selected_tracks,
    selected_track,
    expected_issue,
):
    tracks_to_render, issue_code = resolve_oscilloscope_tracks(
        enabled_tracks,
        user_selected_tracks=user_selected_tracks,
        selected_track=selected_track,
    )

    assert tracks_to_render == []
    assert issue_code == expected_issue
