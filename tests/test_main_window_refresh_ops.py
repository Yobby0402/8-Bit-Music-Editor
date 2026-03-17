from core.models import Track, TrackType
from ui.main_window_refresh_ops import (
    OSC_REFRESH_BPM_ONLY,
    OSC_REFRESH_CLEAR,
    OSC_REFRESH_RENDER,
    build_oscilloscope_refresh_plan,
)


def make_track(name: str, *, enabled: bool = True) -> Track:
    return Track(name=name, track_type=TrackType.NOTE_TRACK, enabled=enabled)


def test_build_oscilloscope_refresh_plan_prefers_bpm_only_for_valid_user_selection():
    lead = make_track("Lead")
    bass = make_track("Bass")

    plan = build_oscilloscope_refresh_plan([lead, bass], [bass], lead)

    assert plan.action == OSC_REFRESH_BPM_ONLY
    assert plan.tracks == []


def test_build_oscilloscope_refresh_plan_clears_when_user_selection_is_invalid():
    lead = make_track("Lead")
    ghost = make_track("Ghost")

    plan = build_oscilloscope_refresh_plan([lead], [ghost], lead)

    assert plan.action == OSC_REFRESH_CLEAR
    assert plan.tracks == []


def test_build_oscilloscope_refresh_plan_uses_selected_track_when_available():
    lead = make_track("Lead")
    bass = make_track("Bass")

    plan = build_oscilloscope_refresh_plan([lead, bass], [], bass)

    assert plan.action == OSC_REFRESH_RENDER
    assert plan.tracks == [lead, bass]
    assert plan.selected_track is bass
    assert plan.selected_tracks_override is None


def test_build_oscilloscope_refresh_plan_renders_all_when_three_or_fewer_tracks():
    lead = make_track("Lead")
    bass = make_track("Bass")

    plan = build_oscilloscope_refresh_plan([lead, bass], [], None)

    assert plan.action == OSC_REFRESH_RENDER
    assert plan.tracks == [lead, bass]
    assert plan.selected_track is None
    assert plan.selected_tracks_override is None


def test_build_oscilloscope_refresh_plan_defaults_to_first_three_tracks():
    tracks = [make_track(f"Track {index}") for index in range(4)]

    plan = build_oscilloscope_refresh_plan(tracks, [], None)

    assert plan.action == OSC_REFRESH_RENDER
    assert plan.tracks == tracks[:3]
    assert plan.selected_tracks_override == tracks[:3]
