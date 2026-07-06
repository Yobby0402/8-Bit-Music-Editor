"""Shared styling for the stacked right-side inspector panel."""

RIGHT_PANEL_STYLESHEET = """
QWidget#rightPanelShell {
    background-color: #F7FAF8;
    color: #173F20;
}
QWidget#rightPanelNav {
    background-color: #EDF7F1;
    border: 1px solid #D6E8E1;
    border-radius: 6px;
    padding: 2px;
}
QPushButton[rightPanelNavButton="true"] {
    color: #2B5D3B;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 28px;
    font-weight: 500;
}
QPushButton[rightPanelNavButton="true"]:hover {
    background-color: #DFF0E6;
    border-color: #B7DEC6;
}
QPushButton[rightPanelNavButton="true"]:checked {
    color: #FFFFFF;
    background-color: #2F8F4E;
    border-color: #24723E;
    font-weight: 600;
}
QStackedWidget#rightPanelStack,
QScrollArea#rightPanelPageScroll,
QScrollArea#rightPanelPageScroll > QWidget > QWidget {
    background-color: #F7FAF8;
}
QLabel,
QCheckBox,
QGroupBox {
    color: #173F20;
}
QLabel#panelTitle {
    color: #103717;
    padding: 2px 2px 4px 2px;
    font-size: 14px;
    font-weight: 700;
}
QLabel#panelSummary,
QLabel#emptyState,
QLabel#selectionSummary {
    color: #41664B;
    background-color: #EDF7F1;
    border: 1px solid #D6E8E1;
    border-radius: 6px;
    padding: 8px;
    line-height: 130%;
}
QLabel#emptyState {
    color: #5B7561;
}
QLabel#selectionSummary {
    color: #1F6E3A;
    font-weight: 600;
}
QWidget[panelToolbar="true"] {
    background-color: #EDF7F1;
    border: 1px solid #D6E8E1;
    border-radius: 6px;
}
QWidget[trackVolumeRow="true"] {
    background-color: #FFFFFF;
    border: 1px solid #DDEBE5;
    border-radius: 6px;
}
QLabel[metricPill="true"] {
    color: #1F6E3A;
    background-color: #E4F4EA;
    border: 1px solid #C9E7D4;
    border-radius: 5px;
    padding: 2px 6px;
    font-weight: 600;
}
QGroupBox {
    border: 1px solid #DDEBE5;
    border-radius: 6px;
    margin-top: 8px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QGroupBox[inspectorGroup="true"] {
    margin-top: 7px;
    padding: 8px 7px 7px 7px;
}
QGroupBox[innerGroup="true"] {
    border-color: #E5F0EA;
    margin-top: 6px;
    padding: 7px 6px 6px 6px;
    font-weight: 500;
}
QPushButton {
    color: #173F20;
    background-color: #FFFFFF;
    border: 1px solid #B8D8C8;
    border-radius: 5px;
    padding: 4px 10px;
    min-height: 24px;
}
QPushButton:hover {
    background-color: #E8F5E9;
    border-color: #66BB6A;
}
QPushButton:pressed,
QPushButton:checked {
    background-color: #CDEDD7;
    border-color: #2F8F4E;
}
QPushButton[primaryAction="true"] {
    color: #FFFFFF;
    background-color: #2F8F4E;
    border-color: #24723E;
    font-weight: 600;
}
QPushButton[primaryAction="true"]:hover {
    background-color: #39A75B;
}
QLineEdit,
QPlainTextEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox {
    color: #173F20;
    background-color: #FFFFFF;
    border: 1px solid #B8D8C8;
    border-radius: 5px;
    padding: 4px 6px;
    min-height: 24px;
    selection-background-color: #C5E1A5;
}
QLineEdit:focus,
QPlainTextEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border-color: #2F8F4E;
}
QTableWidget {
    color: #173F20;
    background-color: #FFFFFF;
    alternate-background-color: #F0F8F3;
    border: 1px solid #D6E8E1;
    border-radius: 5px;
    gridline-color: #D6E8E1;
    selection-background-color: #2F8FC7;
    selection-color: #FFFFFF;
}
QHeaderView::section {
    color: #173F20;
    background-color: #E8F5E9;
    border: 0;
    border-right: 1px solid #D6E8E1;
    border-bottom: 1px solid #D6E8E1;
    padding: 4px;
    font-weight: 600;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #A7D7B6;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background: #A7D7B6;
    border-radius: 5px;
    min-width: 24px;
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}
"""


def right_panel_stylesheet() -> str:
    return RIGHT_PANEL_STYLESHEET
