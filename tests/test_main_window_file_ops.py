from ui.main_window_file_ops import detect_open_file_kind, resolve_export_target


def test_detect_open_file_kind_supports_project_and_midi():
    assert detect_open_file_kind("demo.JSON") == "project"
    assert detect_open_file_kind("demo.midi") == "midi"
    assert detect_open_file_kind("demo.txt") is None


def test_resolve_export_target_preserves_existing_midi_and_oga_suffixes():
    midi_target = resolve_export_target("song.midi", "")
    ogg_target = resolve_export_target("loop.oga", "")

    assert midi_target.kind == "midi"
    assert midi_target.file_path == "song.midi"
    assert ogg_target.kind == "audio"
    assert ogg_target.audio_format == "ogg"
    assert ogg_target.file_path == "loop.oga"


def test_resolve_export_target_uses_selected_filter_when_no_suffix_is_present():
    project_target = resolve_export_target("draft", "JSON项目文件 (*.json)")
    midi_target = resolve_export_target("theme", "MIDI文件 (*.mid)")

    assert project_target.file_path == "draft.json"
    assert project_target.updates_current_project_path is True
    assert midi_target.file_path == "theme.mid"
