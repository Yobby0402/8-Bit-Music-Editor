from core.models import TrackRole, TrackType
from ui.main_window_dialogs import (
    build_new_track_default_name,
    resolve_new_track_role_from_editor_index,
)


def test_build_new_track_default_name_depends_on_track_type():
    assert build_new_track_default_name(0, TrackType.NOTE_TRACK) == "音轨 1"
    assert build_new_track_default_name(3, TrackType.NOTE_TRACK) == "音轨 4"
    assert build_new_track_default_name(9, TrackType.DRUM_TRACK) == "打击乐"


def test_resolve_new_track_role_from_editor_index_matches_expected_roles():
    assert resolve_new_track_role_from_editor_index(0) == TrackRole.MELODY
    assert resolve_new_track_role_from_editor_index(1) == TrackRole.BASS
    assert resolve_new_track_role_from_editor_index(2) == TrackRole.HARMONY
    assert resolve_new_track_role_from_editor_index(3) == TrackRole.EFFECT
    assert resolve_new_track_role_from_editor_index(999) == TrackRole.MELODY
