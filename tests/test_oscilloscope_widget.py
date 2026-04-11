from core.models import Track, TrackType
from ui.oscilloscope_widget import (
    build_track_render_signature,
    collect_enabled_unique_tracks,
    resolve_tracks_to_render,
)


def make_track(name: str, *, enabled: bool = True) -> Track:
    return Track(name=name, track_type=TrackType.NOTE_TRACK, enabled=enabled)


def test_collect_enabled_unique_tracks_filters_disabled_and_duplicates():
    lead = make_track("Lead")
    bass = make_track("Bass")
    muted = make_track("Muted", enabled=False)

    tracks = collect_enabled_unique_tracks([lead, lead, muted, bass])

    assert tracks == [lead, bass]


def test_resolve_tracks_to_render_prefers_user_selection():
    lead = make_track("Lead")
    bass = make_track("Bass")

    tracks = resolve_tracks_to_render(
        [lead, bass],
        selected_tracks_for_render=[bass],
        selected_track=lead,
    )

    assert tracks == [bass]


def test_resolve_tracks_to_render_drops_invalid_user_selection():
    lead = make_track("Lead")
    bass = make_track("Bass")
    ghost = make_track("Ghost")

    tracks = resolve_tracks_to_render(
        [lead, bass],
        selected_tracks_for_render=[ghost],
        selected_track=lead,
    )

    assert tracks == []


def test_resolve_tracks_to_render_falls_back_to_selected_track():
    lead = make_track("Lead")
    bass = make_track("Bass")

    tracks = resolve_tracks_to_render(
        [lead, bass],
        selected_tracks_for_render=[],
        selected_track=lead,
    )

    assert tracks == [lead]


def test_build_track_render_signature_preserves_order():
    lead = make_track("Lead")
    bass = make_track("Bass")

    assert build_track_render_signature([lead, bass]) != build_track_render_signature([bass, lead])
