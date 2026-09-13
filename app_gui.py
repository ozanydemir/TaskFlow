import os
import sys
from PyQt5.QtCore import Qt, QSize, QRectF, QRect, QEvent, pyqtSignal, QPoint, QTimer
from PyQt5.QtGui import QIcon, QFont, QColor, QPainter, QPen, QCursor, QPixmap, QFontMetrics
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QCheckBox, QSystemTrayIcon, QMenu, QAction, QDialog,
    QFrame, QSizePolicy, QSizeGrip, QScrollArea
)

import autostart
from task_manager import TaskManager
from taskflow_visuals import make_icon, CONTROL_STYLE, MENU_STYLE
from datetime import datetime

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

white_check_path = get_resource_path(os.path.join("resources", "check_mark_white.png")).replace("\\", "/")

# The visible frame remains 1px. This is only the invisible pointer catchment
# around it, so resizing does not require pixel-perfect aim.
BORDER_MARGIN = 16

# 16 Distinct Cyberpunk / Modern Palettes (bg, text/border)
DISTINCT_PALETTES = [
    ('#082029', '#00f2fe'),  # 1. Cyan / Aqua
    ('#092618', '#10b981'),  # 2. Emerald Green
    ('#220f38', '#c084fc'),  # 3. Electric Purple
    ('#291e0a', '#fbbf24'),  # 4. Amber / Gold
    ('#2e0f14', '#f87171'),  # 5. Coral Red
    ('#0c1e3d', '#38bdf8'),  # 6. Sky Blue
    ('#2b0c20', '#f472b6'),  # 7. Hot Pink
    ('#1c2908', '#a3e635'),  # 8. Lime Green
    ('#1c1138', '#818cf8'),  # 9. Indigo / Violet
    ('#2e1708', '#fb923c'),  # 10. Orange
    ('#082622', '#2dd4bf'),  # 11. Teal
    ('#290a24', '#e879f9'),  # 12. Magenta
    ('#2b2605', '#fde047'),  # 13. Canary Yellow
    ('#0b2b30', '#38d9a9'),  # 14. Mint
    ('#2d1a38', '#d946ef'),  # 15. Fuchsia
    ('#142338', '#60a5fa'),  # 16. Royal Blue
]

def get_project_color(proj_name, project_list=None):
    if not proj_name:
        return ('#101726', '#71829e')
    if project_list and proj_name in project_list:
        idx = project_list.index(proj_name)
    else:
        idx = sum(ord(c) for c in proj_name)
    return DISTINCT_PALETTES[idx % len(DISTINCT_PALETTES)]


# --- Custom Drag & Wheel Scroll Area for Project Tabs ---
class DraggableScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFixedHeight(38)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._dragging = False
        self._drag_start_x = 0
        self._scroll_start_val = 0

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start_x = event.globalX()
            self._scroll_start_val = self.horizontalScrollBar().value()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            dx = event.globalX() - self._drag_start_x
            self.horizontalScrollBar().setValue(self._scroll_start_val - dx)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        # Convert wheel scroll to horizontal scroll
        delta = event.angleDelta().y() or event.angleDelta().x()
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta)
        event.accept()


# --- Tab Button Supporting Drag-Scroll and Click ---
class ScrollableTabButton(QPushButton):
    def __init__(self, text, scroll_area, parent=None):
        super().__init__(text, parent)
        self.scroll_area = scroll_area
        self._press_pos = None
        self._is_panning = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.globalPos()
            self._is_panning = False
            self.scroll_area._drag_start_x = event.globalX()
            self.scroll_area._scroll_start_val = self.scroll_area.horizontalScrollBar().value()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_pos is not None:
            dist = (event.globalPos() - self._press_pos).manhattanLength()
            if dist > 6:
                self._is_panning = True
                dx = event.globalX() - self.scroll_area._drag_start_x
                self.scroll_area.horizontalScrollBar().setValue(self.scroll_area._scroll_start_val - dx)
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_panning:
            self._is_panning = False
            self._press_pos = None
            event.accept()
            return
        self._is_panning = False
        self._press_pos = None
        super().mouseReleaseEvent(event)


# --- Custom In-Theme Modal Dialogs ---
class ModernDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setMinimumWidth(320)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        self.card = QFrame(self)
        self.card.setStyleSheet("""
            QFrame {
                background-color: #090d16;
                border: 1px solid #2563eb;
                border-radius: 14px;
            }
        """)
        outer_layout.addWidget(self.card)

        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(18, 16, 18, 16)
        self.card_layout.setSpacing(14)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: bold; border: none;")
        self.card_layout.addWidget(title_lbl)


class CustomInputDialog(ModernDialog):
    def __init__(self, title, prompt, parent=None):
        super().__init__(title, parent)
        prompt_lbl = QLabel(prompt)
        prompt_lbl.setStyleSheet("color: #71829e; font-size: 12px; border: none;")
        self.card_layout.addWidget(prompt_lbl)

        self.input_field = QLineEdit()
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #0e1422;
                color: #ffffff;
                border: 1px solid #1e2a42;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)
        self.input_field.returnPressed.connect(self.accept)
        self.card_layout.addWidget(self.input_field)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #101726;
                color: #71829e;
                border: 1px solid #1a253a;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #162035;
                color: #ffffff;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("Ekle")
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        self.card_layout.addLayout(btn_layout)

    def get_text(self):
        return self.input_field.text().strip()


class CustomConfirmDialog(ModernDialog):
    def __init__(self, title, message, confirm_text="Temizle", is_destructive=True, parent=None):
        super().__init__(title, parent)
        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet("color: #94a3b8; font-size: 13px; border: none; line-height: 1.4;")
        self.card_layout.addWidget(msg_lbl)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        cancel_btn = QPushButton("Vazgeç")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #101726;
                color: #71829e;
                border: 1px solid #1a253a;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #162035;
                color: #ffffff;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton(confirm_text)
        confirm_btn.setCursor(Qt.PointingHandCursor)
        if is_destructive:
            confirm_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 16px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                }
            """)
        else:
            confirm_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 16px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #3b82f6;
                }
            """)
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(confirm_btn)

        self.card_layout.addLayout(btn_layout)


# --- Circular Progress Ring ---
class CircularProgressWidget(QWidget):
    def __init__(self, size=44, parent=None):
        super().__init__(parent)
        self.widget_size = size
        self.percentage = 0
        self.setFixedSize(size, size)
        self.setToolTip("Tamamlanma Oranı")

    def set_percentage(self, val):
        self.percentage = max(0, min(100, int(val)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Keep the compact release proportions even when the window is resized.
        pen_width = 3.6
        margin = pen_width / 2.0 + 1.2
        rect = QRectF(margin, margin, self.widget_size - 2*margin, self.widget_size - 2*margin)

        # Background track
        bg_pen = QPen(QColor("#1d2c46"), pen_width)
        bg_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Royal blue arc
        if self.percentage > 0:
            fg_pen = QPen(QColor("#348dff"), pen_width)
            fg_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(fg_pen)
            start_angle = 90 * 16
            span_angle = -int(self.percentage * 3.6 * 16)
            painter.drawArc(rect, start_angle, span_angle)

        painter.setPen(QColor(255, 255, 255))
        font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, f"{self.percentage}%")


# --- Task Item Card ---
class TaskItemWidget(QFrame):
    task_toggled = pyqtSignal(str)
    task_deleted = pyqtSignal(str)
    task_edited = pyqtSignal(str, str)
    task_noted = pyqtSignal(str, str)

    def __init__(self, task, project_list, parent=None):
        super().__init__(parent)
        self.task = task
        self.project_list = project_list
        self.setObjectName("TaskCard")
        self.setStyleSheet("""
            QFrame#TaskCard {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #141f30,stop:1 #0e1623);
                border: 1px solid #304461; border-radius: 16px;
            }
            QFrame#TaskCard:hover { border-color: #49658b; }
            QLabel { border: none; background: transparent; }
        """)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(12, 10, 12, 10)
        self.row.setSpacing(12)
        self.checkbox = QCheckBox()
        self.checkbox.setAccessibleName("Görevi tamamla")
        self.checkbox.setChecked(task.get('completed', False))
        self.checkbox.setCursor(Qt.PointingHandCursor)
        self.checkbox.setStyleSheet(f"""
            QCheckBox {{ border: none; background: transparent; }}
            QCheckBox::indicator {{ width: 20px; height: 20px; border: 2px solid #8da4cd;
                border-radius: 6px; background: #101a2b; }}
            QCheckBox::indicator:hover, QCheckBox::indicator:focus {{ border-color: #4ca4ff; }}
            QCheckBox::indicator:checked {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #249cff,stop:1 #4935f5);
                border-color: #5898ff; image: url({white_check_path}); }}
        """)
        self.checkbox.stateChanged.connect(lambda: self.task_toggled.emit(task['id']))
        self.row.addWidget(self.checkbox, 0, Qt.AlignTop)
        self.content = QVBoxLayout()
        self.content.setSpacing(8)
        self.title_label = QLabel(task.get('title', ''))
        self.title_label.setTextFormat(Qt.PlainText)
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.title_label.setMinimumWidth(0)
        font = QFont("Segoe UI")
        font.setPointSize(10)
        font.setStrikeOut(task.get('completed', False))
        self.title_label.setFont(font)
        self.title_label.setMaximumWidth(16777215)
        self.title_label.setStyleSheet("color: %s;" % ('#91a5c7' if task.get('completed') else '#f2f5fc'))
        self.content.addWidget(self.title_label)
        self.metadata = QHBoxLayout()
        self.metadata.setSpacing(6)
        calendar = QLabel()
        calendar.setPixmap(make_icon('calendar', '#96add4', 18).pixmap(18, 18))
        self.metadata.addWidget(calendar)
        date = task.get('completed_at') or task.get('created_at', '')
        try:
            parsed = datetime.strptime(date, '%d.%m.%Y %H:%M')
            date_text = 'Bugün' if parsed.date() == datetime.now().date() else parsed.strftime('%d.%m.%Y')
        except ValueError:
            date_text = date.split(' ')[0]
        if task.get('completed'):
            date_text = 'Tamamlandı' + ('  ·  ' + date_text if date_text else '')
        self.date_label = QLabel(date_text)
        self.date_label.setStyleSheet('color: #96add4; font-size: 11px;')
        self.metadata.addWidget(self.date_label)
        self.note_btn = QPushButton()
        note = task.get('notes', '')
        self.note_btn.setText('·  ' + (note if len(note) < 28 else note[:25] + '…') if note else '·  Ek not ekle...')
        self.note_btn.setToolTip(note or 'Göreve ek not ekle')
        self.note_btn.setCursor(Qt.PointingHandCursor)
        self.note_btn.setStyleSheet("""
            QPushButton { color: #96add4; font-size: 11px; border: none; background: transparent; text-align: left; }
            QPushButton:hover, QPushButton:focus { color: #cfdef8; }
        """)
        self.note_btn.clicked.connect(self._edit_note)
        self.metadata.addWidget(self.note_btn)
        self.metadata.addStretch()
        self.content.addLayout(self.metadata)
        self.row.addLayout(self.content, 1)
        self.badge = None
        proj = task.get('project')
        if proj:
            bg, fg = get_project_color(proj, project_list)
            self.badge = QLabel('[' + proj + ']')
            self.badge.setTextFormat(Qt.PlainText)
            self.badge.setToolTip(proj)
            self.badge.setStyleSheet(f"QLabel {{ background: {bg}; color: {fg}; border: 1px solid {fg}; border-radius: 6px; padding: 3px 8px; font-size: 11px; font-weight: 600; }}")
            self.row.addWidget(self.badge, 0, Qt.AlignTop)
        self.menu_btn = QPushButton()
        self.menu_btn.setIcon(make_icon('dots'))
        self.menu_btn.setIconSize(QSize(18, 18))
        self.menu_btn.setFixedSize(22, 22)
        self.menu_btn.setToolTip('Görev seçenekleri')
        self.menu_btn.setAccessibleName('Görev seçenekleri')
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        self.menu_btn.setStyleSheet('QPushButton { border: none; border-radius: 6px; background: transparent; } QPushButton:hover, QPushButton:focus { background: #22334e; }')
        self.menu_btn.clicked.connect(self._show_menu)
        self.row.addWidget(self.menu_btn, 0, Qt.AlignTop)

    def fit_to_width(self, width):
        compact = width < 790
        self.row.setContentsMargins(12, 10, 12, 10)
        self.row.setSpacing(12)
        if self.badge:
            self.row.removeWidget(self.badge)
            self.content.removeWidget(self.badge)
            if compact:
                self.content.addWidget(self.badge, 0, Qt.AlignLeft)
            else:
                self.row.insertWidget(2, self.badge, 0, Qt.AlignTop)
            max_badge = max(100, min(300, width - 180 if compact else int(width * .30)))
            self.badge.setMaximumWidth(max_badge)
            self.badge.setText(QFontMetrics(self.badge.font()).elidedText('[' + self.task['project'] + ']', Qt.ElideRight, max_badge - 36))
        self.note_btn.setVisible(width >= 570)
        m = self.row.contentsMargins()
        title_width = width - m.left() - m.right() - 36 - 28 - self.row.spacing() * 2
        if self.badge and not compact:
            title_width -= min(self.badge.sizeHint().width(), self.badge.maximumWidth()) + self.row.spacing()
        title_height = QFontMetrics(self.title_label.font()).boundingRect(QRect(0, 0, max(80, title_width), 10000), Qt.TextWordWrap, self.title_label.text()).height()
        height = title_height + 12 + 24 + m.top() + m.bottom()
        if self.badge and compact:
            height += self.badge.sizeHint().height() + 12
        # QListWidget's item margin consumes four pixels of the size hint.
        # Retain headroom for font rounding so long wrapped titles are never clipped.
        return max(50, height + 4)

    def _edit_title(self):
        dialog = CustomInputDialog('Görevi Düzenle', 'Yeni görev metnini girin:', self)
        dialog.input_field.setText(self.task.get('title', ''))
        if dialog.exec_() == QDialog.Accepted and dialog.get_text():
            self.task_edited.emit(self.task['id'], dialog.get_text())

    def _edit_note(self):
        dialog = CustomInputDialog('Görev Notu', 'Göreve eklemek istediğiniz not:', self)
        dialog.input_field.setText(self.task.get('notes', ''))
        if dialog.exec_() == QDialog.Accepted:
            self.task_noted.emit(self.task['id'], dialog.get_text())

    def _show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        edit = menu.addAction('Görevi düzenle')
        note = menu.addAction('Notu düzenle')
        menu.addSeparator()
        delete = menu.addAction('Görevi sil')
        action = menu.exec_(self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomLeft()))
        if action == edit:
            self._edit_title()
        elif action == note:
            self._edit_note()
        elif action == delete:
            self.task_deleted.emit(self.task['id'])

    def mouseDoubleClickEvent(self, event):
        self._edit_title()


# --- Draggable Header Bar ---
class DraggableHeader(QFrame):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.parent_window.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


# --- Main Application Window ---
class TaskFlowApp(QMainWindow):
    def __init__(self, start_minimized=False, task_manager=None, setup_autostart=True):
        super().__init__()
        self.task_manager = task_manager if task_manager is not None else TaskManager()
        self.current_project = self.task_manager.settings.get('selected_project', 'Tümü')
        self.start_minimized = start_minimized

        self._resizing_edge = None
        self._resize_start_pos = QPoint()
        self._resize_start_geom = QRect()

        # Ensure Windows Autostart is active
        try:
            if setup_autostart and self.task_manager.settings.get('autostart', True):
                autostart.set_autostart(True)
        except Exception:
            pass

        self._setup_window()
        self._setup_tray()
        self._setup_ui()
        self._refresh_project_tabs()
        self._refresh_tasks()
        # Receive pointer events before child widgets so the invisible resize
        # catchment also works when the pointer is over a child at the edge.
        QApplication.instance().installEventFilter(self)

        if not self.start_minimized:
            self.show()
        else:
            self.hide()
            self.tray_icon.showMessage(
                "TaskFlow",
                "Uygulama arka planda sistem tepsisinde başlatıldı.",
                QSystemTrayIcon.Information,
                2000
            )

    def _setup_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.setMouseTracking(True)
        self.setWindowTitle("TaskFlow")
        # Keep the compact startup footprint of the previous TaskFlow release.
        # The existing edge/corner resize handlers remain available for expanding it.
        self.setMinimumSize(340, 460)
        self.resize(440, 640)

        # Prioritize multi-resolution icon.ico for native Windows taskbar & tray scaling
        ico_path = get_resource_path(os.path.join("resources", "icon.ico"))
        png_path = get_resource_path(os.path.join("resources", "icon.png"))
        if os.path.exists(ico_path):
            self.app_icon = QIcon(ico_path)
        elif os.path.exists(png_path):
            self.app_icon = QIcon(png_path)
        else:
            self.app_icon = QIcon()

        self.setWindowIcon(self.app_icon)

        if self.task_manager.settings.get('always_on_top', False):
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        if hasattr(self, 'app_icon') and not self.app_icon.isNull():
            self.tray_icon.setIcon(self.app_icon)
        else:
            self.tray_icon.setIcon(self.windowIcon())

        self.tray_icon.setToolTip("TaskFlow")

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #090d16;
                color: #e2e8f0;
                border: 1px solid #1e2a42;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
            }
        """)

        show_action = QAction("Aç / Gizle", self)
        show_action.triggered.connect(self.toggle_window_visibility)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction("Uygulamayı Kapat", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _setup_ui(self):
        outer = QWidget(self)
        outer.setMouseTracking(True)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        self.setCentralWidget(outer)
        self.app_frame = QFrame(outer)
        self.app_frame.setObjectName('AppFrame')
        self.app_frame.setMouseTracking(True)
        self.app_frame.setStyleSheet("""
            QFrame#AppFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0f192a,stop:.5 #090f1a,stop:1 #0b121e);
                border: 1px solid #354b6c; border-radius: 18px;
            }
            QLabel { background: transparent; border: none; }
        """)
        outer_layout.addWidget(self.app_frame)
        self.app_layout = QVBoxLayout(self.app_frame)
        self.app_layout.setContentsMargins(18, 16, 18, 12)
        self.app_layout.setSpacing(14)
        self.header_bar = DraggableHeader(self)
        self.header_bar.setObjectName('HeaderBar')
        self.header_bar.setStyleSheet('QFrame#HeaderBar { background: transparent; border: none; }')
        self.header_bar.setFixedHeight(56)
        header = QHBoxLayout(self.header_bar)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)
        self.progress_ring = CircularProgressWidget(size=44)
        self.progress_ring.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        header.addWidget(self.progress_ring, 0, Qt.AlignTop)
        brand = QHBoxLayout()
        brand.setSpacing(8)
        self.logo_lbl = QLabel()
        self.logo_lbl.setPixmap(make_icon('logo', size=28).pixmap(28, 28))
        self.logo_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        brand.addWidget(self.logo_lbl, 0, Qt.AlignTop)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_lbl = QLabel('<span style="color:#f5f8ff;">Task</span><span style="color:#3979ff;">Flow</span>')
        self.title_lbl.setStyleSheet('font-size: 19px; font-weight: 800;')
        self.title_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        title_col.addWidget(self.title_lbl)
        self.subtitle_lbl = QLabel('Planla  •  Yap  •  Tamamla')
        self.subtitle_lbl.setStyleSheet('color: #98aed6; font-size: 11px;')
        self.subtitle_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        title_col.addWidget(self.subtitle_lbl)
        brand.addLayout(title_col)
        header.addLayout(brand)
        header.addStretch()
        right = QVBoxLayout()
        right.setSpacing(6)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        for attr, icon, label in [('pin_btn', 'pin', 'Pencereyi her zaman en üstte tut'),
                                  ('hide_btn', 'hide', 'Sistem tepsisine gizle'),
                                  ('close_btn', 'close', 'Gizle (kapat)')]:
            button = QPushButton()
            button.setFixedSize(32, 32)
            button.setIcon(make_icon(icon))
            button.setIconSize(QSize(18, 18))
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(CONTROL_STYLE)
            setattr(self, attr, button)
            actions.addWidget(button)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(self.task_manager.settings.get('always_on_top', False))
        self.pin_btn.clicked.connect(self._toggle_pin)
        self._update_pin_style()
        self.hide_btn.clicked.connect(self.hide_to_tray)
        self.close_btn.clicked.connect(self.hide_to_tray)
        self.close_btn.setStyleSheet(CONTROL_STYLE + 'QPushButton:hover { background: #321b2b; border-color: #b36379; }')
        right.addLayout(actions)
        self.header_motto = QLabel('Daha fazlasını başar')
        self.header_motto.setAlignment(Qt.AlignRight)
        self.header_motto.setStyleSheet('color: #afc4ec; font-family: "Segoe Print"; font-size: 11px; font-style: italic;')
        self.header_motto.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        right.addWidget(self.header_motto)
        header.addLayout(right)
        self.app_layout.addWidget(self.header_bar)
        project_bar = QHBoxLayout()
        project_bar.setSpacing(8)
        self.add_p_btn = QPushButton('Proje Ekle')
        self.add_p_btn.setIcon(make_icon('plus', '#65baff'))
        self.add_p_btn.setIconSize(QSize(18, 18))
        self.add_p_btn.setFixedHeight(38)
        self.add_p_btn.setCursor(Qt.PointingHandCursor)
        self.add_p_btn.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #102d65,stop:1 #211344);
                color: #f4f6ff; border: 1px solid #7254ff; border-radius: 10px;
                padding: 5px 12px; font-size: 12px; font-weight: 700; }
            QPushButton:hover, QPushButton:focus { background: #243367; border-color: #56a7ff; }
            QPushButton:pressed { background: #19244a; }
        """)
        self.add_p_btn.clicked.connect(self._prompt_add_project)
        project_bar.addWidget(self.add_p_btn)
        self.tabs_scroll = DraggableScrollArea()
        self.tabs_container = QWidget()
        self.tabs_container.setStyleSheet('background: transparent;')
        self.project_tabs_layout = QHBoxLayout(self.tabs_container)
        self.project_tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.project_tabs_layout.setSpacing(6)
        self.tabs_scroll.setWidget(self.tabs_container)
        project_bar.addWidget(self.tabs_scroll, 1)
        self.projects_menu_btn = QPushButton()
        self.projects_menu_btn.setIcon(make_icon('more'))
        self.projects_menu_btn.setFixedSize(38, 38)
        self.projects_menu_btn.setCursor(Qt.PointingHandCursor)
        self.projects_menu_btn.setToolTip('Tüm projeler')
        self.projects_menu_btn.setAccessibleName('Tüm projeler')
        self.projects_menu_btn.setStyleSheet(CONTROL_STYLE)
        self.projects_menu_btn.clicked.connect(self._show_projects_overflow)
        project_bar.addWidget(self.projects_menu_btn)
        self.app_layout.addLayout(project_bar)
        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.input_box = QFrame()
        self.input_box.setObjectName('InputBox')
        self.input_box.setFixedHeight(42)
        self.input_box.setStyleSheet('QFrame#InputBox { background: #121d2e; border: 1px solid #354c70; border-radius: 15px; }')
        input_layout = QHBoxLayout(self.input_box)
        input_layout.setContentsMargins(10, 0, 10, 0)
        input_layout.setSpacing(8)
        doc = QLabel()
        doc.setPixmap(make_icon('document', size=18).pixmap(18, 18))
        input_layout.addWidget(doc)
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText('Yeni bir görev yazın... [Enter]')
        self.task_input.setAccessibleName('Yeni görev')
        self.task_input.setStyleSheet('QLineEdit { background: transparent; color: #f3f6ff; border: none; font-size: 13px; selection-background-color: #326ad9; selection-color: #ffffff; }')
        palette = self.task_input.palette()
        palette.setColor(palette.PlaceholderText, QColor('#98acd0'))
        self.task_input.setPalette(palette)
        self.task_input.returnPressed.connect(self._add_task)
        self.task_input.textChanged.connect(lambda text: self.add_btn.setEnabled(bool(text.strip())))
        input_layout.addWidget(self.task_input, 1)
        input_row.addWidget(self.input_box, 1)
        self.add_btn = QPushButton()
        self.add_btn.setIcon(make_icon('plus', '#ffffff', 32))
        self.add_btn.setIconSize(QSize(22, 22))
        self.add_btn.setFixedSize(42, 42)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setToolTip('Görev ekle')
        self.add_btn.setAccessibleName('Görev ekle')
        self.add_btn.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #239bff,stop:1 #5726f5);
                border: 1px solid #6388ff; border-radius: 15px; }
            QPushButton:hover, QPushButton:focus { border: 2px solid #a9caff; }
            QPushButton:pressed { background: #345bea; }
            QPushButton:disabled { border-color: #5c7edb; }
        """)
        self.add_btn.clicked.connect(self._add_task)
        self.add_btn.setEnabled(False)
        input_row.addWidget(self.add_btn)
        self.app_layout.addLayout(input_row)
        self.task_list_widget = QListWidget()
        self.task_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.task_list_widget.setSelectionMode(QListWidget.NoSelection)
        self.task_list_widget.setSpacing(5)
        self.task_list_widget.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { background: transparent; border: none; padding: 0; margin-bottom: 4px; }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
            QScrollBar::handle:vertical { background: #344b6a; border-radius: 3px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #4c91ed; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        self.empty_lbl = QLabel('İlk adımı at.\nYukarıdan bir görev ekleyerek başla.', self.task_list_widget.viewport())
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        self.empty_lbl.setStyleSheet('color: #98acd0; font-size: 13px;')
        self.empty_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.app_layout.addWidget(self.task_list_widget, 1)
        self.footer = QFrame()
        self.footer.setObjectName('Footer')
        self.footer.setStyleSheet('QFrame#Footer { border: none; border-top: 1px solid #203047; background: transparent; }')
        footer = QHBoxLayout(self.footer)
        footer.setContentsMargins(6, 4, 0, 0)
        footer.setSpacing(12)
        stats_icon = QLabel()
        stats_icon.setPixmap(make_icon('stats', size=24).pixmap(24, 24))
        footer.addWidget(stats_icon)
        self.stats_lbl = QLabel('0 aktif görev')
        self.stats_lbl.setStyleSheet('color: #dce9ff; font-size: 14px; font-weight: 700;')
        footer.addWidget(self.stats_lbl)
        sep = QFrame()
        sep.setFixedSize(1, 16)
        sep.setStyleSheet('background: #314668; border: none;')
        footer.addWidget(sep)
        self.clear_btn = QPushButton('Tamamlananları Temizle')
        self.clear_btn.setIcon(make_icon('check'))
        self.clear_btn.setIconSize(QSize(18, 18))
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setStyleSheet('QPushButton { background: transparent; color: #b3c9ee; border: none; border-radius: 6px; padding: 4px 8px; font-size: 11px; } QPushButton:hover, QPushButton:focus { background: #202e46; color: #ffffff; } QPushButton:disabled { color: #879aba; }')
        self.clear_btn.clicked.connect(self._confirm_clear_completed)
        footer.addWidget(self.clear_btn)
        footer.addStretch()
        self.footer_motto = QLabel('Küçük adımlar, büyük sonuçlar.')
        self.footer_motto.setStyleSheet('color: #9fb7df; font-family: "Segoe Print"; font-size: 11px; font-style: italic;')
        footer.addWidget(self.footer_motto)
        sparkle = QLabel()
        sparkle.setPixmap(make_icon('sparkle', size=24).pixmap(24, 24))
        footer.addWidget(sparkle)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(14, 14)
        self.size_grip.setStyleSheet('background: transparent;')
        footer.addWidget(self.size_grip, 0, Qt.AlignBottom)
        self.app_layout.addWidget(self.footer)

    def _show_projects_overflow(self):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        for project in ['Tümü'] + self.task_manager.projects:
            action = menu.addAction(project)
            action.setCheckable(True)
            action.setChecked(project == self.current_project)
            action.triggered.connect(lambda checked, name=project: self._select_project(name))
        menu.exec_(self.projects_menu_btn.mapToGlobal(self.projects_menu_btn.rect().bottomLeft()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'app_layout'):
            compact = self.width() < 850
            self.app_layout.setContentsMargins(18, 16, 18, 12)
            self.title_lbl.setStyleSheet('font-size: 19px; font-weight: 800;')
            self.header_motto.setVisible(not compact)
            self.footer_motto.setVisible(self.width() >= 1000)
            QTimer.singleShot(0, self._resize_task_cards)

    def _resize_task_cards(self):
        viewport = self.task_list_widget.viewport()
        self.empty_lbl.setGeometry(viewport.rect())
        width = max(100, viewport.width() - self.task_list_widget.spacing() * 2 - 2)
        for index in range(self.task_list_widget.count()):
            item = self.task_list_widget.item(index)
            widget = self.task_list_widget.itemWidget(item)
            if widget:
                item.setSizeHint(QSize(width, widget.fit_to_width(width)))

    # --- Edge and Corner Window Resizing Logic ---
    def eventFilter(self, obj, event):
        """Make the invisible edge catchment work over all child widgets."""
        mouse_types = (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease)
        if event.type() not in mouse_types or not self.isVisible():
            return super().eventFilter(obj, event)

        try:
            global_pos = event.globalPos()
        except AttributeError:
            return super().eventFilter(obj, event)

        pos = self.mapFromGlobal(global_pos)
        if not self.rect().contains(pos):
            return super().eventFilter(obj, event)

        edge = self._get_resize_edge(pos)
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            if edge != (False, False, False, False):
                self._resizing_edge = edge
                self._resize_start_pos = global_pos
                self._resize_start_geom = self.geometry()
                event.accept()
                return True
        elif event.type() == QEvent.MouseMove:
            if self._resizing_edge:
                self.mouseMoveEvent(event)
                return True
            self._update_cursor_for_edge(edge)
        elif event.type() == QEvent.MouseButtonRelease and self._resizing_edge:
            self.mouseReleaseEvent(event)
            return True

        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edge = self._get_resize_edge(event.pos())
            if edge != (False, False, False, False):
                self._resizing_edge = edge
                self._resize_start_pos = event.globalPos()
                self._resize_start_geom = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing_edge:
            dx = event.globalX() - self._resize_start_pos.x()
            dy = event.globalY() - self._resize_start_pos.y()
            new_geom = QRect(self._resize_start_geom)

            left, right, top, bottom = self._resizing_edge
            min_w = self.minimumWidth()
            min_h = self.minimumHeight()

            if left:
                new_left = new_geom.left() + dx
                if new_geom.right() - new_left >= min_w:
                    new_geom.setLeft(new_left)
            if right:
                new_right = new_geom.right() + dx
                if new_right - new_geom.left() >= min_w:
                    new_geom.setRight(new_right)
            if top:
                new_top = new_geom.top() + dy
                if new_geom.bottom() - new_top >= min_h:
                    new_geom.setTop(new_top)
            if bottom:
                new_bottom = new_geom.bottom() + dy
                if new_bottom - new_geom.top() >= min_h:
                    new_geom.setBottom(new_bottom)

            self.setGeometry(new_geom)
            event.accept()
            return
        else:
            edge = self._get_resize_edge(event.pos())
            self._update_cursor_for_edge(edge)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._resizing_edge = None
        self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def _get_resize_edge(self, pos):
        w = self.width()
        h = self.height()
        m = BORDER_MARGIN

        left = pos.x() <= m
        right = pos.x() >= w - m
        top = pos.y() <= m
        bottom = pos.y() >= h - m

        return (left, right, top, bottom)

    def _update_cursor_for_edge(self, edge):
        left, right, top, bottom = edge
        if (left and top) or (right and bottom):
            self.setCursor(Qt.SizeFDiagCursor)
        elif (right and top) or (left and bottom):
            self.setCursor(Qt.SizeBDiagCursor)
        elif left or right:
            self.setCursor(Qt.SizeHorCursor)
        elif top or bottom:
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def _refresh_project_tabs(self):
        while self.project_tabs_layout.count():
            item = self.project_tabs_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # [Tümü] tab
        all_btn = ScrollableTabButton("Tümü", self.tabs_scroll)
        all_btn.setCheckable(True)
        all_btn.setChecked(self.current_project == "Tümü")
        all_btn.setCursor(Qt.PointingHandCursor)
        self._apply_all_tab_style(all_btn, self.current_project == "Tümü")
        all_btn.clicked.connect(lambda: self._select_project("Tümü"))
        self.project_tabs_layout.addWidget(all_btn)

        # User defined Project tabs with distinct color bullet
        for idx, proj in enumerate(self.task_manager.projects):
            bg_col, fg_col = get_project_color(proj, self.task_manager.projects)
            p_btn = ScrollableTabButton(proj, self.tabs_scroll)
            p_btn.setIcon(make_icon('dot', fg_col))
            p_btn.setIconSize(QSize(16, 16))
            p_btn.setCheckable(True)
            is_active = (self.current_project == proj)
            p_btn.setChecked(is_active)
            p_btn.setCursor(Qt.PointingHandCursor)
            self._apply_project_tab_style(p_btn, is_active, bg_col, fg_col)
            p_btn.clicked.connect(lambda checked, p=proj: self._select_project(p))

            p_btn.setContextMenuPolicy(Qt.CustomContextMenu)
            p_btn.customContextMenuRequested.connect(lambda pos, p=proj: self._show_project_menu(p))
            self.project_tabs_layout.addWidget(p_btn)

        self.project_tabs_layout.addStretch()

    def _apply_all_tab_style(self, btn, is_active):
        btn.setIcon(make_icon('grid', '#72bdff'))
        btn.setIconSize(QSize(18, 18))
        self._apply_project_tab_style(btn, is_active, '#102849', '#38abff')

    def _apply_project_tab_style(self, btn, is_active, bg_col, fg_col):
        btn.setFixedHeight(38)
        btn.setToolTip(btn.text())
        btn.setStyleSheet(f"""
            QPushButton {{ background: {bg_col if is_active else '#0f1929'};
                color: #d4e2ff; border: 1px solid {fg_col if is_active else '#253751'};
                border-radius: 9px; padding: 5px 12px; font-size: 12px; font-weight: {700 if is_active else 600}; }}
            QPushButton:hover, QPushButton:focus {{ background: {bg_col}; border-color: {fg_col}; }}
            QPushButton:pressed {{ background: #20304a; }}
        """)

    def _select_project(self, proj_name):
        self.current_project = proj_name
        self.task_manager.settings['selected_project'] = proj_name
        self.task_manager.save()
        self._refresh_project_tabs()
        self._refresh_tasks()

    def _prompt_add_project(self):
        dialog = CustomInputDialog("Yeni Proje", "Yeni proje / kategori adı giriniz:", self)
        if dialog.exec_() == QDialog.Accepted:
            proj_name = dialog.get_text()
            if proj_name:
                if self.task_manager.add_project(proj_name):
                    self._select_project(proj_name)
                else:
                    msg_box = CustomConfirmDialog("Bilgi", "Bu proje adı zaten mevcut!", confirm_text="Tamam", is_destructive=False, parent=self)
                    msg_box.exec_()

    def _show_project_menu(self, proj_name):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #090d16;
                color: #e2e8f0;
                border: 1px solid #2563eb;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #ef4444;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        del_act = menu.addAction(f"'{proj_name}' Projesini Sil")
        action = menu.exec_(self.cursor().pos())
        if action == del_act:
            dialog = CustomConfirmDialog(
                "Projeyi Sil",
                f"'{proj_name}' projesini silmek istediğinize emin misiniz?\nİçindeki görevler genel listeye aktarılacaktır.",
                confirm_text="Sil",
                parent=self
            )
            if dialog.exec_() == QDialog.Accepted:
                self.task_manager.delete_project(proj_name)
                self._select_project("Tümü")

    def _refresh_tasks(self):
        self.task_list_widget.clear()
        tasks = self.task_manager.get_tasks(self.current_project)

        for task in tasks:
            item = QListWidgetItem()
            item_widget = TaskItemWidget(task, self.task_manager.projects)
            item_widget.task_toggled.connect(self._on_task_toggled)
            item_widget.task_deleted.connect(self._on_task_deleted)
            item_widget.task_edited.connect(self._on_task_edited)
            item_widget.task_noted.connect(self._on_task_noted)

            width = max(100, self.task_list_widget.viewport().width() - 18)
            item.setSizeHint(QSize(width, item_widget.fit_to_width(width)))
            self.task_list_widget.addItem(item)
            self.task_list_widget.setItemWidget(item, item_widget)

        total, completed = self.task_manager.get_stats(self.current_project)
        active = total - completed

        percent = int((completed / total) * 100) if total > 0 else 0
        self.progress_ring.set_percentage(percent)

        self.stats_lbl.setText(f'{active} aktif görev')
        self.clear_btn.setEnabled(completed > 0)
        self.empty_lbl.setVisible(not tasks)
        QTimer.singleShot(0, self._resize_task_cards)

        all_total, all_completed = self.task_manager.get_stats("Tümü")
        all_active = all_total - all_completed
        self.tray_icon.setToolTip(f"TaskFlow ({all_active} görev bekliyor)")

    def _add_task(self):
        title = self.task_input.text().strip()
        if not title:
            return

        proj = self.current_project if self.current_project != "Tümü" else None

        self.task_manager.add_task(title, proj)
        self.task_input.clear()
        self._refresh_tasks()

    def _on_task_toggled(self, task_id):
        self.task_manager.toggle_task(task_id)
        self._refresh_tasks()

    def _on_task_deleted(self, task_id):
        self.task_manager.delete_task(task_id)
        self._refresh_tasks()

    def _on_task_edited(self, task_id, new_title):
        self.task_manager.edit_task(task_id, new_title)
        self._refresh_tasks()

    def _confirm_clear_completed(self):
        total, completed = self.task_manager.get_stats(self.current_project)
        if completed == 0:
            return

        dialog = CustomConfirmDialog(
            "Tamamlananları Temizle",
            f"Tamamlanmış olan {completed} görevi silmek istediğinize emin misiniz?",
            confirm_text="Temizle",
            is_destructive=True,
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.task_manager.clear_completed(self.current_project)
            self._refresh_tasks()

    def _toggle_pin(self):
        is_checked = self.pin_btn.isChecked()
        self.task_manager.settings['always_on_top'] = is_checked
        self.task_manager.save()

        flags = Qt.FramelessWindowHint | Qt.Window
        if is_checked:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self._update_pin_style()
        self.show()

    def _update_pin_style(self):
        self.pin_btn.setStyleSheet(CONTROL_STYLE)
        self.pin_btn.setIcon(make_icon('pin', '#6dbaff' if self.pin_btn.isChecked() else '#b3c6e9'))

    def _on_task_noted(self, task_id, note):
        self.task_manager.edit_notes(task_id, note)
        self._refresh_tasks()

    def hide_to_tray(self):
        self.hide()

    def toggle_window_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.toggle_window_visibility()

    def closeEvent(self, event):
        event.ignore()
        self.hide_to_tray()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide_to_tray()
        else:
            super().keyPressEvent(event)

    def _quit_app(self):
        self.tray_icon.hide()
        QApplication.quit()
