from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPolygon,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QWidget,
)


RED = QColor("#C8102E")
BODY_TOP = QColor("#4A5A63")
BODY_MID = QColor("#3A4A52")
BODY_BOT = QColor("#2B383F")

_TONE_COLORS = {
    "normal": QColor("#F4F6F7"),
    "ok": QColor("#7DCE9A"),
    "warn": QColor("#E7A06C"),
    "err": QColor("#EF7A6E"),
}


def vertical_gradient(rect: QRect) -> QLinearGradient:
    return QLinearGradient(
        float(rect.left()),
        float(rect.top()),
        float(rect.left()),
        float(rect.bottom()),
    )


def paint_nfs_body(widget: QWidget, painter: QPainter, header_cut: int = 76) -> None:
    gradient = QLinearGradient(0.0, 0.0, 0.0, float(widget.height()))
    gradient.setColorAt(0.0, BODY_TOP)
    gradient.setColorAt(0.45, BODY_MID)
    gradient.setColorAt(1.0, BODY_BOT)
    painter.fillRect(widget.rect(), QBrush(gradient))
    shine = QLinearGradient(
        float(widget.width()) * 0.42,
        80.0,
        float(widget.width()),
        float(widget.height()) * 0.55,
    )
    shine.setColorAt(0.0, QColor(255, 255, 255, 0))
    shine.setColorAt(0.55, QColor(255, 255, 255, 10))
    shine.setColorAt(0.82, QColor(255, 255, 255, 28))
    shine.setColorAt(1.0, QColor(255, 255, 255, 6))
    painter.fillRect(widget.rect().adjusted(0, header_cut, 0, 0), QBrush(shine))


def nfs_chrome_stylesheet() -> str:
    return (
        "QLabel#section { color: #C5CDD2; font-size: 12px; font-weight: 700; "
        "letter-spacing: 2px; background: transparent; }"
        "QLabel#hint, QLabel#notice, QLabel#status, QLabel#path { background: transparent; }"
        "QLabel#hint { color: #A7B3B9; font-size: 11px; }"
        "QLabel#notice { color: #E7A06C; font-size: 11px; }"
        "QLabel#status { color: #A7B3B9; font-size: 11px; }"
        "QLabel#path { color: #D5DCE1; font-size: 11px; }"
        "QToolTip { background: #2B383F; color: #F4F6F7; border: 1px solid #C8102E; }"
        "QScrollArea#nfsPage { border: 0; background: transparent; }"
        "QScrollArea#nfsPage QWidget#nfsPageBody { background: transparent; }"
        "QScrollArea { border: 1px solid #1C2428; background: #2A3237; }"
        "QScrollArea QWidget#scrollBody { background: #2A3237; }"
        "QScrollBar:vertical { background: #2A3237; width: 12px; margin: 0; border: 0; }"
        "QScrollBar::handle:vertical { background: #9AA4AC; min-height: 28px; }"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        "QTextEdit#nfsLog { background: #1C2428; color: #D5DCE1; border: 1px solid #1C2428; "
        "padding: 8px; font-family: Consolas, 'Cascadia Mono', monospace; font-size: 11px; selection-background-color: #C8102E; }"
        "QMessageBox { background: #3A4A52; color: #F4F6F7; }"
        "QMessageBox QLabel { color: #F4F6F7; background: transparent; }"
        "QMessageBox QPushButton { background: #C2CAD0; color: #C8102E; font-weight: 800; "
        "padding: 8px 18px; border: 1px solid #1C2428; min-width: 80px; }"
        "QMessageBox QPushButton:hover { background: #E1E6EA; }"
    )


def available_geometry(widget: QWidget) -> QRect:
    screen = widget.screen()
    if screen is None:
        app = QApplication.instance()
        screen = app.primaryScreen() if app is not None else None
    if screen is None:
        return QRect(0, 0, 1024, 768)
    return screen.availableGeometry()


def fit_nfs_window(
    window: QWidget,
    preferred_width: int,
    preferred_height: int,
    *,
    min_width: int = 400,
    min_height: int = 420,
) -> None:
    area = available_geometry(window)
    max_w = max(min_width, area.width() - 16)
    max_h = max(min_height, area.height() - 28)
    width = min(preferred_width, max_w)
    height = min(preferred_height, max_h)
    window.setMinimumSize(min(min_width, width), min(min_height, height))
    window.resize(width, height)
    x = area.x() + max(0, (area.width() - width) // 2)
    y = area.y() + max(0, (area.height() - height) // 2)
    window.move(x, y)


def make_nfs_page_scroll(parent: QWidget | None = None) -> tuple[QScrollArea, QWidget]:
    scroll = QScrollArea(parent)
    scroll.setObjectName("nfsPage")
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    scroll.viewport().setAutoFillBackground(False)
    body = QWidget()
    body.setObjectName("nfsPageBody")
    body.setAutoFillBackground(False)
    body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    scroll.setWidget(body)
    return scroll, body


def make_wrapping_label(text: str = "", object_name: str = "hint") -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    return label


def install_nfs_fonts(fonts_dir: Path | None = None) -> None:
    regular_family = "Bahnschrift" if "Bahnschrift" in QFontDatabase.families() else "Segoe UI"
    if fonts_dir is not None:
        for filename in ("gothambook.ttf", "gothambold.ttf", "gothamblack.ttf"):
            font_id = QFontDatabase.addApplicationFont(str(fonts_dir / filename))
            families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
            if families and filename == "gothambook.ttf":
                regular_family = families[0]
    app = QApplication.instance()
    if app is not None:
        app.setFont(QFont(regular_family, 10))


def make_section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("section")
    return label


def _normalize_items(
    items: list[tuple[str, object]] | list[tuple[str, object, bool]],
) -> list[tuple[str, object, bool]]:
    normalized: list[tuple[str, object, bool]] = []
    for item in items:
        if len(item) == 2:
            text, data = item
            normalized.append((text, data, True))
        else:
            text, data, enabled = item
            normalized.append((text, data, bool(enabled)))
    return normalized


class NfsHeader(QWidget):
    def __init__(self, title: str, subtitle: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self.setFixedHeight(84)

    def set_text(self, title: str, subtitle: str) -> None:
        self._title = title
        self._subtitle = subtitle
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()

        path = QPainterPath()
        path.moveTo(0, 0)
        path.lineTo(width, 0)
        path.lineTo(width, height - 22)
        path.lineTo(0, height - 10)
        path.closeSubpath()
        painter.fillPath(path, QBrush(QColor("#F1F1F1")))

        edge = QPainterPath()
        edge.moveTo(0, height - 10)
        edge.lineTo(width, height - 22)
        edge.lineTo(width, height - 16)
        edge.lineTo(0, height - 4)
        edge.closeSubpath()
        painter.fillPath(edge, QBrush(QColor("#1C2428")))

        title_box = QRect(20, 8, max(40, width - 40), 40)
        title_font = QFont(self.font())
        title_font.setBold(True)
        title_size = 30 if width >= 500 else 24 if width >= 420 else 20
        title_font.setPixelSize(title_size)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2 if width >= 480 else 0.4)
        painter.setFont(title_font)
        painter.setPen(RED)
        title = QFontMetrics(title_font).elidedText(
            self._title, Qt.TextElideMode.ElideRight, title_box.width()
        )
        painter.drawText(title_box, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

        sub_box = QRect(20, 46, max(40, width - 40), 20)
        sub_font = QFont(self.font())
        sub_font.setBold(True)
        sub_font.setPixelSize(11)
        sub_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0 if width >= 480 else 0.2)
        painter.setFont(sub_font)
        painter.setPen(QColor("#6A7378"))
        subtitle = QFontMetrics(sub_font).elidedText(
            self._subtitle, Qt.TextElideMode.ElideRight, sub_box.width()
        )
        painter.drawText(sub_box, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, subtitle)


class NfsOptionRow(QWidget):
    valueChanged = pyqtSignal()

    LABEL_H = 24
    VALUE_H = 44

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._items: list[tuple[str, object, bool]] = []
        self._index = 0
        self._hovered = False
        self._pressed_side = 0
        self._interactive = True
        self.setFixedHeight(self.LABEL_H + self.VALUE_H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_label(self, label: str) -> None:
        self._label = label
        self.update()

    def set_interactive(self, interactive: bool) -> None:
        self._interactive = interactive
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if interactive else Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor if interactive else Qt.CursorShape.ArrowCursor)
        self.update()

    def set_items(
        self,
        items: list[tuple[str, object]] | list[tuple[str, object, bool]],
    ) -> None:
        previous = self.current_data()
        self._items = _normalize_items(items)
        self._index = 0
        if previous is not None:
            for index, (_, data, _) in enumerate(self._items):
                if data == previous:
                    self._index = index
                    break
        self.update()

    def set_current_data(self, data: object) -> None:
        for index, (_, item_data, _) in enumerate(self._items):
            if item_data == data:
                self._index = index
                self.update()
                return
        if self._items:
            self._index = 0
        self.update()

    def current_data(self) -> object | None:
        if not self._items:
            return None
        return self._items[self._index][1]

    def current_text(self) -> str:
        if not self._items:
            return ""
        return self._items[self._index][0]

    def item_labels(self) -> list[str]:
        return [text for text, _data, _enabled in self._items]

    def _enabled_indices(self) -> list[int]:
        return [index for index, (_, _, enabled) in enumerate(self._items) if enabled]

    def can_cycle(self) -> bool:
        return self._interactive and self.isEnabled() and len(self._enabled_indices()) > 1

    def _is_lit(self) -> bool:
        return self.isEnabled() and (self.hasFocus() or self._hovered)

    def cycle(self, step: int) -> None:
        enabled = self._enabled_indices()
        if not self.can_cycle() or len(enabled) < 2:
            return
        try:
            position = enabled.index(self._index)
        except ValueError:
            position = 0
        new_index = enabled[(position + step) % len(enabled)]
        if new_index == self._index:
            return
        self._index = new_index
        self.update()
        self.valueChanged.emit()

    def _label_rect(self) -> QRect:
        return QRect(0, 0, self.width(), self.LABEL_H)

    def _value_rect(self) -> QRect:
        return QRect(0, self.LABEL_H, self.width(), self.VALUE_H)

    def _arrow_hit(self, pos: QPoint) -> int:
        value = self._value_rect()
        if not value.contains(pos) or not self.can_cycle():
            return 0
        if pos.x() <= value.left() + 46:
            return -1
        if pos.x() >= value.right() - 46:
            return 1
        return 0

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        lit = self._is_lit()
        enabled = self.isEnabled()
        label_rect = self._label_rect()
        value_rect = self._value_rect()

        label_grad = vertical_gradient(label_rect)
        if lit:
            label_grad.setColorAt(0.0, QColor("#F8F9FA"))
            label_grad.setColorAt(0.12, QColor("#E7EBEE"))
            label_grad.setColorAt(0.55, QColor("#CDD4DA"))
            label_grad.setColorAt(1.0, QColor("#A7B1B8"))
        else:
            label_grad.setColorAt(0.0, QColor("#6E7A81"))
            label_grad.setColorAt(0.4, QColor("#586368"))
            label_grad.setColorAt(1.0, QColor("#414B51"))
        painter.fillRect(label_rect, QBrush(label_grad))
        painter.setPen(QPen(QColor(255, 255, 255, 110 if lit else 36), 1))
        painter.drawLine(label_rect.left() + 1, label_rect.top() + 1, label_rect.right() - 1, label_rect.top() + 1)
        painter.setPen(QPen(QColor(0, 0, 0, 90 if lit else 50), 1))
        painter.drawLine(label_rect.left(), label_rect.bottom(), label_rect.right(), label_rect.bottom())

        value_grad = vertical_gradient(value_rect)
        if lit:
            value_grad.setColorAt(0.0, QColor("#6C787F"))
            value_grad.setColorAt(0.45, QColor("#515B61"))
            value_grad.setColorAt(1.0, QColor("#3C454B"))
        else:
            value_grad.setColorAt(0.0, QColor("#3F484E"))
            value_grad.setColorAt(1.0, QColor("#2A3237"))
        painter.fillRect(value_rect, QBrush(value_grad))
        inset = value_rect.adjusted(10, 7, -10, -7)
        well = vertical_gradient(inset)
        well.setColorAt(0.0, QColor(0, 0, 0, 55 if lit else 30))
        well.setColorAt(0.35, QColor(255, 255, 255, 18 if lit else 8))
        well.setColorAt(1.0, QColor(0, 0, 0, 50))
        painter.fillRect(inset, QBrush(well))

        painter.setPen(QPen(QColor(0, 0, 0, 180), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.setPen(QPen(QColor(255, 255, 255, 45), 1))
        painter.drawLine(1, 1, self.width() - 2, 1)

        label_font = QFont(self.font())
        label_font.setBold(True)
        label_font.setPixelSize(11 if self.width() < 440 else 12)
        label_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8 if self.width() < 440 else 1.2)
        painter.setFont(label_font)
        painter.setPen(QColor("#FFFFFF") if enabled else QColor("#9AA3A8"))
        label_box = label_rect.adjusted(12, 0, -12, 0)
        caption = QFontMetrics(label_font).elidedText(
            self._label.upper(), Qt.TextElideMode.ElideRight, max(20, label_box.width())
        )
        painter.drawText(label_box, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, caption)

        text = self.current_text().upper()
        value_box = value_rect.adjusted(40, 4, -40, -4)
        value_font = QFont(self.font())
        value_font.setBold(True)
        value_font.setPixelSize(14 if self.width() < 440 else 15)
        value_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.2 if self.width() < 480 else 0.6)
        painter.setFont(value_font)
        painter.setPen(QColor("#F4F6F7") if enabled else QColor("#8B959A"))
        flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
        metrics = QFontMetrics(value_font)
        if metrics.boundingRect(value_box, int(flags), text).height() > value_box.height():
            value_font.setPixelSize(12)
            value_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.0)
            painter.setFont(value_font)
            metrics = QFontMetrics(value_font)
        if metrics.boundingRect(value_box, int(flags), text).height() > value_box.height():
            text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(20, value_box.width() * 2 - 12))
        painter.drawText(value_box, flags, text)

        if self.can_cycle() and lit:
            cy = value_rect.center().y()
            self._draw_chevron(painter, 20, cy, -1, self._pressed_side == -1)
            self._draw_chevron(painter, self.width() - 20, cy, 1, self._pressed_side == 1)

    def _draw_chevron(self, painter: QPainter, cx: int, cy: int, direction: int, pressed: bool) -> None:
        span, depth = (8, 10) if not pressed else (7, 9)
        if direction < 0:
            points = QPolygon([
                QPoint(cx + depth, cy - span),
                QPoint(cx + depth, cy + span),
                QPoint(cx - 3, cy),
            ])
        else:
            points = QPolygon([
                QPoint(cx - depth, cy - span),
                QPoint(cx - depth, cy + span),
                QPoint(cx + 3, cy),
            ])
        painter.setPen(QPen(QColor(0, 0, 0, 120), 1))
        painter.setBrush(QBrush(QColor("#C8102E") if pressed else QColor("#F7FAFC")))
        painter.drawPolygon(points)

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._hovered = False
        self._pressed_side = 0
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if not self._interactive:
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if not self.can_cycle():
            return
        side = self._arrow_hit(event.position().toPoint())
        self._pressed_side = side if side else 1
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        side = self._pressed_side
        self._pressed_side = 0
        self.update()
        if side and self._value_rect().contains(event.position().toPoint()):
            self.cycle(side)

    def _page_needs_scroll(self) -> bool:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                bar = parent.verticalScrollBar()
                return bar is not None and bar.maximum() > 0
            parent = parent.parentWidget()
        return False

    def wheelEvent(self, event) -> None:  # noqa: ANN001
        if not self.can_cycle():
            event.ignore()
            return
        if not self.hasFocus() and self._page_needs_scroll():
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self.cycle(-1)
            event.accept()
        elif delta < 0:
            self.cycle(1)
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_A):
            self.cycle(-1)
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_D, Qt.Key.Key_Space, Qt.Key.Key_Return):
            self.cycle(1)
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:  # noqa: ANN001
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:  # noqa: ANN001
        super().focusOutEvent(event)
        self.update()


class NfsInfoRow(QWidget):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._value = ""
        self._tone = "normal"
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(48)

    def set_label(self, label: str) -> None:
        self._label = label
        self.update()

    def setText(self, text: str) -> None:
        self._value = text
        self._refresh_height()
        self.update()

    def text(self) -> str:
        return self._value

    def set_tone(self, tone: str) -> None:
        self._tone = tone if tone in _TONE_COLORS else "normal"
        self.update()

    def _label_font(self) -> QFont:
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(11)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        return font

    def _value_font(self) -> QFont:
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(12)
        return font

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        text_w = max(40, width - 28)
        bounds = QFontMetrics(self._value_font()).boundingRect(
            QRect(0, 0, text_w, 4000),
            int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap),
            self._value or " ",
        )
        return max(48, 26 + bounds.height() + 10)

    def sizeHint(self) -> QSize:
        width = max(self.width(), 200)
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        return QSize(180, 48)

    def _refresh_height(self) -> None:
        height = self.heightForWidth(max(self.width(), 180))
        if self.minimumHeight() != height:
            self.setMinimumHeight(height)
            self.updateGeometry()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        self._refresh_height()
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        grad = vertical_gradient(rect)
        grad.setColorAt(0.0, QColor("#3F484E"))
        grad.setColorAt(1.0, QColor("#2A3237"))
        painter.fillRect(rect, QBrush(grad))
        inset = rect.adjusted(6, 4, -6, -4)
        well = vertical_gradient(inset)
        well.setColorAt(0.0, QColor(0, 0, 0, 30))
        well.setColorAt(0.35, QColor(255, 255, 255, 8))
        well.setColorAt(1.0, QColor(0, 0, 0, 50))
        painter.fillRect(inset, QBrush(well))
        painter.setPen(QPen(QColor(0, 0, 0, 180), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.setPen(QPen(QColor(255, 255, 255, 45), 1))
        painter.drawLine(1, 1, rect.width() - 2, 1)

        label_font = self._label_font()
        painter.setFont(label_font)
        painter.setPen(QColor("#C5CDD2"))
        caption = QFontMetrics(label_font).elidedText(
            self._label.upper(), Qt.TextElideMode.ElideRight, max(20, rect.width() - 28)
        )
        painter.drawText(
            QRect(14, 5, max(20, rect.width() - 28), 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            caption,
        )

        painter.setFont(self._value_font())
        painter.setPen(_TONE_COLORS.get(self._tone, _TONE_COLORS["normal"]))
        painter.drawText(
            QRect(14, 24, max(20, rect.width() - 28), max(16, rect.height() - 32)),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
            self._value,
        )


class NfsActionButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None, *, compact: bool = False) -> None:
        super().__init__(text, parent)
        self._compact = compact
        self.setFixedHeight(36 if compact else 46)
        self.setMinimumWidth(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        hovered = self.underMouse() and self.isEnabled()
        pressed = self.isDown() and self.isEnabled()
        focused = self.hasFocus() and self.isEnabled()

        grad = vertical_gradient(rect)
        if not self.isEnabled():
            grad.setColorAt(0.0, QColor("#5A6368"))
            grad.setColorAt(1.0, QColor("#3E464B"))
        elif pressed:
            grad.setColorAt(0.0, QColor("#B4BCC2"))
            grad.setColorAt(1.0, QColor("#8A949C"))
        elif hovered or focused:
            grad.setColorAt(0.0, QColor("#F7F8F9"))
            grad.setColorAt(0.2, QColor("#E1E6EA"))
            grad.setColorAt(1.0, QColor("#A8B2BA"))
        else:
            grad.setColorAt(0.0, QColor("#D5DCE1"))
            grad.setColorAt(0.45, QColor("#C2CAD0"))
            grad.setColorAt(1.0, QColor("#9AA4AC"))
        painter.fillRect(rect, QBrush(grad))
        painter.setPen(QPen(QColor(0, 0, 0, 170), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
        painter.drawLine(1, 1, rect.width() - 2, 1)

        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(13 if self._compact else 16)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8 if self._compact else 1.4)
        text = self.text().upper()
        available = max(20, rect.width() - 16)
        metrics = QFontMetrics(font)
        if metrics.horizontalAdvance(text) > available:
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.0)
            metrics = QFontMetrics(font)
        if metrics.horizontalAdvance(text) > available:
            font.setPixelSize(11 if self._compact else 13)
            metrics = QFontMetrics(font)
        painter.setFont(font)
        painter.setPen(RED if self.isEnabled() else QColor("#8B959A"))
        painter.drawText(
            rect.adjusted(8, 0, -8, 0),
            Qt.AlignmentFlag.AlignCenter,
            metrics.elidedText(text, Qt.TextElideMode.ElideRight, available),
        )


class NfsProgressBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._minimum = 0
        self._maximum = 100
        self._value = 0
        self.setFixedHeight(20)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._minimum = minimum
        self._maximum = max(maximum, minimum)
        self.update()

    def setValue(self, value: int) -> None:
        self._value = value
        self.update()

    def value(self) -> int:
        return self._value

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        track = vertical_gradient(rect)
        track.setColorAt(0.0, QColor("#3F484E"))
        track.setColorAt(1.0, QColor("#2A3237"))
        painter.fillRect(rect, QBrush(track))
        painter.setPen(QPen(QColor(0, 0, 0, 180), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.drawLine(1, 1, rect.width() - 2, 1)

        span = self._maximum - self._minimum
        fraction = 0.0 if span <= 0 else (self._value - self._minimum) / span
        fraction = max(0.0, min(1.0, fraction))
        fill_width = int((rect.width() - 2) * fraction)
        if fill_width > 0:
            fill_rect = QRect(1, 1, fill_width, rect.height() - 2)
            fill = vertical_gradient(fill_rect)
            fill.setColorAt(0.0, QColor("#E23A4C"))
            fill.setColorAt(0.45, RED)
            fill.setColorAt(1.0, QColor("#8E0B1F"))
            painter.fillRect(fill_rect, QBrush(fill))
            painter.setPen(QPen(QColor(255, 255, 255, 70), 1))
            painter.drawLine(fill_rect.left(), fill_rect.top(), fill_rect.right(), fill_rect.top())
