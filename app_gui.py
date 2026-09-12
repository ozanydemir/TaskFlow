import os
import sys
from PyQt5.QtCore import Qt, QSize, QRectF, QRect, pyqtSignal, QPoint
from PyQt5.QtGui import QIcon, QFont, QColor, QPainter, QPen, QCursor, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QCheckBox, QSystemTrayIcon, QMenu, QAction, QDialog,
    QFrame, QSizePolicy, QSizeGrip, QScrollArea
)

import autostart
from task_manager import TaskManager

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

white_check_path = get_resource_path(os.path.join("resources", "check_mark_white.png")).replace("\\", "/")

BORDER_MARGIN = 8

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

        pen_width = 3.6
        margin = pen_width / 2.0 + 1.2
        rect = QRectF(margin, margin, self.widget_size - 2*margin, self.widget_size - 2*margin)

        # Background track
        bg_pen = QPen(QColor(19, 27, 46), pen_width)
        bg_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Royal blue arc
        if self.percentage > 0:
            fg_pen = QPen(QColor(41, 121, 255), pen_width)
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
class TaskItemWidget(QWidget):
    task_toggled = pyqtSignal(str)
    task_deleted = pyqtSignal(str)
    task_edited = pyqtSignal(str, str)

    def __init__(self, task, project_list, parent=None):
        super().__init__(parent)
        self.task = task
        self.project_list = project_list
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.task.get('completed', False))
        self.checkbox.setCursor(Qt.PointingHandCursor)
        self.checkbox.stateChanged.connect(lambda: self.task_toggled.emit(self.task['id']))
        self.checkbox.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border: 2px solid #23324d;
                border-radius: 6px;
                background-color: #0c121e;
            }}
            QCheckBox::indicator:hover {{
                border-color: #3b82f6;
            }}
            QCheckBox::indicator:checked {{
                background-color: #2563eb;
                border-color: #3b82f6;
                image: url({white_check_path});
            }}
        """)
        layout.addWidget(self.checkbox)

        # Task title
        self.title_label = QLabel(self.task.get('title', ''))
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.title_label.setWordWrap(True)
        self._update_text_style()
        layout.addWidget(self.title_label)

        # Project Badge with distinct assigned color
        proj = self.task.get('project')
        if proj:
            bg_col, fg_col = get_project_color(proj, self.project_list)
            self.badge = QLabel(f" [{proj}] ")
            self.badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_col};
                    color: {fg_col};
                    border: 1px solid {fg_col};
                    border-radius: 6px;
                    padding: 3px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }}
            """)
            layout.addWidget(self.badge)

        # Delete button
        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedSize(22, 22)
        self.del_btn.setCursor(Qt.PointingHandCursor)
        self.del_btn.setToolTip("Görevi Sil")
        self.del_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #5c6f8f;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38151c;
                color: #ef4444;
            }
        """)
        self.del_btn.clicked.connect(lambda: self.task_deleted.emit(self.task['id']))
        layout.addWidget(self.del_btn)

    def _update_text_style(self):
        font = QFont("Segoe UI", 10)
        if self.task.get('completed'):
            font.setStrikeOut(True)
            self.title_label.setFont(font)
            self.title_label.setStyleSheet("color: #475569; border: none;")
        else:
            font.setStrikeOut(False)
            self.title_label.setFont(font)
            self.title_label.setStyleSheet("color: #e2e8f0; border: none;")

    def mouseDoubleClickEvent(self, event):
        dialog = CustomInputDialog("Görevi Düzenle", "Yeni görev metnini girin:", self)
        dialog.input_field.setText(self.task.get('title', ''))
        if dialog.exec_() == QDialog.Accepted and dialog.get_text():
            self.task_edited.emit(self.task['id'], dialog.get_text())


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
class FlowListApp(QMainWindow):
    def __init__(self, start_minimized=False):
        super().__init__()
        self.task_manager = TaskManager()
        self.current_project = self.task_manager.settings.get('selected_project', 'Tümü')
        self.start_minimized = start_minimized

        self._resizing_edge = None
        self._resize_start_pos = QPoint()
        self._resize_start_geom = QRect()

        # Ensure Windows Autostart is active
        try:
            autostart.set_autostart(True)
        except Exception:
            pass

        self._setup_window()
        self._setup_tray()
        self._setup_ui()
        self._refresh_project_tabs()
        self._refresh_tasks()

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
        outer_central = QWidget(self)
        outer_central.setMouseTracking(True)
        outer_layout = QVBoxLayout(outer_central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(outer_central)

        # Outer App Card
        self.app_frame = QFrame(outer_central)
        self.app_frame.setObjectName("AppFrame")
        self.app_frame.setMouseTracking(True)
        self.app_frame.setStyleSheet("""
            QFrame#AppFrame {
                background-color: #090d16;
                border: 1px solid #141c2d;
                border-radius: 18px;
            }
        """)
        outer_layout.addWidget(self.app_frame)

        app_layout = QVBoxLayout(self.app_frame)
        app_layout.setContentsMargins(18, 16, 18, 12)
        app_layout.setSpacing(14)

        # 1. Header Bar (Full Draggable Header)
        self.header_bar = DraggableHeader(self)
        self.header_bar.setObjectName("HeaderBar")
        self.header_bar.setStyleSheet("QFrame#HeaderBar { background: transparent; border: none; }")
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        # Circular progress ring
        self.progress_ring = CircularProgressWidget(size=44)
        self.progress_ring.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        header_layout.addWidget(self.progress_ring)

        # Title & Subtitle
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.setContentsMargins(0, 2, 0, 2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.setContentsMargins(0, 0, 0, 0)

        # Concept 3 High-Fidelity Logo Icon
        logo_lbl = QLabel()
        logo_path = get_resource_path(os.path.join("resources", "app_logo.png"))
        if os.path.exists(logo_path):
            logo_pix = QPixmap(logo_path).scaled(84, 84, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_pix.setDevicePixelRatio(3.0)
            logo_lbl.setPixmap(logo_pix)
            logo_lbl.setFixedSize(28, 28)
        logo_lbl.setStyleSheet("border: none; background: transparent;")
        logo_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        title_row.addWidget(logo_lbl)

        title_lbl = QLabel('<span style="color:#ffffff; font-size:19px; font-weight:800; letter-spacing: -0.3px;">Task</span><span style="color:#3b82f6; font-size:19px; font-weight:800; letter-spacing: -0.3px;">Flow</span>')
        title_lbl.setStyleSheet("border: none;")
        title_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        title_row.addWidget(title_lbl)
        title_row.addStretch()

        title_col.addLayout(title_row)

        sub_lbl = QLabel("Planla  •  Yap  •  Tamamla")
        sub_lbl.setStyleSheet("color: #5c6f8f; font-size: 11px; font-weight: 500; border: none;")
        sub_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        title_col.addWidget(sub_lbl)

        header_layout.addLayout(title_col)
        header_layout.addStretch()

        # Right Action Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(32, 32)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(self.task_manager.settings.get('always_on_top', False))
        self.pin_btn.setToolTip("Pencereyi Her Zaman En Üstte Tut")
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.clicked.connect(self._toggle_pin)
        self._update_pin_style()
        btn_box.addWidget(self.pin_btn)

        self.hide_btn = QPushButton("—")
        self.hide_btn.setFixedSize(32, 32)
        self.hide_btn.setToolTip("Sistem Tepsisine Gizle")
        self.hide_btn.setCursor(Qt.PointingHandCursor)
        self.hide_btn.setStyleSheet("""
            QPushButton {
                background-color: #101726;
                color: #71829e;
                border: 1px solid #1a253a;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #162035;
                color: #3b82f6;
                border-color: #3b82f6;
            }
        """)
        self.hide_btn.clicked.connect(self.hide_to_tray)
        btn_box.addWidget(self.hide_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setToolTip("Gizle (Kapat)")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #101726;
                color: #71829e;
                border: 1px solid #1a253a;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38151c;
                color: #ef4444;
                border-color: #ef4444;
            }
        """)
        self.close_btn.clicked.connect(self.hide_to_tray)
        btn_box.addWidget(self.close_btn)

        header_layout.addLayout(btn_box)
        app_layout.addWidget(self.header_bar)

        # 2. Project Bar Container: Fixed '+ Proje Ekle' Button on the Left, Draggable Tabs Scroll on the Right!
        project_bar_container = QFrame()
        project_bar_container.setStyleSheet("background: transparent; border: none;")
        project_bar_layout = QHBoxLayout(project_bar_container)
        project_bar_layout.setContentsMargins(0, 0, 0, 0)
        project_bar_layout.setSpacing(8)

        # FIXED '+ Proje Ekle' button on the FAR LEFT (never scrolls away!)
        self.add_p_btn = QPushButton("+ Proje Ekle")
        self.add_p_btn.setCursor(Qt.PointingHandCursor)
        self.add_p_btn.setToolTip("Yeni Bir Proje / Kategori Ekle")
        self.add_p_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e1526;
                color: #38bdf8;
                border: 1px dashed #2563eb;
                border-radius: 14px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16223b;
                color: #ffffff;
                border-color: #38bdf8;
            }
        """)
        self.add_p_btn.clicked.connect(self._prompt_add_project)
        project_bar_layout.addWidget(self.add_p_btn)

        # Draggable Scroll Area for [Tümü] and Project Tabs
        self.tabs_scroll = DraggableScrollArea()
        self.tabs_container = QWidget()
        self.tabs_container.setStyleSheet("background: transparent;")
        self.project_tabs_layout = QHBoxLayout(self.tabs_container)
        self.project_tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.project_tabs_layout.setSpacing(6)
        self.tabs_scroll.setWidget(self.tabs_container)
        project_bar_layout.addWidget(self.tabs_scroll, 1)

        app_layout.addWidget(project_bar_container)

        # 3. Input Section (Pencil Icon Inside + Gradient '+' Button)
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        input_box = QFrame()
        input_box.setFixedHeight(42)
        input_box.setStyleSheet("""
            QFrame {
                background-color: #0e1422;
                border: 1px solid #182338;
                border-radius: 12px;
            }
        """)
        box_layout = QHBoxLayout(input_box)
        box_layout.setContentsMargins(10, 0, 10, 0)
        box_layout.setSpacing(8)

        pencil_icon = QLabel("✏️")
        pencil_icon.setStyleSheet("border: none; font-size: 13px; color: #5c6f8f;")
        box_layout.addWidget(pencil_icon)

        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Yeni bir görev yazın... [Enter]")
        self.task_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                color: #ffffff;
                border: none;
                font-size: 13px;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
        """)
        self.task_input.returnPressed.connect(self._add_task)
        box_layout.addWidget(self.task_input, 1)

        input_row.addWidget(input_box, 1)

        # Gradient '+' Add Button
        self.add_btn = QPushButton("+")
        self.add_btn.setFixedSize(42, 42)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setToolTip("Görev Ekle")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3b82f6, stop:1 #8b5cf6);
                color: #ffffff;
                border: none;
                border-radius: 12px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #60a5fa, stop:1 #a855f7);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:1 #7c3aed);
            }
        """)
        self.add_btn.clicked.connect(self._add_task)
        input_row.addWidget(self.add_btn)

        app_layout.addLayout(input_row)

        # 4. Task List Widget
        self.task_list_widget = QListWidget()
        self.task_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.task_list_widget.setSpacing(5)
        self.task_list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background-color: #0e1422;
                border: 1px solid #182338;
                border-radius: 12px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #121a2c;
                border-color: #23334e;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 5px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #182338;
                min-height: 20px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3b82f6;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        app_layout.addWidget(self.task_list_widget, 1)

        # 5. Footer Status Bar
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(6, 4, 0, 0)
        footer_row.setSpacing(12)

        self.stats_lbl = QLabel('0 aktif görev')
        self.stats_lbl.setStyleSheet("border: none;")
        footer_row.addWidget(self.stats_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedHeight(16)
        sep.setStyleSheet("color: #1e293b; background-color: #1e293b; border: none;")
        footer_row.addWidget(sep)

        self.clear_btn = QPushButton("🧹 Tamamlananları Temizle")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8b9bb4;
                border: none;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                color: #ef4444;
                background-color: #26141a;
            }
        """)
        self.clear_btn.clicked.connect(self._confirm_clear_completed)
        footer_row.addWidget(self.clear_btn)

        footer_row.addStretch()

        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(14, 14)
        self.size_grip.setStyleSheet("background: transparent;")
        footer_row.addWidget(self.size_grip, 0, Qt.AlignBottom | Qt.AlignRight)

        app_layout.addLayout(footer_row)

    # --- Edge and Corner Window Resizing Logic ---
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
            p_btn = ScrollableTabButton(f"● {proj}", self.tabs_scroll)
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
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: none;
                    border-radius: 14px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 700;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0f1523;
                    color: #71829e;
                    border: 1px solid #1a2438;
                    border-radius: 14px;
                    padding: 5px 12px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #162035;
                    color: #93c5fd;
                    border-color: #2563eb;
                }
            """)

    def _apply_project_tab_style(self, btn, is_active, bg_col, fg_col):
        if is_active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {fg_col};
                    color: #090d16;
                    border: 1px solid {fg_col};
                    border-radius: 14px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 800;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #0f1523;
                    color: {fg_col};
                    border: 1px solid #1a2438;
                    border-radius: 14px;
                    padding: 5px 12px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: #162035;
                    border-color: {fg_col};
                }}
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
            item = QListWidgetItem(self.task_list_widget)
            item_widget = TaskItemWidget(task, self.task_manager.projects)
            item_widget.task_toggled.connect(self._on_task_toggled)
            item_widget.task_deleted.connect(self._on_task_deleted)
            item_widget.task_edited.connect(self._on_task_edited)

            size = item_widget.sizeHint()
            item.setSizeHint(QSize(size.width(), max(50, size.height())))
            self.task_list_widget.addItem(item)
            self.task_list_widget.setItemWidget(item, item_widget)

        total, completed = self.task_manager.get_stats(self.current_project)
        active = total - completed

        percent = int((completed / total) * 100) if total > 0 else 0
        self.progress_ring.set_percentage(percent)

        self.stats_lbl.setText(f'<span style="color:#3b82f6; font-size:14px; font-weight:800;">{active}</span> <span style="color:#64748b; font-size:12px; font-weight:500;">aktif görev</span>')

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
        is_checked = self.pin_btn.isChecked()
        if is_checked:
            self.pin_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: 1px solid #3b82f6;
                    border-radius: 8px;
                    font-size: 13px;
                    font-weight: bold;
                }
            """)
        else:
            self.pin_btn.setStyleSheet("""
                QPushButton {
                    background-color: #101726;
                    color: #ef4444;
                    border: 1px solid #1a253a;
                    border-radius: 8px;
                    font-size: 13px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #162035;
                    border-color: #ef4444;
                }
            """)

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