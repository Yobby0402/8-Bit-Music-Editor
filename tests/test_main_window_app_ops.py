from types import SimpleNamespace

from ui.main_window_app_ops import build_about_text, find_category_index, get_first_segment_bpm


def test_build_about_text_contains_app_identity():
    text = build_about_text("8bit", "9.9.9")

    assert "8bit 9.9.9" in text
    assert "PyQt5" in text


def test_get_first_segment_bpm_returns_none_for_empty_segments():
    assert get_first_segment_bpm([]) is None


def test_get_first_segment_bpm_uses_first_segment():
    bpm = get_first_segment_bpm(
        [
            SimpleNamespace(bpm=144.0),
            SimpleNamespace(bpm=120.0),
        ]
    )

    assert bpm == 144.0


def test_find_category_index_returns_matching_position():
    category_names = ["显示设置", "编辑设置", "快捷键", "其他设置"]

    assert find_category_index(category_names, "快捷键") == 2
    assert find_category_index(category_names, "不存在") is None
