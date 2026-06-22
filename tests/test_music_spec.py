from core.models import Project, TrackRole, TrackType
from core.music_spec import (
    generate_music_spec,
    music_spec_from_dict,
    music_spec_to_dict,
    music_track_to_track,
)
from core.track_events import DrumType


def _notes_by_bar(notes):
    by_bar = {}
    for note in notes:
        bar = int(note.start_beat // 4)
        by_bar.setdefault(bar, []).append(note)
    return by_bar


def test_generate_music_spec_creates_epic_multi_track_payload():
    spec = generate_music_spec(style="epic", length_bars=8, bpm=140, key="D", intensity=0.9)
    data = music_spec_to_dict(spec)

    assert data["kind"] == "epic_music"
    assert data["bpm"] == 140
    assert data["duration_beats"] == 32.0
    assert [track["role"] for track in data["tracks"][:3]] == ["melody", "bass", "harmony"]
    assert data["tracks"][3]["track_type"] == "drum"
    assert data["tracks"][0]["notes"]
    assert data["tracks"][3]["drum_events"]


def test_generate_music_spec_constrains_phrases_and_strong_beats():
    spec = generate_music_spec(style="epic", length_bars=5, bpm=140, key="C", intensity=0.9)
    melody = spec.tracks[0]
    drums = spec.tracks[3]

    assert spec.duration_beats == 32.0
    assert spec.style_params["phrase_bars"] == 4
    assert spec.style_params["melody_notes_per_bar_max"] == 5
    assert all(len(notes) <= 5 for notes in _notes_by_bar(melody.notes).values())

    for bar in range(8):
        strong_notes = {
            note.start_beat % 4: note.pitch
            for note in melody.notes
            if int(note.start_beat // 4) == bar and note.start_beat % 4 in {0.0, 2.0}
        }
        chord = {pitch + 12 for pitch in (60, 63, 67)}
        if bar % 4 == 1:
            chord = {pitch + 12 for pitch in (57, 60, 64)}
        elif bar % 4 == 2:
            chord = {pitch + 12 for pitch in (55, 58, 62)}
        elif bar % 4 == 3:
            chord = {pitch + 12 for pitch in (53, 56, 60)}
        assert strong_notes[0.0] in chord or strong_notes[0.0] - 12 in chord
        assert strong_notes[2.0] in chord or strong_notes[2.0] - 12 in chord

    drum_starts = {(event.drum_type, event.start_beat % 4) for event in drums.drum_events}
    assert (DrumType.KICK, 0.0) in drum_starts
    assert (DrumType.SNARE, 1.0) in drum_starts
    assert (DrumType.SNARE, 3.0) in drum_starts


def test_generate_music_spec_supports_playful_template():
    spec = generate_music_spec(style="轻松幽默诙谐活泼", length_bars=16, bpm=120, key="C", intensity=0.65)
    data = music_spec_to_dict(spec)

    assert data["kind"] == "playful_music"
    assert data["style_params"]["style"] == "playful"
    assert data["style_params"]["drum_template"] == "playful_backbeat"
    assert data["duration_beats"] == 64.0
    assert all(len(notes) <= 6 for notes in _notes_by_bar(spec.tracks[0].notes).values())
    assert spec.tracks[0].notes[0].start_beat == 0.0
    assert spec.tracks[0].notes[0].pitch in {72, 76, 79}


def test_music_spec_from_dict_parses_notes_drums_structure_and_effects():
    spec = music_spec_from_dict(
        {
            "kind": "custom_theme",
            "label": "Custom Theme",
            "bpm": 128,
            "time_signature": [4, 4],
            "structure": [{"name": "intro", "start_beat": 0, "duration_beats": 4}],
            "tracks": [
                {
                    "name": "Lead",
                    "role": "melody",
                    "notes": [
                        {
                            "pitch": 72,
                            "start_beat": 0,
                            "duration_beats": 1,
                            "waveform": "square",
                        }
                    ],
                    "delay_params": {
                        "delay_time": 0.08,
                        "feedback": 0.2,
                        "mix": 0.15,
                        "enabled": True,
                    },
                },
                {
                    "name": "Drums",
                    "track_type": "drum",
                    "drum_events": [{"drum_type": "kick", "start_beat": 0, "duration_beats": 0.25}],
                },
            ],
        }
    )

    assert spec.label == "Custom Theme"
    assert spec.tracks[0].role == TrackRole.MELODY
    assert spec.tracks[0].delay_params is not None
    assert spec.tracks[1].track_type == TrackType.DRUM_TRACK
    assert spec.tracks[1].drum_events[0].drum_type == DrumType.KICK


def test_music_track_to_track_offsets_notes_and_drums():
    spec = generate_music_spec(length_bars=4, bpm=120)
    project = Project(bpm=120)

    lead = music_track_to_track(project, spec.tracks[0], start_beat=4.0)
    drums = music_track_to_track(project, spec.tracks[3], start_beat=4.0)

    assert lead.notes[0].start_tick == project.beats_to_ticks(4.0)
    assert drums.drum_events[0].start_beat == 4.0
