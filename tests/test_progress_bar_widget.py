from ui.progress_bar_widget import ProgressBarWidget


class FakeSlider:
    def __init__(self, value=0):
        self._value = value
        self.values = []
        self.blocked = []

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value
        self.values.append(value)

    def blockSignals(self, blocked):
        self.blocked.append(blocked)


class FakeLabel:
    def __init__(self):
        self.text_values = []

    def setText(self, text):
        self.text_values.append(text)


class FakeProgressBar:
    format_time = ProgressBarWidget.format_time
    _set_current_time_text = ProgressBarWidget._set_current_time_text
    set_current_time = ProgressBarWidget.set_current_time

    def __init__(self):
        self.is_dragging = False
        self.current_time = 10.0
        self.total_time = 100.0
        self._current_time_text = "00:10"
        self.current_time_label = FakeLabel()
        self.progress_slider = FakeSlider(value=100)


def test_set_current_time_skips_redundant_slider_and_label_update():
    widget = FakeProgressBar()

    widget.set_current_time(10.0)
    widget.set_current_time(10.2)

    assert widget.current_time_label.text_values == []
    assert widget.progress_slider.values == [102]
    assert widget.progress_slider.blocked == [True, False]
