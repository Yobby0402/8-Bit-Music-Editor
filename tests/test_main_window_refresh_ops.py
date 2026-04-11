from types import SimpleNamespace

from core.models import Note, Project, Track, TrackType
from ui.main_window_refresh_ops import (
    OSC_REFRESH_RENDER,
    MainWindowRefreshOpsMixin,
    build_oscilloscope_refresh_plan,
)


class FakeProgressBar:
    def __init__(self):
        self.total_times = []

    def set_total_time(self, total_time):
        self.total_times.append(total_time)


class FakeSequenceWidget:
    def __init__(self):
        self.progress_bar = FakeProgressBar()
        self.set_tracks_calls = []
        self.set_bpm_calls = []
        self.refresh_calls = []
        self.sync_note_block_calls = []
        self.sync_note_blocks_calls = []
        self.sync_track_presentation_calls = []
        self.remove_note_block_calls = []
        self.remove_note_blocks_calls = []
        self.highlighted_tracks = []
        self.project = None
        self.tracks = []
        self.track_groups = []
        self.sync_result = True
        self.sync_track_result = True
        self.remove_result = True

    def set_project(self, project):
        self.project = project

    def set_tracks(self, tracks, preserve_selection=False, refresh=True):
        self.set_tracks_calls.append((tracks, preserve_selection, refresh))
        self.tracks = tracks

    def set_bpm(self, bpm, refresh=True):
        self.set_bpm_calls.append((bpm, refresh))

    def refresh(self, force_full_refresh=False):
        self.refresh_calls.append(force_full_refresh)

    def sync_note_block(self, note, track):
        self.sync_note_block_calls.append((note, track))
        return self.sync_result

    def sync_note_blocks(self, notes_and_tracks):
        self.sync_note_blocks_calls.append(notes_and_tracks)
        return self.sync_result

    def sync_track_presentation(self, track):
        self.sync_track_presentation_calls.append(track)
        return self.sync_track_result

    def remove_note_block(self, note, track):
        self.remove_note_block_calls.append((note, track))
        return self.remove_result

    def remove_note_blocks(self, notes_and_tracks):
        self.remove_note_blocks_calls.append(notes_and_tracks)
        return self.remove_result

    def set_highlighted_track(self, track):
        self.highlighted_tracks.append(track)


class FakePanel:
    def __init__(self):
        self.project = None
        self.tracks = None
        self.volume_ratios = None

    def set_project(self, project):
        self.project = project

    def set_tracks(self, tracks):
        self.tracks = tracks

    def set_volume_ratios(self, ratios):
        self.volume_ratios = ratios


class FakePlaybackSettingsPanel(FakePanel):
    def __init__(self):
        super().__init__()
        self.state_calls = []

    def set_state(self, tracks, ratios):
        self.state_calls.append((tracks, ratios))
        self.tracks = tracks
        self.volume_ratios = ratios


class FakeUnifiedEditor:
    def __init__(self):
        self.bpm = None

    def set_bpm(self, bpm):
        self.bpm = bpm


class FakeOscilloscopeWidget:
    def __init__(self):
        self.tracks = []
        self.set_tracks_calls = []
        self.set_bpm_calls = []
        self._selected_tracks_for_render = []

    def set_tracks(self, tracks, selected_track=None):
        self.set_tracks_calls.append((list(tracks), selected_track))
        self.tracks = list(tracks)
        return True

    def set_bpm(self, bpm):
        self.set_bpm_calls.append(bpm)


class FakeWindow(MainWindowRefreshOpsMixin):
    def __init__(self):
        track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
        track.add_note(Note(pitch=60, start_time=0.0, duration=0.25))

        project = Project(name="Refresh", bpm=120.0, original_bpm=120.0)
        project.add_track(track)

        self.sequencer = SimpleNamespace(
            project=project,
            get_bpm=lambda: 120.0,
            playback_volume_ratios={},
        )
        self.sequence_widget = FakeSequenceWidget()
        self.sequence_widget.tracks = project.tracks
        self.sequence_widget.track_groups = [object()]
        self.property_panel = FakePanel()
        self.unified_editor = FakeUnifiedEditor()
        self.playback_settings_panel = FakePlaybackSettingsPanel()
        self.bpm_editor_panel = FakePanel()
        self.view_stack = SimpleNamespace(currentIndex=lambda: 0)
        self.oscilloscope_widget = FakeOscilloscopeWidget()

    def _get_selected_track(self):
        return self.sequencer.project.tracks[0] if self.sequencer.project.tracks else None


def test_update_refreshable_widgets_triggers_single_incremental_refresh():
    window = FakeWindow()

    window._update_refreshable_widgets(preserve_selection=True, force_full_refresh=False)

    assert window.sequence_widget.set_tracks_calls == [
        (window.sequencer.project.tracks, True, False)
    ]
    assert window.sequence_widget.set_bpm_calls == [(120.0, False)]
    assert window.sequence_widget.refresh_calls == [False]


def test_update_refreshable_widgets_can_request_single_full_refresh():
    window = FakeWindow()

    window._update_refreshable_widgets(preserve_selection=False, force_full_refresh=True)

    assert window.sequence_widget.set_tracks_calls == [
        (window.sequencer.project.tracks, False, False)
    ]
    assert window.sequence_widget.set_bpm_calls == [(120.0, False)]
    assert window.sequence_widget.refresh_calls == [True]


def test_update_refreshable_widgets_batches_playback_settings_refresh():
    window = FakeWindow()

    window._update_refreshable_widgets(preserve_selection=False, force_full_refresh=False)

    assert window.playback_settings_panel.state_calls == [
        (window.sequencer.project.tracks, window.sequencer.playback_volume_ratios)
    ]


def test_sync_note_block_ui_updates_local_widgets_without_full_refresh():
    window = FakeWindow()
    track = window.sequencer.project.tracks[0]
    note = track.notes[0]

    assert window._sync_note_block_ui(note, track, highlight_track=True) is True
    assert window.sequence_widget.sync_note_block_calls == [(note, track)]
    assert window.sequence_widget.progress_bar.total_times[-1] == 0.25
    assert window.sequence_widget.highlighted_tracks == [track]


def test_can_use_lightweight_note_refresh_allows_hidden_sequence_sync_in_oscilloscope_view():
    window = FakeWindow()
    window.view_stack = SimpleNamespace(currentIndex=lambda: 1)

    assert window._can_use_lightweight_note_refresh(window.sequencer.project.tracks[0]) is True


def test_remove_note_block_ui_updates_local_widgets():
    window = FakeWindow()
    track = window.sequencer.project.tracks[0]
    note = track.notes[0]

    assert window._remove_note_block_ui(note, track) is True
    assert window.sequence_widget.remove_note_block_calls == [(note, track)]
    assert window.sequence_widget.progress_bar.total_times[-1] == 0.25


def test_sync_note_blocks_ui_updates_multiple_blocks_in_one_pass():
    window = FakeWindow()
    track = window.sequencer.project.tracks[0]
    extra_note = Note(pitch=64, start_time=0.5, duration=0.25)
    track.add_note(extra_note)

    notes_and_tracks = [(track.notes[0], track), (extra_note, track)]

    assert window._sync_note_blocks_ui(notes_and_tracks) is True
    assert window.sequence_widget.sync_note_blocks_calls == [notes_and_tracks]
    assert window.sequence_widget.progress_bar.total_times[-1] == 0.75


def test_remove_note_blocks_ui_updates_multiple_blocks_in_one_pass():
    window = FakeWindow()
    track = window.sequencer.project.tracks[0]
    extra_note = Note(pitch=64, start_time=0.5, duration=0.25)
    track.add_note(extra_note)

    notes_and_tracks = [(track.notes[0], track), (extra_note, track)]

    assert window._remove_note_blocks_ui(notes_and_tracks) is True
    assert window.sequence_widget.remove_note_blocks_calls == [notes_and_tracks]
    assert window.sequence_widget.progress_bar.total_times[-1] == 0.75


def test_sync_track_ui_updates_track_widgets_without_full_refresh():
    window = FakeWindow()
    track = window.sequencer.project.tracks[0]

    assert window._sync_track_ui(track) is True
    assert window.sequence_widget.sync_track_presentation_calls == [track]
    assert window.playback_settings_panel.tracks == window.sequencer.project.tracks
    assert window.playback_settings_panel.volume_ratios == window.sequencer.playback_volume_ratios
    assert window.sequence_widget.refresh_calls == []


def test_build_oscilloscope_refresh_plan_keeps_rendering_valid_user_selection():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    bass = Track(name="Bass", track_type=TrackType.NOTE_TRACK)

    plan = build_oscilloscope_refresh_plan(
        [lead, bass],
        user_selected_tracks=[bass],
        selected_track=lead,
    )

    assert plan.action == OSC_REFRESH_RENDER
    assert plan.tracks == [bass]
    assert plan.selected_tracks_override == [bass]


def test_refresh_oscilloscope_widget_skips_redundant_clear_when_already_empty():
    window = FakeWindow()
    track = window.sequencer.project.tracks[0]
    window.view_stack = SimpleNamespace(currentIndex=lambda: 1)
    window.sequencer.playback_enabled_tracks = {id(track): False}

    window._refresh_oscilloscope_widget()

    assert window.oscilloscope_widget.set_tracks_calls == []
    assert window.oscilloscope_widget.set_bpm_calls == [120.0]
