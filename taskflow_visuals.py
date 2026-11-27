"""TaskFlow's reference-inspired surfaces and resolution-independent icons."""
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

CONTROL_STYLE = """
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #131e31, stop:1 #0c1320);
    color: #b3c6e9; border: 1px solid #2d4264; border-radius: 10px;
}
QPushButton:hover { background: #192943; border-color: #4a84e8; }
QPushButton:focus { border: 2px solid #75b7ff; }
QPushButton:pressed { background: #101b30; }
QPushButton:checked { background: #18365f; border-color: #399cff; }
"""

MENU_STYLE = """
QMenu { background: #111b2b; color: #dfebff; border: 1px solid #354c70; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 8px 18px; border-radius: 6px; }
QMenu::item:selected { background: #213d68; color: #ffffff; }
QMenu::item:disabled { color: #6d81a3; }
QMenu::separator { height: 1px; background: #283b58; margin: 5px 10px; }
"""

DARK_SCROLLBAR_STYLE = """
QScrollBar:vertical { background: transparent; width: 6px; margin: 2px 0; }
QScrollBar::handle:vertical { background: #46628a; border-radius: 3px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #60a5fa; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 6px; margin: 0 2px; }
QScrollBar::handle:horizontal { background: #46628a; border-radius: 3px; min-width: 28px; }
QScrollBar::handle:horizontal:hover { background: #60a5fa; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
"""

DIALOG_STYLE = """
QLineEdit, QTextEdit, QListWidget {
    background: #0e1624; color: #f2f5fc; border: 1px solid #354c70;
    border-radius: 8px; padding: 7px 10px; font-size: 12px;
    selection-background-color: #1d56d8; selection-color: #ffffff;
}
QLineEdit:focus, QTextEdit:focus, QListWidget:focus { border: 1px solid #60a5fa; }
QListWidget::item { padding: 7px 8px; border-radius: 6px; }
QListWidget::item:selected { background: #1e375e; color: #ffffff; }
QPushButton {
    background: #131d30; color: #d4e2ff; border: 1px solid #354c70;
    border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600;
}
QPushButton:hover { background: #1b2b45; color: #ffffff; border-color: #4f79b8; }
QPushButton:focus { border: 2px solid #75b7ff; }
QPushButton:pressed { background: #10192b; }
QPushButton:disabled { background: #101726; color: #879aba; border-color: #24334d; }
QPushButton[role="primary"] {
    background: #1d56d8; color: #ffffff; border: 1px solid #3b76f6; font-weight: 700;
}
QPushButton[role="primary"]:hover { background: #2563eb; border-color: #60a5fa; }
QPushButton[role="primary"]:focus { border: 2px solid #a9caff; }
QPushButton[role="primary"]:pressed { background: #1746b3; }
QPushButton[role="primary"]:disabled { background: #16233a; color: #879aba; border-color: #2a3d5e; }
QPushButton[role="danger"] {
    background: #c81e1e; color: #ffffff; border: 1px solid #e03e3e; font-weight: 700;
}
QPushButton[role="danger"]:hover { background: #dc2626; border-color: #f87171; }
QPushButton[role="danger"]:focus { border: 2px solid #fca5a5; }
QPushButton[role="danger"]:pressed { background: #9b1c1c; }
""" + DARK_SCROLLBAR_STYLE


def make_icon(name, color='#acc0e6', size=24):
    """Draw a single, consistent icon family at 2x for high-DPI displays."""
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size * 2 / 24, size * 2 / 24)
    pen = QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    if name == 'plus':
        p.drawLine(QPointF(5, 12), QPointF(19, 12))
        p.drawLine(QPointF(12, 5), QPointF(12, 19))
    elif name == 'close':
        p.drawLine(QPointF(6, 6), QPointF(18, 18))
        p.drawLine(QPointF(18, 6), QPointF(6, 18))
    elif name == 'hide':
        p.drawLine(QPointF(6, 12), QPointF(18, 12))
    elif name == 'pin':
        path = QPainterPath(QPointF(8, 4))
        for x, y in [(16, 4), (15, 11), (18, 14), (6, 14), (9, 11), (8, 4)]:
            path.lineTo(x, y)
        p.drawPath(path)
        p.drawLine(QPointF(12, 14), QPointF(12, 21))
    elif name in ('more', 'dots'):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        for n in (5, 12, 19):
            p.drawEllipse(QPointF(n, 12) if name == 'more' else QPointF(12, n), 1.7, 1.7)
    elif name == 'cloud':
        path = QPainterPath(QPointF(7, 18))
        path.arcTo(QRectF(2, 10, 8, 8), 270, -180)
        path.arcTo(QRectF(6, 5, 11, 11), 160, -150)
        path.arcTo(QRectF(14, 10, 8, 8), 90, -180)
        path.closeSubpath()
        p.drawPath(path)
    elif name == 'grid':
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        for x in (3, 13):
            for y in (3, 13):
                p.drawRoundedRect(QRectF(x, y, 8, 8), 1.8, 1.8)
    elif name == 'dot':
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(12, 12), 5.2, 5.2)
    elif name == 'document':
        path = QPainterPath(QPointF(5, 3))
        for x, y in [(14, 3), (19, 8), (19, 21), (5, 21), (5, 3)]:
            path.lineTo(x, y)
        p.drawPath(path)
        p.drawLine(QPointF(14, 3), QPointF(14, 8))
        p.drawLine(QPointF(14, 8), QPointF(19, 8))
        p.drawLine(QPointF(8, 12), QPointF(16, 12))
        p.drawLine(QPointF(8, 16), QPointF(13, 16))
    elif name == 'calendar':
        p.drawRoundedRect(QRectF(4, 5, 16, 16), 2, 2)
        p.drawLine(QPointF(4, 10), QPointF(20, 10))
        for x in (8, 16):
            p.drawLine(QPointF(x, 3), QPointF(x, 7))
    elif name == 'note':
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 2.5, 2.5)
        p.drawLine(QPointF(8, 9), QPointF(16, 9))
        p.drawLine(QPointF(8, 13), QPointF(16, 13))
        p.drawLine(QPointF(8, 17), QPointF(12.5, 17))
    elif name == 'warning':
        path = QPainterPath(QPointF(12, 3.5))
        path.lineTo(21, 19.5)
        path.lineTo(3, 19.5)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(12, 9.5), QPointF(12, 13.8))
        p.drawPoint(QPointF(12, 16.8))
    elif name == 'blocked':
        p.drawEllipse(QRectF(3.5, 3.5, 17, 17))
        p.drawLine(QPointF(6.5, 17.5), QPointF(17.5, 6.5))
    elif name == 'sync':
        p.drawArc(QRectF(4, 4, 16, 16), 35 * 16, 145 * 16)
        p.drawArc(QRectF(4, 4, 16, 16), 215 * 16, 145 * 16)
        p.drawLine(QPointF(17, 5), QPointF(20, 8))
        p.drawLine(QPointF(7, 19), QPointF(4, 16))
    elif name == 'check_circle':
        p.drawEllipse(QRectF(3.5, 3.5, 17, 17))
        path = QPainterPath(QPointF(8, 12.2))
        path.lineTo(10.8, 15)
        path.lineTo(16.2, 9.2)
        p.drawPath(path)
    elif name in ('check', 'logo'):
        if name == 'logo':
            gradient = QLinearGradient(4, 5, 19, 21)
            gradient.setColorAt(0, QColor('#27baff'))
            gradient.setColorAt(.48, QColor('#3973ff'))
            gradient.setColorAt(1, QColor('#9638ef'))
            p.setPen(QPen(gradient, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        path = QPainterPath(QPointF(4, 12))
        path.lineTo(10, 18)
        path.lineTo(21, 5)
        p.drawPath(path)
    elif name == 'stats':
        gradient = QLinearGradient(3, 3, 21, 21)
        gradient.setColorAt(0, QColor('#2ec5ff'))
        gradient.setColorAt(1, QColor('#5354ff'))
        p.setBrush(gradient)
        p.setPen(Qt.NoPen)
        for x, y in ((3, 12), (10, 4), (17, 9)):
            p.drawRoundedRect(QRectF(x, y, 4, 22-y), 1.2, 1.2)
    elif name == 'sparkle':
        gradient = QLinearGradient(4, 3, 20, 22)
        gradient.setColorAt(0, QColor('#2eb9ff'))
        gradient.setColorAt(1, QColor('#a64dff'))
        p.setBrush(gradient)
        p.setPen(Qt.NoPen)
        path = QPainterPath(QPointF(12, 2))
        for x, y in [(15, 9), (22, 12), (15, 15), (12, 22), (9, 15), (2, 12), (9, 9), (12, 2)]:
            path.lineTo(x, y)
        p.drawPath(path)
    p.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
