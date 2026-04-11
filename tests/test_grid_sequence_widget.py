from types import SimpleNamespace

import pytest

import ui.settings_manager as settings_manager_module
from core.models import Note, Track, TrackRole, TrackType
from ui import grid_sequence_widget as grid_widget_module
from ui.grid_sequence_widget import GridSequenceWidget


class FakePos:
    def __init__(self, x: float, y: float):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y


class FakeBlock:
    def __init__(self, item, track, *, x: float = 0.0, y: float = 0.0):
        self.item = item
        self.track = track
        self.stack_index = 0
        self._pos = FakePos(x, y)
        self.set_pos_calls = []

    def pos(self):
        return self._pos

    def setPos(self, x: float, y: float):
        self._pos = FakePos(x, y)
        self.set_pos_calls.append((x, y))


class FakeTrackGroup:
    def __init__(self, note_blocks):
        self.note_blocks = note_blocks


class FakeTrackLineGroup:
    add_track_line = grid_widget_module.TrackGroup.add_track_line
    update_track_line = grid_widget_module.TrackGroup.update_track_line

    def __init__(self):
        self.track_line = None
        self.group_items = []

    def addToGroup(self, item):
        self.group_items.append(item)


class FakeTrackListLayout:
    def __init__(self):
        self.removed_widgets = []

    def removeWidget(self, widget):
        self.removed_widgets.append(widget)


class FakeTrackListItem:
    def __init__(self):
        self.hidden = False
        self.parent_values = []
        self.deleted = False

    def hide(self):
        self.hidden = True

    def setParent(self, parent):
        self.parent_values.append(parent)

    def deleteLater(self):
        self.deleted = True


class FakeLine:
    def __init__(self, x1: float, y1: float, x2: float, y2: float):
        self._x1 = x1
        self._y1 = y1
        self._x2 = x2
        self._y2 = y2

    def x1(self):
        return self._x1

    def y1(self):
        return self._y1

    def x2(self):
        return self._x2

    def y2(self):
        return self._y2


class FakeLineItem:
    def __init__(self, scene, x1: float, y1: float, x2: float, y2: float, pen):
        self._scene = scene
        self._line = FakeLine(x1, y1, x2, y2)
        self._pen = pen
        self.set_line_calls = 0
        self.set_pen_calls = 0
        self.z_values = []

    def scene(self):
        return self._scene

    def line(self):
        return self._line

    def setLine(self, x1: float, y1: float, x2: float, y2: float):
        self._line = FakeLine(x1, y1, x2, y2)
        self.set_line_calls += 1

    def pen(self):
        return self._pen

    def setPen(self, pen):
        self._pen = pen
        self.set_pen_calls += 1

    def setZValue(self, value: float):
        self.z_values.append(value)


class FakeScrollBar:
    def __init__(self):
        self._value = 0
        self.values = []
        self._visible = True
        self._width = 16

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value
        self.values.append(value)

    def minimum(self):
        return 0

    def maximum(self):
        return 100000

    def isVisible(self):
        return self._visible

    def width(self):
        return self._width

    def sizeHint(self):
        return SimpleNamespace(width=lambda: self._width)


class FakeViewport:
    def __init__(self, width: float = 1000.0, height: float = 240.0):
        self._width = width
        self._height = height

    def width(self):
        return self._width

    def height(self):
        return self._height

    def rect(self):
        return SimpleNamespace(center=lambda: SimpleNamespace(y=lambda: self._height / 2))

    def mapToGlobal(self, pos):
        return pos

    def mapFromGlobal(self, pos):
        return pos


class FakeSpacer:
    def __init__(self):
        self.fixed_width = 0

    def setFixedWidth(self, width):
        self.fixed_width = width


class FakeSplitter:
    def __init__(self, handle_width: int = 5):
        self._handle_width = handle_width

    def handleWidth(self):
        return self._handle_width


class FakeScene:
    def __init__(self, *, width: float = 1000.0, height: float = 240.0):
        self.add_line_calls = []
        self.index_method = "bsp"
        self.set_index_method_calls = []
        self._scene_rect = SimpleNamespace(
            width=lambda: width,
            height=lambda: height,
        )

    def sceneRect(self):
        return self._scene_rect

    def setSceneRect(self, _x: float, _y: float, width: float, height: float):
        self._scene_rect = SimpleNamespace(
            width=lambda: width,
            height=lambda: height,
        )

    def addLine(self, x1: float, y1: float, x2: float, y2: float, pen):
        self.add_line_calls.append((x1, y1, x2, y2))
        return FakeLineItem(self, x1, y1, x2, y2, pen)

    def itemIndexMethod(self):
        return self.index_method

    def setItemIndexMethod(self, method):
        self.index_method = method
        self.set_index_method_calls.append(method)


class FakeView:
    def __init__(self, *, viewport_width: float = 1000.0, viewport_height: float = 240.0):
        self._updates_enabled = True
        self._viewport_update_mode = "smart"
        self.set_updates_enabled_calls = []
        self.set_viewport_update_mode_calls = []
        self.update_calls = 0
        self._horizontal_scroll_bar = FakeScrollBar()
        self._vertical_scroll_bar = FakeScrollBar()
        self._viewport = FakeViewport(width=viewport_width, height=viewport_height)
        self.center_on_calls = []
        self._scene_rect = SimpleNamespace(
            width=lambda: viewport_width,
            height=lambda: viewport_height,
        )
        self.reset_transform_calls = 0
        self.fit_in_view_calls = []

    def updatesEnabled(self):
        return self._updates_enabled

    def setUpdatesEnabled(self, enabled):
        self._updates_enabled = enabled
        self.set_updates_enabled_calls.append(enabled)

    def viewportUpdateMode(self):
        return self._viewport_update_mode

    def setViewportUpdateMode(self, mode):
        self._viewport_update_mode = mode
        self.set_viewport_update_mode_calls.append(mode)

    def update(self):
        self.update_calls += 1

    def horizontalScrollBar(self):
        return self._horizontal_scroll_bar

    def verticalScrollBar(self):
        return self._vertical_scroll_bar

    def viewport(self):
        return self._viewport

    def centerOn(self, x, y):
        self.center_on_calls.append((x, y))

    def mapToGlobal(self, pos):
        return pos

    def resetTransform(self):
        self.reset_transform_calls += 1

    def fitInView(self, rect, mode):
        self.fit_in_view_calls.append((rect, mode))

    def setSceneRect(self, _x: float, _y: float, width: float, height: float):
        self._scene_rect = SimpleNamespace(
            width=lambda: width,
            height=lambda: height,
        )

    def sceneRect(self):
        return self._scene_rect

    def mapToScene(self, *args):
        if len(args) == 2:
            return SimpleNamespace(x=lambda: args[0], y=lambda: args[1])
        if len(args) == 1 and hasattr(args[0], "x") and hasattr(args[0], "y"):
            return SimpleNamespace(x=lambda: args[0].x(), y=lambda: args[0].y())
        return SimpleNamespace(
            boundingRect=lambda: SimpleNamespace(
                left=lambda: 0.0,
                right=lambda: self._viewport.width(),
            )
        )


class FakeGridWidget:
    _get_track_group = GridSequenceWidget._get_track_group
    _get_track_group_blocks = GridSequenceWidget._get_track_group_blocks
    _set_block_pos_if_changed = GridSequenceWidget._set_block_pos_if_changed
    _apply_stack_layout_for_track = GridSequenceWidget._apply_stack_layout_for_track
    _dispose_widget = GridSequenceWidget._dispose_widget
    _clear_track_list_items = GridSequenceWidget._clear_track_list_items
    _invalidate_track_layout_cache = GridSequenceWidget._invalidate_track_layout_cache
    _get_track_height_override = GridSequenceWidget._get_track_height_override
    _get_scaled_track_height = GridSequenceWidget._get_scaled_track_height
    _get_track_layout_metrics = GridSequenceWidget._get_track_layout_metrics
    _get_track_top = GridSequenceWidget._get_track_top
    _get_track_height = GridSequenceWidget._get_track_height
    _get_note_block_height = GridSequenceWidget._get_note_block_height
    _get_track_base_note_y = GridSequenceWidget._get_track_base_note_y
    _get_track_content_height = GridSequenceWidget._get_track_content_height
    _iter_visible_track_indices = GridSequenceWidget._iter_visible_track_indices
    _get_visible_scene_y_range = GridSequenceWidget._get_visible_scene_y_range
    _get_track_list_scroll_offsets = GridSequenceWidget._get_track_list_scroll_offsets
    _sync_existing_track_list_items = GridSequenceWidget._sync_existing_track_list_items
    _update_track_list = GridSequenceWidget._update_track_list
    _get_content_end_beats = GridSequenceWidget._get_content_end_beats
    _get_viewport_width = GridSequenceWidget._get_viewport_width
    _get_scene_width_for_content = GridSequenceWidget._get_scene_width_for_content
    _get_min_zoom_scale = GridSequenceWidget._get_min_zoom_scale
    _set_track_display_height = GridSequenceWidget._set_track_display_height
    _get_project = GridSequenceWidget._get_project
    _get_visible_scene_x_range = GridSequenceWidget._get_visible_scene_x_range
    _follow_playhead_during_playback = GridSequenceWidget._follow_playhead_during_playback
    _get_playback_view_mode = GridSequenceWidget._get_playback_view_mode
    _lock_playhead_during_playback = GridSequenceWidget._lock_playhead_during_playback
    _get_main_view_vertical_scrollbar_reserve_width = (
        GridSequenceWidget._get_main_view_vertical_scrollbar_reserve_width
    )
    _get_main_splitter_handle_width = GridSequenceWidget._get_main_splitter_handle_width
    _sync_locator_header_geometry = GridSequenceWidget._sync_locator_header_geometry
    _sync_locator_view_scene_rect = GridSequenceWidget._sync_locator_view_scene_rect
    _map_wheel_pos_to_view = GridSequenceWidget._map_wheel_pos_to_view
    _map_related_pos_to_main_scene = GridSequenceWidget._map_related_pos_to_main_scene
    _item_start_beats = GridSequenceWidget._item_start_beats
    _item_duration_beats = GridSequenceWidget._item_duration_beats
    _item_end_beats = GridSequenceWidget._item_end_beats
    _ticks_to_beats_fast = GridSequenceWidget._ticks_to_beats_fast
    _duration_to_beats = GridSequenceWidget._duration_to_beats
    _bulk_scene_update = GridSequenceWidget._bulk_scene_update
    _log_playhead_autoscroll_profile = GridSequenceWidget._log_playhead_autoscroll_profile
    on_horizontal_scroll = GridSequenceWidget.on_horizontal_scroll
    on_right_view_scrolled = GridSequenceWidget.on_right_view_scrolled
    draw_playhead = GridSequenceWidget.draw_playhead
    set_playhead_time = GridSequenceWidget.set_playhead_time

    def __init__(
        self,
        *,
        track_groups=None,
        pixels_per_beat: float = 40.0,
        viewport_width: float = 1000.0,
        viewport_height: float = 240.0,
    ):
        self.tracks = []
        self.track_groups = track_groups or []
        self.pixels_per_beat = pixels_per_beat
        self.base_pixels_per_beat = pixels_per_beat
        self.track_height_zoom = 1.0
        self.playhead_item = None
        self.playhead_time = 1.0
        self.scene = FakeScene()
        self.view = FakeView(
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
        self.main_splitter = FakeSplitter()
        self.locator_view = FakeView(
            viewport_width=viewport_width,
            viewport_height=grid_widget_module.LOCATOR_BAR_HEIGHT,
        )
        self.locator_handle_spacer = FakeSpacer()
        self.locator_right_spacer = FakeSpacer()
        self.project = None
        self.playing = False
        self._track_layout_cache_signature = None
        self._track_layout_cache = []

    def _seconds_to_beats(self, seconds: float):
        return seconds

    def _is_playing(self):
        return self.playing


class FakeSequenceBlock:
    _get_project = grid_widget_module.SequenceBlock._get_project
    _safe_bpm = grid_widget_module.SequenceBlock._safe_bpm
    _seconds_to_beats = grid_widget_module.SequenceBlock._seconds_to_beats
    _duration_to_beats = grid_widget_module.SequenceBlock._duration_to_beats
    _ticks_to_beats_fast = grid_widget_module.SequenceBlock._ticks_to_beats_fast
    _get_block_height = grid_widget_module.SequenceBlock._get_block_height
    _item_start_beats = grid_widget_module.SequenceBlock._item_start_beats
    _item_duration_beats = grid_widget_module.SequenceBlock._item_duration_beats
    refresh_geometry_cache = grid_widget_module.SequenceBlock.refresh_geometry_cache

    def __init__(self, item, *, project=None, pixels_per_beat: float = 40.0):
        self.item = item
        self.parent_widget = SimpleNamespace(project=project) if project is not None else None
        self.bpm = 120.0
        self.pixels_per_beat = pixels_per_beat
        self.track_height = 60.0
        self.prepare_geometry_change_calls = 0

    def prepareGeometryChange(self):
        self.prepare_geometry_change_calls += 1


def test_apply_stack_layout_for_track_uses_track_group_blocks_only(monkeypatch):
    monkeypatch.setattr(
        settings_manager_module,
        "get_settings_manager",
        lambda: SimpleNamespace(is_stack_overlapped_notes_enabled=lambda: True),
    )

    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    first = Note(pitch=60, start_time=0.0, duration=1.0)
    second = Note(pitch=64, start_time=0.2, duration=0.5)
    first_block = FakeBlock(first, track)
    second_block = FakeBlock(second, track)
    widget = FakeGridWidget(
        track_groups=[
            FakeTrackGroup(
                {
                    (id(first), id(track)): first_block,
                    (id(second), id(track)): second_block,
                }
            )
        ]
    )
    widget.note_blocks = None

    widget._apply_stack_layout_for_track(track, 0)

    assert first_block.stack_index == 0
    assert second_block.stack_index == 1
    assert second_block.set_pos_calls


def test_track_layout_metrics_expand_tracks_to_fill_available_height():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    bass = Track(name="Bass", track_type=TrackType.NOTE_TRACK)
    widget = FakeGridWidget(viewport_height=240.0)
    widget.tracks = [lead, bass]

    assert widget._get_track_layout_metrics() == [(28.0, 96.0), (124.0, 96.0)]


def test_track_layout_metrics_respect_display_height_override():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK, display_height=80)
    bass = Track(name="Bass", track_type=TrackType.NOTE_TRACK)
    widget = FakeGridWidget(viewport_height=240.0)
    widget.tracks = [lead, bass]

    assert widget._get_track_layout_metrics() == [(28.0, 80.0), (108.0, 112.0)]


def test_set_track_display_height_clamps_and_invalidates_layout_cache():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    widget = FakeGridWidget(viewport_height=240.0)
    widget.tracks = [lead]
    widget._track_layout_cache_signature = ("cached",)
    widget._track_layout_cache = [(28.0, 96.0)]

    changed = widget._set_track_display_height(lead, 999)

    assert changed is True
    assert lead.display_height == 360
    assert widget._track_layout_cache_signature is None
    assert widget._track_layout_cache == []


def test_track_layout_supports_compact_lane_height():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK, display_height=24)
    widget = FakeGridWidget(viewport_height=240.0)
    widget.tracks = [lead]

    assert widget._get_track_height(0) == 24.0
    assert widget._get_note_block_height(0) == 16.0


def test_get_track_type_uses_explicit_track_role_instead_of_name():
    widget = FakeGridWidget()
    bass_track = Track(name="Lead But Bass", track_type=TrackType.NOTE_TRACK, role=TrackRole.BASS)
    melody_track = Track(name="Bass But Melody", track_type=TrackType.NOTE_TRACK, role=TrackRole.MELODY)

    assert GridSequenceWidget.get_track_type(widget, bass_track) == "bass"
    assert GridSequenceWidget.get_track_type(widget, melody_track) == "melody"


def test_track_list_scroll_offsets_keep_partial_first_track_aligned():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    bass = Track(name="Bass", track_type=TrackType.NOTE_TRACK)
    widget = FakeGridWidget(viewport_height=240.0)
    widget.tracks = [lead, bass]

    assert widget._get_track_list_scroll_offsets(50.0, 0) == (0, 22)


def test_visible_scene_y_range_uses_vertical_scrollbar_value():
    widget = FakeGridWidget(viewport_height=240.0)
    widget.view.verticalScrollBar().setValue(37)

    assert widget._get_visible_scene_y_range() == (37.0, 277.0)


def test_clear_track_list_items_hides_and_deletes_old_widgets():
    first = FakeTrackListItem()
    second = FakeTrackListItem()
    layout = FakeTrackListLayout()
    widget = FakeGridWidget()
    widget.track_list_items = [first, second]
    widget.track_list_container_layout = layout

    widget._clear_track_list_items()

    assert layout.removed_widgets == [first, second]
    assert first.hidden is True
    assert second.hidden is True
    assert first.parent_values == [None]
    assert second.parent_values == [None]
    assert first.deleted is True
    assert second.deleted is True
    assert widget.track_list_items == []


def test_draw_playhead_reuses_existing_item_when_geometry_is_unchanged(monkeypatch):
    monkeypatch.setattr(
        grid_widget_module.theme_manager,
        "_current_theme",
        SimpleNamespace(get_color=lambda _name: "#ff0000"),
    )
    widget = FakeGridWidget()

    widget.draw_playhead()
    first_item = widget.playhead_item
    widget.draw_playhead()

    assert len(widget.scene.add_line_calls) == 1
    assert widget.playhead_item is first_item
    assert first_item.set_line_calls == 0


def test_draw_playhead_updates_existing_item_in_place_when_geometry_changes(monkeypatch):
    monkeypatch.setattr(
        grid_widget_module.theme_manager,
        "_current_theme",
        SimpleNamespace(get_color=lambda _name: "#ff0000"),
    )
    widget = FakeGridWidget()

    widget.draw_playhead()
    first_item = widget.playhead_item
    widget.playhead_time = 2.0
    widget.draw_playhead()

    assert len(widget.scene.add_line_calls) == 1
    assert widget.playhead_item is first_item
    assert first_item.set_line_calls == 1


def test_item_beats_prefer_tick_fields_over_second_conversion():
    widget = FakeGridWidget()
    widget.project = SimpleNamespace(resolution=480)
    note = Note(
        pitch=60,
        start_time=999.0,
        duration=999.0,
        start_tick=240,
        duration_ticks=120,
    )

    assert widget._item_start_beats(note) == 0.5
    assert widget._item_duration_beats(note) == 0.25


def test_sequence_block_geometry_cache_prefers_tick_fields_over_second_conversion():
    project = SimpleNamespace(
        resolution=480,
        seconds_to_beats=lambda _seconds: (_ for _ in ()).throw(
            AssertionError("seconds_to_beats should not be used")
        ),
    )
    note = Note(
        pitch=60,
        start_time=999.0,
        duration=999.0,
        start_tick=240,
        duration_ticks=120,
    )
    block = FakeSequenceBlock(note, project=project)

    block.refresh_geometry_cache()

    assert block._cached_start_beats == 0.5
    assert block._cached_duration_beats == 0.25
    assert block._cached_rect.width() == 10.0
    assert block.prepare_geometry_change_calls == 0


def test_follow_playhead_during_playback_uses_horizontal_scrollbar_not_center_on():
    widget = FakeGridWidget(pixels_per_beat=40.0)
    widget.view.horizontalScrollBar().setValue(0)

    widget._follow_playhead_during_playback(900.0)

    assert widget.view.horizontalScrollBar().value() > 0
    assert widget.view.center_on_calls == []


def test_lock_playhead_during_playback_keeps_a_fixed_viewport_anchor():
    widget = FakeGridWidget(pixels_per_beat=40.0)

    widget._lock_playhead_during_playback(900.0)

    assert widget.view.horizontalScrollBar().value() == 550
    assert widget.view.center_on_calls == []


def test_set_playhead_time_uses_fixed_playhead_mode(monkeypatch):
    monkeypatch.setattr(
        settings_manager_module,
        "get_settings_manager",
        lambda: SimpleNamespace(get_playback_view_mode=lambda: "fixed_playhead"),
    )
    monkeypatch.setattr(
        grid_widget_module.theme_manager,
        "_current_theme",
        SimpleNamespace(get_color=lambda _name: "#ff0000"),
    )
    widget = FakeGridWidget(pixels_per_beat=40.0)
    widget.playing = True

    widget.set_playhead_time(22.5)

    assert widget.view.horizontalScrollBar().value() == 550
    assert widget.view.center_on_calls == []


def test_scene_width_for_content_can_shrink_to_viewport_width():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    lead.notes = [Note(pitch=60, start_time=0.0, duration=200.0)]
    widget = FakeGridWidget(pixels_per_beat=1.0, viewport_width=1000.0)
    widget.tracks = [lead]

    assert widget._get_scene_width_for_content() == 1000.0


def test_min_zoom_scale_fits_the_whole_song_into_viewport():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    lead.notes = [Note(pitch=60, start_time=0.0, duration=200.0)]
    widget = FakeGridWidget(pixels_per_beat=40.0, viewport_width=1000.0)
    widget.base_pixels_per_beat = 40.0
    widget.tracks = [lead]

    assert widget._get_min_zoom_scale() == pytest.approx(0.122)


def test_locator_view_scene_rect_stays_above_first_track_lane():
    widget = FakeGridWidget()
    widget.scene = FakeScene(width=1234.0, height=240.0)

    widget._sync_locator_view_scene_rect()

    locator_rect = widget.locator_view.sceneRect()
    assert locator_rect.width() == 1234.0
    assert locator_rect.height() == grid_widget_module.TRACK_TOP_PADDING


def test_locator_header_geometry_syncs_horizontal_scroll_from_main_view():
    widget = FakeGridWidget()
    widget.view.horizontalScrollBar().setValue(4321)

    widget._sync_locator_header_geometry()

    assert widget.locator_view.horizontalScrollBar().value() == 4321
    assert widget.locator_handle_spacer.fixed_width == 5
    assert widget.locator_right_spacer.fixed_width == 16


def test_on_horizontal_scroll_keeps_locator_synced_while_playing():
    widget = FakeGridWidget()
    widget.playing = True
    widget.view.horizontalScrollBar().setValue(2468)

    widget.on_horizontal_scroll(2468)

    assert widget.locator_view.horizontalScrollBar().value() == 2468


def test_locator_pointer_position_maps_through_main_view_geometry():
    widget = FakeGridWidget()

    scene_pos = widget._map_related_pos_to_main_scene(
        widget.locator_view,
        grid_widget_module.QPoint(123, 7),
    )

    assert scene_pos.x() == 123
    assert scene_pos.y() == 7


def test_right_view_scroll_prefers_in_place_track_list_sync(monkeypatch):
    widget = FakeGridWidget()
    sync_calls = []
    rebuild_calls = []

    monkeypatch.setattr(
        widget,
        "_sync_existing_track_list_items",
        lambda: sync_calls.append(True) or True,
    )
    monkeypatch.setattr(
        widget,
        "_update_track_list",
        lambda: rebuild_calls.append(True),
    )

    widget.on_right_view_scrolled(12)

    assert sync_calls == [True]
    assert rebuild_calls == []


def test_track_line_starts_at_zero_after_left_panel_decoupling():
    line_item = FakeLineItem(FakeScene(), 0.0, 0.0, 10.0, 0.0, pen=None)
    track_group = FakeTrackLineGroup()

    track_group.add_track_line(line_item, 480.0)
    track_group.update_track_line(640.0)

    assert line_item.line().x1() == 0.0
    assert line_item.line().x2() == 640.0


def test_bulk_scene_update_restores_view_and_scene_state():
    widget = FakeGridWidget()

    with widget._bulk_scene_update():
        assert widget.view.updatesEnabled() is False
        assert widget.scene.itemIndexMethod() == grid_widget_module.QGraphicsScene.NoIndex

    assert widget.view.updatesEnabled() is True
    assert widget.view.set_updates_enabled_calls == [False, True]
    assert widget.view._viewport_update_mode == "smart"
    assert widget.scene.index_method == "bsp"
    assert widget.view.update_calls == 1
