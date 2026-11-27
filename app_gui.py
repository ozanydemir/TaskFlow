import copy
import json
import os
import sys
import sqlite3
import threading
from PyQt5.QtCore import Qt, QObject, QSize, QRectF, QRect, QEvent, pyqtSignal, QPoint, QTimer
from PyQt5.QtGui import QIcon, QFont, QColor, QPainter, QPen, QCursor, QPixmap, QFontMetrics, QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QCheckBox, QSystemTrayIcon, QMenu, QAction, QDialog,
    QFrame, QSizePolicy, QScrollArea, QFileDialog, QTextEdit, QShortcut
)

import autostart
import cloud_sync
from supabase_sync import LinkCallback, SupabaseClient
from task_manager import TaskManager
from taskflow_agent import agent_prompt
from taskflow_visuals import make_icon, CONTROL_STYLE, MENU_STYLE, DIALOG_STYLE, DARK_SCROLLBAR_STYLE
from datetime import datetime


def _wrap_unbroken(text, limit=22):
    """Insert zero-width break points inside extra-long unbroken tokens so QLabel never clips."""
    if not text or len(text) <= limit:
        return text
    parts = []
    run = 0
    for ch in text:
        if ch.isspace() or ch in '/\\-_.,;:!?()[]{}':
            run = 0
            parts.append(ch)
        else:
            if run >= limit:
                parts.append('\u200b')
                run = 0
            parts.append(ch)
            run += 1
    return ''.join(parts)

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
            self.setDown(False)
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
        self._drag_pos = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        self.card = QFrame(self)
        self.card.setObjectName('DialogCard')
        self.card.setStyleSheet("""
            QFrame#DialogCard {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0f192a,stop:1 #090f1a);
                border: 1px solid #354c70;
                border-radius: 14px;
            }
            QLabel { background: transparent; border: none; }
        """)
        outer_layout.addWidget(self.card)

        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(18, 16, 18, 16)
        self.card_layout.setSpacing(12)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("color: #f5f8ff; font-size: 15px; font-weight: 700; border: none;")
        self.card_layout.addWidget(self.title_lbl)
        self.setStyleSheet(DIALOG_STYLE)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            if child is None or child in (self.card, self.title_lbl):
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class ProjectConnectionDialog(ModernDialog):
    def __init__(self, project, binding, parent=None):
        super().__init__('Agent bağlantısı · ' + project, parent)
        self.project = project
        self.has_binding = bool(binding)
        self.resize(420, 360)
        info = QLabel('Görevleri biriktirin; agentı istediğiniz zaman başlatın.\nBu bağlantı kendiliğinden agent çalıştırmaz.')
        info.setStyleSheet('color: #96add4; font-size: 12px; border: none;')
        info.setWordWrap(True)
        self.card_layout.addWidget(info)
        self.repo_field = self._folder_field('Projenin bilgisayarındaki klasörü', binding.get('repo_path', ''))
        self.brain_field = self._folder_field('OZI Brain proje klasörü (isteğe bağlı)', binding.get('brain_dir', ''))
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet('color: #fbbf24; border: none; font-size: 12px;')
        self.card_layout.addWidget(self.error_label)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.unbind_btn = QPushButton('Bağlantıyı kaldır')
        self.unbind_btn.setCursor(Qt.PointingHandCursor)
        self.unbind_btn.clicked.connect(self._unbind)
        self.unbind_btn.setVisible(self.has_binding)
        buttons.addWidget(self.unbind_btn)
        buttons.addStretch()
        cancel = QPushButton('Vazgeç')
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        save = QPushButton('Bağlantıyı kaydet')
        save.setProperty('role', 'primary')
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        self.card_layout.addLayout(buttons)

    def _folder_field(self, label, value):
        title = QLabel(label)
        title.setStyleSheet('color: #d4e2ff; border: none; font-size: 12px;')
        self.card_layout.addWidget(title)
        row = QHBoxLayout()
        field = QLineEdit(value)
        field.setAccessibleName(label)
        choose = QPushButton('Seç')
        choose.setCursor(Qt.PointingHandCursor)
        def browse():
            folder = QFileDialog.getExistingDirectory(self, label, field.text())
            if folder:
                field.setText(folder)
        choose.clicked.connect(browse)
        row.addWidget(field, 1)
        row.addWidget(choose)
        self.card_layout.addLayout(row)
        return field

    def _unbind(self):
        try:
            self.parent().task_manager.unbind_project(self.project)
        except (ValueError, OSError, sqlite3.Error) as exc:
            self.error_label.setText(str(exc))
            return
        super().accept()

    def accept(self):
        try:
            self.parent().task_manager.bind_project(self.project,
                                                    self.repo_field.text().strip(), self.brain_field.text().strip())
        except (ValueError, OSError, sqlite3.Error) as exc:
            self.error_label.setText(str(exc))
            return
        super().accept()


class _Relay(QObject):
    """Carries results from worker threads to the GUI thread."""
    message = pyqtSignal(str, str)
    status = pyqtSignal(dict)


class CloudSyncDialog(ModernDialog):
    """Supabase address, sign-in by email link, and switching sync on or off on this computer."""

    def __init__(self, window):
        super().__init__('Bulut senkronu', window)
        self.window = window
        self.callback = None
        self.resize(420, 430)
        config = cloud_sync.get_config(window.task_manager) or {}
        info = QLabel('Görevler ve notlar aynı hesapla giriş yapılan bilgisayarlarda aynı görünür. '
                      'Agent bağlantıları ve pencere ayarları bu bilgisayarda kalır.')
        info.setStyleSheet('color: #96add4; font-size: 12px; border: none;')
        info.setWordWrap(True)
        self.card_layout.addWidget(info)
        self.url_field = self._field('Supabase proje adresi', config.get('url', ''), 'https://<proje>.supabase.co')
        self.key_field = self._field('Publishable anahtar', config.get('key', ''), 'sb_publishable_...')
        self.email_field = self._field('E-posta', config.get('email', ''), 'ad@ornek.com')
        self.state_label = QLabel()
        self.state_label.setWordWrap(True)
        self.state_label.setStyleSheet('color: #fbbf24; border: none; font-size: 12px;')
        state_row = QHBoxLayout()
        state_row.setSpacing(8)
        state_row.addWidget(self.state_label, 1)
        self.reauth_btn = QPushButton('Yeniden giriş')
        self.reauth_btn.setCursor(Qt.PointingHandCursor)
        self.reauth_btn.clicked.connect(self._send_link)
        self.reauth_btn.hide()
        state_row.addWidget(self.reauth_btn, 0, Qt.AlignVCenter)
        self.card_layout.addLayout(state_row)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.off_btn = QPushButton('Senkronu kapat')
        self.off_btn.setCursor(Qt.PointingHandCursor)
        self.off_btn.clicked.connect(self._turn_off)
        self.close_btn = QPushButton('Kapat')
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.reject)
        self.sync_now_btn = QPushButton('Şimdi eşitle')
        self.sync_now_btn.setProperty('role', 'primary')
        self.sync_now_btn.setCursor(Qt.PointingHandCursor)
        self.sync_now_btn.clicked.connect(self._sync_now)
        self.sync_now_btn.hide()
        self.sign_btn = QPushButton('Giriş bağlantısı gönder')
        self.sign_btn.setProperty('role', 'primary')
        self.sign_btn.setCursor(Qt.PointingHandCursor)
        self.sign_btn.clicked.connect(self._send_link)
        buttons.addWidget(self.off_btn)
        buttons.addStretch()
        buttons.addWidget(self.close_btn)
        buttons.addWidget(self.sign_btn)
        buttons.addWidget(self.sync_now_btn)
        self.card_layout.addLayout(buttons)
        self.relay = _Relay(self)
        self.relay.message.connect(self._on_message)
        enabled = bool(config.get('enabled')) and window.cloud.signed_in(config)
        self.off_btn.setVisible(bool(config.get('enabled')))
        if enabled:
            self.state_label.setStyleSheet('color: #6ee7b7; border: none; font-size: 12px;')
            self.state_label.setText('Bağlı: {}. {}'.format(config.get('email', ''), window.cloud_status.get('message', '')))
            self.sign_btn.hide()
            self.reauth_btn.show()
            self.sync_now_btn.show()

    def _sync_now(self):
        self._on_message('wait', 'Eşitleniyor...')
        self.window.start_cloud_sync(force=True)

    def _field(self, label, value, placeholder):
        title = QLabel(label)
        title.setStyleSheet('color: #d4e2ff; border: none; font-size: 12px;')
        self.card_layout.addWidget(title)
        field = QLineEdit(value)
        field.setPlaceholderText(placeholder)
        field.setAccessibleName(label)
        self.card_layout.addWidget(field)
        return field

    def _config(self):
        config = {'url': self.url_field.text().strip().rstrip('/'), 'key': self.key_field.text().strip(),
                  'email': self.email_field.text().strip(), 'enabled': True}
        SupabaseClient(config['url'], config['key'])
        if '@' not in config['email']:
            raise ValueError('Geçerli bir e-posta adresi girin.')
        return config

    def _send_link(self):
        try:
            config = self._config()
            self.callback = LinkCallback()
        except (ValueError, OSError) as exc:
            self._on_message('error', str(exc))
            return
        self.sign_btn.setEnabled(False)
        self._on_message('wait', 'Bağlantı gönderiliyor...')
        callback, cloud, relay = self.callback, self.window.cloud, self.relay

        def work():
            try:
                cloud.sign_in(config, callback, on_sent=lambda: relay.message.emit(
                    'wait', 'E-postanıza gelen bağlantıyı bu bilgisayarda açın. 10 dakika bekleniyor...'))
                relay.message.emit('done', json.dumps(config))
            except (OSError, ValueError) as exc:
                relay.message.emit('error', str(exc))
        threading.Thread(target=work, daemon=True).start()

    def _on_message(self, kind, text):
        colors = {'error': '#fca5a5', 'wait': '#93c5fd', 'done': '#6ee7b7'}
        self.state_label.setStyleSheet('color: {}; border: none; font-size: 12px;'.format(colors[kind]))
        if kind == 'done':
            self.window.set_cloud_config(json.loads(text))
            super().accept()
            return
        self.state_label.setText(text)
        if kind == 'error':
            self.sign_btn.setEnabled(True)

    def _turn_off(self):
        config = cloud_sync.get_config(self.window.task_manager)
        if config:
            self.window.set_cloud_config(dict(config, enabled=False))
            try:
                self.window.cloud.sign_out(config)
            except OSError as exc:
                self._on_message('error', str(exc))
                return
        super().accept()

    def done(self, result):
        if self.callback:
            self.callback.cancel()
        super().done(result)


class CustomInputDialog(ModernDialog):
    def __init__(self, title, prompt, parent=None, confirm_text="Ekle", multiline=False):
        super().__init__(title, parent)
        self._multiline = multiline
        prompt_lbl = QLabel(prompt)
        prompt_lbl.setWordWrap(True)
        prompt_lbl.setStyleSheet("color: #96add4; font-size: 12px; border: none;")
        self.card_layout.addWidget(prompt_lbl)

        if multiline:
            self.input_field = QTextEdit()
            self.input_field.setFixedHeight(96)
            self.input_field.setAcceptRichText(False)
            self.input_field.installEventFilter(self)
            hint = QLabel('Kaydetmek için Ctrl+Enter kullanabilirsiniz.')
            hint.setStyleSheet('color: #7e95b8; font-size: 11px; border: none;')
            self.card_layout.addWidget(self.input_field)
            self.card_layout.addWidget(hint)
        else:
            self.input_field = QLineEdit()
            self.input_field.returnPressed.connect(self.accept)
            self.card_layout.addWidget(self.input_field)
        self.input_field.setAccessibleName(title)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Vazgeç")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.ok_btn = QPushButton(confirm_text)
        self.ok_btn.setProperty('role', 'primary')
        self.ok_btn.setCursor(Qt.PointingHandCursor)
        self.ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.ok_btn)

        self.card_layout.addLayout(btn_layout)

    def eventFilter(self, obj, event):
        if self._multiline and obj is self.input_field and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and (event.modifiers() & Qt.ControlModifier):
                self.accept()
                return True
        return super().eventFilter(obj, event)

    def set_text(self, value):
        if self._multiline:
            self.input_field.setPlainText(value or '')
        else:
            self.input_field.setText(value or '')

    def get_text(self):
        if self._multiline:
            return self.input_field.toPlainText().strip()
        return self.input_field.text().strip()


class CustomConfirmDialog(ModernDialog):
    def __init__(self, title, message, confirm_text="Temizle", is_destructive=True, parent=None, show_cancel=True):
        super().__init__(title, parent)
        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet("color: #b3c6e9; font-size: 13px; border: none;")
        self.card_layout.addWidget(msg_lbl)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()

        self.cancel_btn = None
        if show_cancel:
            self.cancel_btn = QPushButton("Vazgeç")
            self.cancel_btn.setCursor(Qt.PointingHandCursor)
            self.cancel_btn.clicked.connect(self.reject)
            btn_layout.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton(confirm_text)
        self.confirm_btn.setProperty('role', 'danger' if is_destructive else 'primary')
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.confirm_btn)

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
    task_requeued = pyqtSignal(str)
    task_review_changed = pyqtSignal(str, bool)
    task_publication = pyqtSignal(str, int, str)
    task_moved = pyqtSignal(str, object)

    STATUS_META = {
        'in_progress': ('Agent çalışıyor', 'sync', '#7dd3fc', '#0c1e3d', '#1d4ed8'),
        'needs_review': ('Kontrolünü bekliyor', 'warning', '#fbbf24', '#291e0a', '#a16207'),
        'blocked': ('Engellendi', 'blocked', '#fca5a5', '#2e0f14', '#b91c1c'),
    }

    def __init__(self, task, project_list, parent=None, is_bound=False):
        super().__init__(parent)
        self.task = task
        self.project_list = project_list
        self.is_bound = is_bound
        self.setObjectName("TaskCard")
        self.setStyleSheet("""
            QFrame#TaskCard {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #141f30,stop:1 #0e1623);
                border: 1px solid #354c70; border-radius: 14px;
            }
            QFrame#TaskCard:hover { border-color: #5577a6; }
            QLabel { border: none; background: transparent; }
        """)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(11, 8, 11, 8)
        self.row.setSpacing(10)
        self.checkbox = QCheckBox()
        self.checkbox.setAccessibleName(f"Görevi tamamla: {task.get('title', '')}")
        self.checkbox.setChecked(task.get('completed', False))
        self.checkbox.setCursor(Qt.PointingHandCursor)
        self.checkbox.setStyleSheet(f"""
            QCheckBox {{ border: none; background: transparent; }}
            QCheckBox::indicator {{ width: 20px; height: 20px; border: 2px solid #8da4cd;
                border-radius: 6px; background: #101a2b; }}
            QCheckBox::indicator:hover, QCheckBox::indicator:focus {{ border-color: #60a5fa; }}
            QCheckBox::indicator:checked {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1674d6,stop:1 #4935f5);
                border-color: #5898ff; image: url({white_check_path}); }}
        """)
        self.checkbox.stateChanged.connect(lambda: self.task_toggled.emit(task['id']))
        self.row.addWidget(self.checkbox, 0, Qt.AlignTop)

        self.content = QVBoxLayout()
        self.content.setSpacing(5)
        raw_title = task.get('title', '')
        self.title_label = QLabel(_wrap_unbroken(raw_title))
        self.title_label.setTextFormat(Qt.PlainText)
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.title_label.setMinimumWidth(0)
        if len(raw_title) > 55:
            self.title_label.setToolTip(raw_title)
        font = QFont("Segoe UI")
        font.setPointSize(10)
        font.setStrikeOut(task.get('completed', False))
        self.title_label.setFont(font)
        self.title_label.setMaximumWidth(16777215)
        self.title_label.setStyleSheet("color: %s;" % ('#91a5c7' if task.get('completed') else '#f2f5fc'))
        self.content.addWidget(self.title_label)

        self.metadata = QHBoxLayout()
        self.metadata.setSpacing(6)
        date = task.get('completed_at') or task.get('created_at', '')
        try:
            parsed = datetime.strptime(date, '%d.%m.%Y %H:%M')
            date_text = 'Bugün' if parsed.date() == datetime.now().date() else parsed.strftime('%d.%m.%Y')
        except ValueError:
            date_text = date.split(' ')[0]

        status = task.get('status')
        delivery = task.get('delivery')
        status_info = self.STATUS_META.get(status)

        self.status_icon = QLabel()
        self.secondary_date_lbl = None
        if status_info:
            status_text, icon_name, fg_col, bg_col, border_col = status_info
            self.status_icon.setPixmap(make_icon(icon_name, fg_col, 14).pixmap(14, 14))
            self.metadata.addWidget(self.status_icon)
            self.date_label = QLabel(status_text)
            self.date_label.setStyleSheet(
                f'background: {bg_col}; color: {fg_col}; border: 1px solid {border_col}; '
                f'border-radius: 5px; padding: 1px 6px; font-size: 11px; font-weight: 600;'
            )
            self.metadata.addWidget(self.date_label)
            if date_text:
                self.secondary_date_lbl = QLabel(date_text)
                self.secondary_date_lbl.setStyleSheet('color: #8ea5cc; font-size: 11px;')
                self.metadata.addWidget(self.secondary_date_lbl)
        else:
            if task.get('completed') and delivery == 'published':
                self.status_icon.setPixmap(make_icon('check_circle', '#34d399', 14).pixmap(14, 14))
                label_text = 'Yayınlandı' + ('  ·  ' + date_text if date_text else '')
                label_style = 'color: #6ee7b7; font-size: 11px; font-weight: 600;'
            elif task.get('completed'):
                label = {'local': 'Yerelde tamamlandı', 'published': 'Yayınlandı'}.get(delivery, 'Tamamlandı')
                self.status_icon.setPixmap(make_icon('check', '#7dd3fc', 14).pixmap(14, 14))
                label_text = label + ('  ·  ' + date_text if date_text else '')
                label_style = 'color: #96add4; font-size: 11px;'
            else:
                self.status_icon.setPixmap(make_icon('calendar', '#96add4', 14).pixmap(14, 14))
                label_text = date_text
                label_style = 'color: #96add4; font-size: 11px;'
            self.metadata.addWidget(self.status_icon)
            self.date_label = QLabel(label_text)
            self.date_label.setStyleSheet(label_style)
            self.metadata.addWidget(self.date_label)

        self.date_label.setToolTip(TaskManager.delivery_label(task) + ('\n' + task['result']['summary'] if task.get('result') else ''))

        self._raw_note = task.get('notes', '')
        self.note_btn = QPushButton()
        self.note_btn.setCursor(Qt.PointingHandCursor)
        self.note_btn.setToolTip(self._raw_note or 'Göreve ek not ekle')
        self.note_btn.setAccessibleName('Görev notu: ' + (self._raw_note or 'Not ekle'))
        if self._raw_note:
            self.note_btn.setIcon(make_icon('note', '#9ec0f0', 13))
            self.note_btn.setIconSize(QSize(13, 13))
            self.note_btn.setStyleSheet("""
                QPushButton { color: #b5ccf2; background: #182740; border: 1px solid #304769;
                    border-radius: 5px; padding: 1px 6px; font-size: 11px; text-align: left; }
                QPushButton:hover, QPushButton:focus { color: #ffffff; border-color: #60a5fa; background: #1e3252; }
            """)
        else:
            self.note_btn.setText('·  Not ekle...')
            self.note_btn.setStyleSheet("""
                QPushButton { color: #96add4; font-size: 11px; border: none; background: transparent; text-align: left; padding: 1px 2px; }
                QPushButton:hover, QPushButton:focus { color: #cfdef8; }
            """)
        self.note_btn.clicked.connect(self._edit_note)
        self.metadata.addWidget(self.note_btn)
        self.metadata.addStretch()
        self.content.addLayout(self.metadata)

        self.badge_row = QHBoxLayout()
        self.badge_row.setContentsMargins(0, 0, 0, 0)
        self.badge_row.setSpacing(6)
        self.content.addLayout(self.badge_row)

        self.row.addLayout(self.content, 1)
        self.badge = None
        proj = task.get('project')
        if proj:
            bg, fg = get_project_color(proj, project_list)
            self.badge = QLabel('[' + proj + ']')
            self.badge.setTextFormat(Qt.PlainText)
            self.badge.setToolTip(proj)
            self.badge.setStyleSheet(f"QLabel {{ background: {bg}; color: {fg}; border: 1px solid {fg}; border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 600; }}")
            self.row.addWidget(self.badge, 0, Qt.AlignTop)

        self.menu_btn = QPushButton()
        self.menu_btn.setIcon(make_icon('dots'))
        self.menu_btn.setIconSize(QSize(18, 18))
        self.menu_btn.setFixedSize(26, 26)
        self.menu_btn.setToolTip('Görev seçenekleri')
        self.menu_btn.setAccessibleName('Görev seçenekleri')
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        self.menu_btn.setStyleSheet('QPushButton { border: none; border-radius: 6px; background: transparent; } QPushButton:hover { background: #22334e; } QPushButton:focus { background: #22334e; border: 1px solid #60a5fa; }')
        self.menu_btn.clicked.connect(self._show_menu)
        self.row.addWidget(self.menu_btn, 0, Qt.AlignTop)

    def fit_to_width(self, width):
        compact = width < 790
        self.row.setContentsMargins(11, 8, 11, 8)
        self.row.setSpacing(10)
        m = self.row.contentsMargins()
        content_width = max(90, width - m.left() - m.right() - 22 - 26 - self.row.spacing() * 2)

        # Clear badge_row completely (including stretch spacers) before re-populating.
        while self.badge_row.count():
            item = self.badge_row.takeAt(0)
            if item.widget():
                item.widget().setParent(self)

        if self.badge:
            self.row.removeWidget(self.badge)
            if compact:
                self.badge_row.addWidget(self.badge, 0, Qt.AlignVCenter)
            else:
                self.row.insertWidget(2, self.badge, 0, Qt.AlignTop)
            max_badge = max(90, min(300, content_width - (68 if self._raw_note else 6) if compact else int(width * .30)))
            self.badge.setMaximumWidth(max_badge)
            self.badge.setText(QFontMetrics(self.badge.font()).elidedText('[' + self.task['project'] + ']', Qt.ElideRight, max(40, max_badge - 18)))

        # Notes with content remain visible at all widths; empty note prompt shows only when wide.
        self.metadata.removeWidget(self.note_btn)
        has_bottom_row = bool(self.badge and compact)
        if self._raw_note:
            self.note_btn.setVisible(True)
            note_one_line = ' '.join(self._raw_note.split())
            if compact:
                self.badge_row.addWidget(self.note_btn, 0, Qt.AlignVCenter)
                has_bottom_row = True
                badge_w = min(self.badge.sizeHint().width(), self.badge.maximumWidth()) + 8 if self.badge else 0
                note_budget = max(56, content_width - badge_w - 28)
                self.note_btn.setMaximumWidth(note_budget + 24)
                self.note_btn.setText(QFontMetrics(self.note_btn.font()).elidedText(note_one_line, Qt.ElideRight, note_budget))
            else:
                self.metadata.insertWidget(self.metadata.count() - 1, self.note_btn)
                note_budget = max(120, int(content_width * 0.42))
                self.note_btn.setMaximumWidth(note_budget + 24)
                self.note_btn.setText(QFontMetrics(self.note_btn.font()).elidedText(note_one_line, Qt.ElideRight, note_budget))
        else:
            show_prompt = width >= 540
            self.note_btn.setVisible(show_prompt)
            if show_prompt:
                self.metadata.insertWidget(self.metadata.count() - 1, self.note_btn)
                self.note_btn.setMaximumWidth(160)
                self.note_btn.setText('·  Not ekle...')

        if has_bottom_row:
            self.badge_row.addStretch()

        if self.secondary_date_lbl is not None:
            self.secondary_date_lbl.setVisible(width >= 340)

        title_width = content_width
        if self.badge and not compact:
            title_width -= min(self.badge.sizeHint().width(), self.badge.maximumWidth()) + self.row.spacing()
        title_height = QFontMetrics(self.title_label.font()).boundingRect(
            QRect(0, 0, max(80, title_width), 10000), Qt.TextWordWrap, self.title_label.text()
        ).height()
        meta_height = 20
        height = title_height + self.content.spacing() + meta_height + m.top() + m.bottom()
        if has_bottom_row:
            bottom_h = max(
                self.badge.sizeHint().height() if (self.badge and compact) else 0,
                self.note_btn.sizeHint().height() if (self._raw_note and compact) else 0,
                22
            )
            height += self.content.spacing() + bottom_h
        # QListWidget's item margin consumes four pixels of the size hint.
        return max(48, height + 6)

    def _edit_title(self):
        task_id = self.task['id']
        dialog = CustomInputDialog('Görevi Düzenle', 'Görev metnini düzenleyin:', self.window(), confirm_text='Kaydet')
        dialog.set_text(self.task.get('title', ''))
        if dialog.exec_() == QDialog.Accepted and dialog.get_text():
            self.task_edited.emit(task_id, dialog.get_text())

    def _edit_note(self):
        task_id = self.task['id']
        dialog = CustomInputDialog('Görev Notu', 'Görev notunu yazın (boş bırakırsanız not silinir):',
                                   self.window(), confirm_text='Kaydet', multiline=True)
        dialog.set_text(self.task.get('notes', ''))
        if dialog.exec_() == QDialog.Accepted:
            self.task_noted.emit(task_id, dialog.get_text())

    def _show_menu(self):
        task_id = self.task['id']
        task_rev = self.task.get('revision', 1)
        current_proj = self.task.get('project')
        show_agent = (
            self.is_bound
            or bool(self.task.get('result'))
            or bool(self.task.get('review_required'))
            or self.task.get('status') in {'in_progress', 'needs_review', 'blocked'}
            or self.task.get('delivery') in {'local', 'published'}
        )

        menu = QMenu(self.window())
        menu.setStyleSheet(MENU_STYLE)
        edit = menu.addAction('Görevi düzenle')
        note = menu.addAction('Notu düzenle')

        move_actions = {}
        if self.project_list or current_proj is not None:
            move_menu = menu.addMenu('Projeye taşı')
            move_menu.setStyleSheet(MENU_STYLE)
            none_act = move_menu.addAction('Projesiz (Tümü)')
            none_act.setCheckable(True)
            none_act.setChecked(current_proj is None)
            move_actions[none_act] = None
            for proj in self.project_list:
                act = move_menu.addAction(proj)
                act.setCheckable(True)
                act.setChecked(current_proj == proj)
                move_actions[act] = proj

        result = publication = review = requeue = None
        if show_agent:
            menu.addSeparator()
            result = menu.addAction('Agent sonucunu gör') if self.task.get('result') else None
            publication = menu.addAction('Yayın doğrulamasını kaydet') if self.task.get('status') in {'completed', 'needs_review'} else None
            review = menu.addAction('Agent sonrası onayım gerekli')
            review.setCheckable(True)
            review.setChecked(self.task.get('review_required', False))
            requeue = menu.addAction('Tekrar sıraya al') if self.task.get('status') in {'in_progress', 'needs_review', 'blocked'} else None

        menu.addSeparator()
        delete = menu.addAction('Görevi sil')
        action = menu.exec_(self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomLeft()))
        if action is None:
            return
        if action == edit:
            self._edit_title()
        elif action == note:
            self._edit_note()
        elif action in move_actions:
            target_proj = move_actions[action]
            if target_proj != current_proj:
                self.task_moved.emit(task_id, target_proj)
        elif action == delete:
            self.task_deleted.emit(task_id)
        elif result is not None and action == result:
            self._show_agent_result()
        elif publication is not None and action == publication:
            dialog = CustomInputDialog('Yayın doğrulaması', 'Gerçekleşen yayının adresini veya doğrulama kaydını yazın:',
                                       self.window(), confirm_text='Kaydet')
            if dialog.exec_() == QDialog.Accepted and dialog.get_text():
                self.task_publication.emit(task_id, task_rev, dialog.get_text())
        elif review is not None and action == review:
            self.task_review_changed.emit(task_id, review.isChecked())
        elif requeue is not None and action == requeue:
            self.task_requeued.emit(task_id)

    def _show_agent_result(self):
        task_id = self.task['id']
        needs_review = self.task.get('status') == 'needs_review'
        dialog = ModernDialog('Agent sonucu', self.window())
        dialog.resize(420, 360)
        result = self.task['result']
        text = QTextEdit()
        text.setReadOnly(True)
        entries = ['Yayın durumu: ' + TaskManager.delivery_label(self.task)]
        if self.task.get('publication_evidence'):
            entries.append('Yayın doğrulaması: ' + self.task['publication_evidence'])
        for report in self.task.get('history', []) or [result]:
            entries.append(report['reported_at'] + '\nYapılan işlem:\n' + report['summary'] +
                           '\n\nDoğrulama:\n' + (report['evidence'] or 'Doğrulama kaydı yok.'))
        text.setPlainText('\n\n'.join(entries))
        dialog.card_layout.addWidget(text, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        decision = {'action': None}
        if needs_review:
            requeue_btn = QPushButton('Tekrar sıraya al')
            requeue_btn.setCursor(Qt.PointingHandCursor)
            requeue_btn.clicked.connect(lambda: (decision.update(action='requeue'), dialog.accept()))
            buttons.addWidget(requeue_btn)
        buttons.addStretch()
        close = QPushButton('Kapat')
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(dialog.reject)
        buttons.addWidget(close)
        if needs_review:
            approve_btn = QPushButton('Onayla ve tamamla')
            approve_btn.setProperty('role', 'primary')
            approve_btn.setCursor(Qt.PointingHandCursor)
            approve_btn.clicked.connect(lambda: (decision.update(action='approve'), dialog.accept()))
            buttons.addWidget(approve_btn)
        dialog.card_layout.addLayout(buttons)
        dialog.exec_()
        if decision['action'] == 'approve':
            self.task_toggled.emit(task_id)
        elif decision['action'] == 'requeue':
            self.task_requeued.emit(task_id)

    def mouseDoubleClickEvent(self, event):
        if self.title_label.geometry().contains(event.pos()):
            self._edit_title()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


# --- Draggable Header Bar ---
class DraggableHeader(QFrame):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self._drag_pos = None
        self._did_move = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.parent_window.frameGeometry().topLeft()
            self._did_move = False
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.parent_window.move(event.globalPos() - self._drag_pos)
            self._did_move = True
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._did_move and hasattr(self.parent_window, '_save_window_geometry'):
            self.parent_window._save_window_geometry()
        self._drag_pos = None
        self._did_move = False


class TaskArchiveDialog(ModernDialog):
    def __init__(self, manager, project, parent=None):
        super().__init__('Arşiv · ' + project, parent)
        self.manager, self.project = manager, project
        self.resize(420, 500)
        self.list = QListWidget()
        self.list.setAccessibleName('Arşivlenen görevler')
        self.card_layout.addWidget(self.list, 1)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setAccessibleName('Arşivlenen görev sonucu ve geçmişi')
        self.card_layout.addWidget(self.details, 1)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch()
        close = QPushButton('Kapat')
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        self.restore_btn = QPushButton('Geri getir')
        self.restore_btn.setProperty('role', 'primary')
        self.restore_btn.setCursor(Qt.PointingHandCursor)
        self.restore_btn.clicked.connect(self._restore)
        buttons.addWidget(self.restore_btn)
        self.card_layout.addLayout(buttons)
        self.list.currentItemChanged.connect(self._select)
        self._reload()

    def _reload(self):
        self.manager.reload_if_changed()
        self.list.clear()
        self.tasks = self.manager.get_tasks(self.project, archived=True)
        for task in self.tasks:
            label = task['title']
            if self.project == 'Tümü' and task.get('project'):
                label = f"[{task['project']}]  {label}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, task['id'])
            self.list.addItem(item)
        if self.tasks:
            self.list.setCurrentRow(0)
        else:
            self.details.setPlainText('Bu listede arşivlenen görev yok.\nTamamlananları Arşivle ile görevleri buraya taşıyabilirsiniz.')
            self.restore_btn.setEnabled(False)

    def _select(self, item, previous=None):
        task = next((t for t in self.tasks if item and t['id'] == item.data(Qt.UserRole)), None)
        self.restore_btn.setEnabled(task is not None)
        if not task:
            return
        entries = [task['title']]
        if task.get('project'):
            entries.append('Proje: ' + task['project'])
        entries.extend([TaskManager.delivery_label(task), 'Arşiv tarihi: ' + task['archived_at']])
        if task.get('notes'):
            entries.append('Not: ' + task['notes'])
        if task.get('publication_evidence'):
            entries.append('Yayın doğrulaması: ' + task['publication_evidence'])
        for result in task.get('history', []) or ([task['result']] if task.get('result') else []):
            entries.append(result['reported_at'] + '\n' + result['summary'] + '\nDoğrulama: ' + result['evidence'])
        self.details.setPlainText('\n\n'.join(entries))

    def _restore(self):
        item = self.list.currentItem()
        if item:
            self.manager.restore_task(item.data(Qt.UserRole))
            self._reload()


# --- Main Application Window ---
class TaskFlowApp(QMainWindow):
    CLOUD_INTERVAL_MS = 30000
    CLOUD_COLORS = {'off': '#71829e', 'syncing': '#60a5fa', 'ok': '#34d399', 'offline': '#fbbf24',
                    'signed_out': '#f87171'}

    def __init__(self, start_minimized=False, task_manager=None, setup_autostart=True, cloud=None):
        super().__init__()
        self.task_manager = task_manager if task_manager is not None else TaskManager()
        self.cloud = cloud or cloud_sync.CloudSync(self.task_manager.db_file)
        self.cloud_status = {'state': 'off', 'message': 'Bulut senkronu kapalı.'}
        self._cloud_running = False
        self._cloud_synced_change = None
        self.current_project = self.task_manager.settings.get('selected_project', 'Tümü')
        self.start_minimized = start_minimized

        self._resizing_edge = None
        self._resize_start_pos = QPoint()
        self._resize_start_geom = QRect()
        self._pending_external_refresh = False
        self._tab_buttons = {}
        self._tab_project_order = None
        self._undo_entry = None
        self._undo_timer = QTimer(self)
        self._undo_timer.setSingleShot(True)
        self._undo_timer.timeout.connect(self._hide_undo_bar)

        # Ensure Windows Autostart is active
        try:
            if setup_autostart and self.task_manager.settings.get('autostart', True):
                autostart.set_autostart(True)
        except Exception:
            pass

        self._setup_window()
        self._setup_tray()
        self._setup_ui()
        self._setup_shortcuts()
        self._refresh_project_tabs()
        self._refresh_tasks()
        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(1500)
        self.sync_timer.timeout.connect(self._poll_external_changes)
        self.sync_timer.start()
        self._last_sync_warning = None
        self.cloud_relay = _Relay(self)
        self.cloud_relay.status.connect(self._on_cloud_status)
        self.cloud_timer = QTimer(self)
        self.cloud_timer.setInterval(self.CLOUD_INTERVAL_MS)
        self.cloud_timer.timeout.connect(self.start_cloud_sync)
        self._apply_cloud_config()
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
        self._restore_window_geometry()

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
        cloud_action = QAction("Bulut senkronu", self)
        cloud_action.triggered.connect(self.show_cloud_dialog)
        tray_menu.addAction(cloud_action)
        self.tray_autostart_action = QAction("Windows ile başlat", self)
        self.tray_autostart_action.setCheckable(True)
        self.tray_autostart_action.setChecked(bool(self.task_manager.settings.get('autostart', True)))
        self.tray_autostart_action.triggered.connect(self._toggle_autostart)
        tray_menu.addAction(self.tray_autostart_action)

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
        self.header_layout = header
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)
        self.progress_ring = CircularProgressWidget(size=44)
        self.progress_ring.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        header.addWidget(self.progress_ring, 0, Qt.AlignTop)
        brand = QHBoxLayout()
        self.brand_layout = brand
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
        self.header_actions_layout = actions
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
        self.projects_menu_btn.setToolTip('Projeler ve seçenekler')
        self.projects_menu_btn.setAccessibleName('Projeler ve seçenekler')
        self.projects_menu_btn.setStyleSheet(CONTROL_STYLE)
        self.projects_menu_btn.clicked.connect(self._show_projects_overflow)
        project_bar.addWidget(self.projects_menu_btn)
        self.app_layout.addLayout(project_bar)
        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.input_box = QFrame()
        self.input_box.setObjectName('InputBox')
        self.input_box.setFixedHeight(42)
        self._set_input_box_focused(False)
        input_layout = QHBoxLayout(self.input_box)
        input_layout.setContentsMargins(10, 0, 10, 0)
        input_layout.setSpacing(8)
        doc = QLabel()
        doc.setPixmap(make_icon('document', size=18).pixmap(18, 18))
        input_layout.addWidget(doc)
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText('Yeni bir görev yazın... [Enter]')
        self.task_input.setAccessibleName('Yeni görev')
        self.task_input.setStyleSheet('QLineEdit { background: transparent; color: #f3f6ff; border: none; font-size: 13px; selection-background-color: #1d56d8; selection-color: #ffffff; }')
        palette = self.task_input.palette()
        palette.setColor(palette.PlaceholderText, QColor('#98acd0'))
        self.task_input.setPalette(palette)
        self.task_input.returnPressed.connect(self._add_task)
        self.task_input.textChanged.connect(self._on_task_input_changed)
        input_layout.addWidget(self.task_input, 1)
        input_row.addWidget(self.input_box, 1)
        self.add_btn = QPushButton()
        self.add_btn.setIcon(make_icon('plus', '#6b82a8', 32))
        self.add_btn.setIconSize(QSize(22, 22))
        self.add_btn.setFixedSize(42, 42)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setToolTip('Görev ekle')
        self.add_btn.setAccessibleName('Görev ekle')
        self.add_btn.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1674d6,stop:1 #5726f5);
                border: 1px solid #6388ff; border-radius: 15px; }
            QPushButton:hover, QPushButton:focus { border: 2px solid #a9caff; }
            QPushButton:pressed { background: #1d4ed8; }
            QPushButton:disabled { background: #152136; border: 1px solid #2b3e5e; }
        """)
        self.add_btn.clicked.connect(self._add_task)
        self.add_btn.setEnabled(False)
        input_row.addWidget(self.add_btn)
        self.app_layout.addLayout(input_row)
        self.task_list_widget = QListWidget()
        self.task_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.task_list_widget.setSelectionMode(QListWidget.NoSelection)
        self.task_list_widget.setSpacing(4)
        self.task_list_widget.setStyleSheet("""
            QListWidget { background: transparent; border: 1px solid transparent; border-radius: 10px; outline: none; }
            QListWidget:focus { border: 1px solid #3c5f94; }
            QListWidget::item { background: transparent; border: none; padding: 0; margin-bottom: 3px; }
        """ + DARK_SCROLLBAR_STYLE)
        self.empty_lbl = QLabel('İlk adımı atın.\nYukarıdan bir görev ekleyerek başlayın.', self.task_list_widget.viewport())
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        self.empty_lbl.setStyleSheet('color: #98acd0; font-size: 13px;')
        self.empty_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.app_layout.addWidget(self.task_list_widget, 1)

        # Inline non-blocking Undo bar for destructive actions
        self.undo_bar = QFrame()
        self.undo_bar.setObjectName('UndoBar')
        self.undo_bar.setStyleSheet(
            'QFrame#UndoBar { background: #15243b; border: 1px solid #3c5f94; border-radius: 10px; }'
        )
        undo_layout = QHBoxLayout(self.undo_bar)
        undo_layout.setContentsMargins(10, 6, 8, 6)
        undo_layout.setSpacing(8)
        self.undo_lbl = QLabel('Görev silindi.')
        self.undo_lbl.setStyleSheet('color: #e2ecff; font-size: 12px; border: none;')
        undo_layout.addWidget(self.undo_lbl, 1)
        self.undo_btn = QPushButton('Geri Al')
        self.undo_btn.setCursor(Qt.PointingHandCursor)
        self.undo_btn.setStyleSheet(
            'QPushButton { background: #1d56d8; color: #ffffff; border: 1px solid #3b76f6; border-radius: 6px; '
            'padding: 3px 10px; font-size: 11px; font-weight: 700; } '
            'QPushButton:hover, QPushButton:focus { background: #2563eb; border-color: #93c5fd; }'
        )
        self.undo_btn.clicked.connect(self._undo_last_action)
        undo_layout.addWidget(self.undo_btn)
        undo_close = QPushButton()
        undo_close.setIcon(make_icon('close', '#96add4', 14))
        undo_close.setIconSize(QSize(14, 14))
        undo_close.setFixedSize(22, 22)
        undo_close.setToolTip('Bildirimi kapat')
        undo_close.setCursor(Qt.PointingHandCursor)
        undo_close.setStyleSheet('QPushButton { background: transparent; border: none; border-radius: 5px; } QPushButton:hover { background: #223656; }')
        undo_close.clicked.connect(self._hide_undo_bar)
        undo_layout.addWidget(undo_close)
        self.undo_bar.hide()
        self.app_layout.addWidget(self.undo_bar)

        self.footer = QFrame()
        self.footer.setObjectName('Footer')
        self.footer.setStyleSheet('QFrame#Footer { border: none; border-top: 1px solid #283b58; background: transparent; }')
        footer = QHBoxLayout(self.footer)
        self.footer_layout = footer
        footer.setContentsMargins(6, 5, 2, 0)
        footer.setSpacing(12)
        stats_icon = QLabel()
        stats_icon.setPixmap(make_icon('stats', size=22).pixmap(22, 22))
        footer.addWidget(stats_icon)
        self.stats_lbl = QLabel('0 aktif görev')
        self.stats_lbl.setStyleSheet('color: #dce9ff; font-size: 13px; font-weight: 700;')
        footer.addWidget(self.stats_lbl)
        sep = QFrame()
        sep.setFixedSize(1, 16)
        sep.setStyleSheet('background: #354c70; border: none;')
        footer.addWidget(sep)
        self.clear_btn = QPushButton('Tamamlananları Arşivle')
        self.clear_btn.setToolTip('Tamamlananları Arşivle · Sonuçlar korunur')
        self.clear_btn.setIcon(make_icon('check'))
        self.clear_btn.setIconSize(QSize(16, 16))
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setStyleSheet('QPushButton { background: transparent; color: #b3c9ee; border: none; border-radius: 6px; padding: 4px 8px; font-size: 11px; } QPushButton:hover, QPushButton:focus { background: #202e46; color: #ffffff; } QPushButton:disabled { color: #879aba; }')
        self.clear_btn.clicked.connect(self._confirm_clear_completed)
        footer.addWidget(self.clear_btn)
        footer.addStretch()
        self.footer_motto = QLabel('Küçük adımlar, büyük sonuçlar.')
        self.footer_motto.setStyleSheet('color: #9fb7df; font-family: "Segoe Print"; font-size: 11px; font-style: italic;')
        footer.addWidget(self.footer_motto)
        self.sparkle_lbl = QLabel()
        self.sparkle_lbl.setPixmap(make_icon('sparkle', size=22).pixmap(22, 22))
        footer.addWidget(self.sparkle_lbl)
        # While cloud sync is on, its status takes the decorative sparkle's slot, so the
        # approved footer keeps its width.
        self.cloud_btn = QPushButton()
        self.cloud_btn.setFixedSize(26, 26)
        self.cloud_btn.setIconSize(QSize(20, 20))
        self.cloud_btn.setCursor(Qt.PointingHandCursor)
        self.cloud_btn.setStyleSheet('QPushButton { background: transparent; border: none; border-radius: 6px; } '
                                     'QPushButton:hover, QPushButton:focus { background: #202e46; }')
        self.cloud_btn.clicked.connect(self.show_cloud_dialog)
        self.cloud_btn.hide()
        footer.addWidget(self.cloud_btn)
        self.app_layout.addWidget(self.footer)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence('Ctrl+N'), self, activated=self._focus_task_input)
        QShortcut(QKeySequence('Ctrl+Z'), self, activated=self._undo_last_action)
        QShortcut(QKeySequence('Ctrl+Shift+S'), self, activated=lambda: self.start_cloud_sync(force=True))

    def _focus_task_input(self):
        self.task_input.setFocus()
        self.task_input.selectAll()

    def _set_input_box_focused(self, focused):
        border = '#60a5fa' if focused else '#354c70'
        self.input_box.setStyleSheet(
            f'QFrame#InputBox {{ background: #121d2e; border: 1px solid {border}; border-radius: 15px; }}'
        )

    def _on_task_input_changed(self, text):
        enabled = bool(text.strip())
        self.add_btn.setEnabled(enabled)
        self.add_btn.setIcon(make_icon('plus', '#ffffff' if enabled else '#6b82a8', 32))

    def _restore_window_geometry(self):
        geom = self.task_manager.settings.get('window_geometry')
        if not isinstance(geom, dict):
            return
        try:
            x, y, w, h = int(geom['x']), int(geom['y']), int(geom['w']), int(geom['h'])
        except (KeyError, TypeError, ValueError):
            return
        w = max(self.minimumWidth(), min(w, 2400))
        h = max(self.minimumHeight(), min(h, 1600))
        target = QRect(x, y, w, h)
        screens = QApplication.screens()
        if screens and any(s.availableGeometry().intersects(target) for s in screens):
            self.setGeometry(target)
        else:
            self.resize(w, h)

    def _save_window_geometry(self):
        g = self.geometry()
        if g.width() < self.minimumWidth() or g.height() < self.minimumHeight():
            return
        self.task_manager.settings['window_geometry'] = {
            'x': g.x(), 'y': g.y(), 'w': g.width(), 'h': g.height()
        }
        try:
            self.task_manager.save()
        except Exception:
            pass

    def _show_projects_overflow(self):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        projects = list(self.task_manager.projects)
        all_act = menu.addAction('Tümü')
        all_act.setCheckable(True)
        all_act.setChecked(self.current_project == 'Tümü')
        all_act.triggered.connect(lambda: self._select_project('Tümü'))
        if len(projects) <= 6:
            for project in projects:
                action = menu.addAction(project)
                action.setCheckable(True)
                action.setChecked(project == self.current_project)
                action.triggered.connect(lambda checked, name=project: self._select_project(name))
        else:
            if self.current_project != 'Tümü' and self.current_project in projects:
                curr_act = menu.addAction(self.current_project)
                curr_act.setCheckable(True)
                curr_act.setChecked(True)
                curr_act.triggered.connect(lambda checked, name=self.current_project: self._select_project(name))
            sub = menu.addMenu(f'Projeler ({len(projects)})')
            sub.setStyleSheet(MENU_STYLE)
            for project in projects:
                action = sub.addAction(project)
                action.setCheckable(True)
                action.setChecked(project == self.current_project)
                action.triggered.connect(lambda checked, name=project: self._select_project(name))

        if self.current_project != 'Tümü':
            menu.addSeparator()
            rename = menu.addAction('Projeyi yeniden adlandır')
            rename.triggered.connect(lambda: self._rename_project(self.current_project))
            connection = menu.addAction('Agent bağlantısını ayarla')
            connection.triggered.connect(lambda: self._configure_connection(self.current_project))
            if self.current_project in self.task_manager.bindings:
                prompt = menu.addAction('Agent yönergesini kopyala')
                prompt.triggered.connect(lambda: self._copy_agent_prompt(self.current_project))

        menu.addSeparator()
        archive = menu.addAction('Arşivlenen görevler')
        archive.triggered.connect(self._show_archive)
        cloud = menu.addAction('Bulut senkronu')
        cloud.triggered.connect(self.show_cloud_dialog)
        auto = menu.addAction('Windows ile başlat')
        auto.setCheckable(True)
        auto.setChecked(bool(self.task_manager.settings.get('autostart', True)))
        auto.triggered.connect(self._toggle_autostart)
        menu.exec_(self.projects_menu_btn.mapToGlobal(self.projects_menu_btn.rect().bottomLeft()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'app_layout'):
            w = self.width()
            narrow = w < 385
            self.app_layout.setContentsMargins(14 if narrow else 18, 14 if narrow else 16, 14 if narrow else 18, 12)
            if hasattr(self, 'header_layout'):
                self.header_layout.setSpacing(8 if narrow else 12)
                self.brand_layout.setSpacing(6 if narrow else 8)
                self.header_actions_layout.setSpacing(5 if narrow else 8)
            self.subtitle_lbl.setVisible(not narrow)
            self.add_p_btn.setText('' if narrow else 'Proje Ekle')
            self.add_p_btn.setToolTip('Proje Ekle')
            self.header_motto.setVisible(w >= 850)
            self.footer_motto.setVisible(w >= 1000)
            if hasattr(self, 'footer_layout'):
                self.footer_layout.setSpacing(8 if narrow else 12)
            if hasattr(self, 'stats_lbl'):
                self.stats_lbl.setStyleSheet(f'color: #dce9ff; font-size: {12 if w < 370 else 13}px; font-weight: 700;')
            if hasattr(self, 'clear_btn'):
                self.clear_btn.setText('Arşivle' if w < 436 else 'Tamamlananları Arşivle')
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
        """Make the invisible edge catchment work over all child widgets and keep input focus ring synced."""
        etype = event.type()
        if obj is getattr(self, 'task_input', None):
            if etype == QEvent.FocusIn:
                self._set_input_box_focused(True)
            elif etype == QEvent.FocusOut:
                self._set_input_box_focused(False)

        if etype in (QEvent.Leave, QEvent.WindowDeactivate) and obj is self and not self._resizing_edge:
            self.setCursor(Qt.ArrowCursor)
            return super().eventFilter(obj, event)

        mouse_types = (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease)
        if etype not in mouse_types or not self.isVisible():
            return super().eventFilter(obj, event)

        # Always finish an active resize even if pointer left self.rect() or released over another window.
        if self._resizing_edge:
            if etype == QEvent.MouseButtonRelease:
                self.mouseReleaseEvent(event)
                return True
            if etype == QEvent.MouseMove:
                if not (event.buttons() & Qt.LeftButton):
                    self._resizing_edge = None
                    self.setCursor(Qt.ArrowCursor)
                    return super().eventFilter(obj, event)
                self.mouseMoveEvent(event)
                return True

        # Popup menus and dialogs can overlap the window edge; their clicks are never resizes.
        owner = obj.window() if isinstance(obj, QWidget) else obj
        if owner is not self and owner is not self.windowHandle():
            return super().eventFilter(obj, event)

        try:
            global_pos = event.globalPos()
        except AttributeError:
            return super().eventFilter(obj, event)

        pos = self.mapFromGlobal(global_pos)
        if not self.rect().contains(pos):
            return super().eventFilter(obj, event)

        edge = self._get_resize_edge(pos)
        if etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            if edge != (False, False, False, False):
                self._resizing_edge = edge
                self._resize_start_pos = global_pos
                self._resize_start_geom = self.geometry()
                event.accept()
                return True
        elif etype == QEvent.MouseMove:
            self._update_cursor_for_edge(edge)

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
        was_resizing = self._resizing_edge is not None
        self._resizing_edge = None
        self.setCursor(Qt.ArrowCursor)
        if was_resizing:
            self._save_window_geometry()
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
        desired_order = ['Tümü'] + list(self.task_manager.projects)
        if self._tab_project_order == desired_order and all(name in self._tab_buttons for name in desired_order):
            self._update_project_tab_styles()
            return

        prev_scroll = self.tabs_scroll.horizontalScrollBar().value()
        self._tab_buttons = {}
        while self.project_tabs_layout.count():
            item = self.project_tabs_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # [Tümü] tab
        all_btn = ScrollableTabButton("Tümü", self.tabs_scroll)
        all_btn.setCheckable(True)
        all_btn.setCursor(Qt.PointingHandCursor)
        all_btn.clicked.connect(lambda: self._select_project("Tümü"))
        self.project_tabs_layout.addWidget(all_btn)
        self._tab_buttons["Tümü"] = all_btn

        # User defined Project tabs with distinct color bullet
        for proj in self.task_manager.projects:
            p_btn = ScrollableTabButton(proj, self.tabs_scroll)
            p_btn.setCheckable(True)
            p_btn.setCursor(Qt.PointingHandCursor)
            p_btn.clicked.connect(lambda checked, p=proj: self._select_project(p))
            p_btn.setContextMenuPolicy(Qt.CustomContextMenu)
            p_btn.customContextMenuRequested.connect(lambda pos, p=proj: self._show_project_menu(p))
            self.project_tabs_layout.addWidget(p_btn)
            self._tab_buttons[proj] = p_btn

        self.project_tabs_layout.addStretch()
        self._tab_project_order = desired_order
        self._update_project_tab_styles()
        self.tabs_scroll.horizontalScrollBar().setValue(prev_scroll)
        QTimer.singleShot(0, self._ensure_active_tab_visible)

    def _update_project_tab_styles(self):
        all_btn = self._tab_buttons.get("Tümü")
        if all_btn:
            is_active = (self.current_project == "Tümü")
            all_btn.setChecked(is_active)
            self._apply_all_tab_style(all_btn, is_active)
        for proj in self.task_manager.projects:
            p_btn = self._tab_buttons.get(proj)
            if not p_btn:
                continue
            bg_col, fg_col = get_project_color(proj, self.task_manager.projects)
            p_btn.setIcon(make_icon('dot', fg_col))
            p_btn.setIconSize(QSize(16, 16))
            is_active = (self.current_project == proj)
            p_btn.setChecked(is_active)
            self._apply_project_tab_style(p_btn, is_active, bg_col, fg_col)

    def _ensure_active_tab_visible(self):
        btn = self._tab_buttons.get(self.current_project)
        if btn is not None:
            self.tabs_container.adjustSize()
            self.tabs_scroll.ensureWidgetVisible(btn, 24, 0)

    def _apply_all_tab_style(self, btn, is_active):
        btn.setIcon(make_icon('grid', '#72bdff'))
        btn.setIconSize(QSize(18, 18))
        self._apply_project_tab_style(btn, is_active, '#102849', '#38abff')

    def _apply_project_tab_style(self, btn, is_active, bg_col, fg_col):
        btn.setFixedHeight(38)
        btn.setToolTip(btn.text())
        btn.setStyleSheet(f"""
            QPushButton {{ background: {bg_col if is_active else '#0f1929'};
                color: #d4e2ff; border: 1px solid {fg_col if is_active else '#2d4264'};
                border-radius: 9px; padding: 5px 12px; font-size: 12px; font-weight: {700 if is_active else 600}; }}
            QPushButton:hover, QPushButton:focus {{ background: {bg_col}; border-color: {fg_col}; }}
            QPushButton:pressed {{ background: #20304a; }}
        """)

    def _select_project(self, proj_name):
        self.current_project = proj_name
        self.task_manager.settings['selected_project'] = proj_name
        self.task_manager.save()
        self._refresh_project_tabs()
        self._ensure_active_tab_visible()
        QTimer.singleShot(0, self._ensure_active_tab_visible)
        self._refresh_tasks(reset_scroll=True)

    def _prompt_add_project(self):
        dialog = CustomInputDialog("Yeni Proje", "Yeni proje adını girin:", self, confirm_text="Ekle")
        if dialog.exec_() == QDialog.Accepted:
            proj_name = dialog.get_text()
            if proj_name:
                if self.task_manager.add_project(proj_name):
                    self._select_project(proj_name)
                else:
                    msg_box = CustomConfirmDialog("Bilgi", "Bu proje adı zaten mevcut!", confirm_text="Tamam",
                                                  is_destructive=False, parent=self, show_cancel=False)
                    msg_box.exec_()

    def _rename_project(self, proj_name):
        dialog = CustomInputDialog("Projeyi Yeniden Adlandır", f"'{proj_name}' için yeni proje adını girin:",
                                   self, confirm_text="Kaydet")
        dialog.set_text(proj_name)
        if dialog.exec_() == QDialog.Accepted:
            new_name = dialog.get_text()
            if not new_name or new_name == proj_name:
                return
            try:
                if self.task_manager.rename_project(proj_name, new_name):
                    if self.current_project == proj_name:
                        self.current_project = new_name
                    self._tab_project_order = None
                    self._refresh_project_tabs()
                    self._ensure_active_tab_visible()
                    self._refresh_tasks()
            except (ValueError, OSError, sqlite3.Error) as exc:
                CustomConfirmDialog('Proje yeniden adlandırılamadı', str(exc), confirm_text='Tamam',
                                    is_destructive=False, parent=self, show_cancel=False).exec_()

    def _show_project_menu(self, proj_name):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        rename_act = menu.addAction('Projeyi yeniden adlandır')
        archive_act = menu.addAction('Arşivlenen görevler')
        bind_act = menu.addAction('Agent bağlantısını ayarla')
        prompt_act = menu.addAction('Agent yönergesini kopyala') if proj_name in self.task_manager.bindings else None
        menu.addSeparator()
        del_act = menu.addAction(f"'{proj_name}' Projesini Sil")
        action = menu.exec_(self.cursor().pos())
        if action == rename_act:
            self._rename_project(proj_name)
        elif action == archive_act:
            self._show_archive(proj_name)
        elif action == bind_act:
            self._configure_connection(proj_name)
        elif prompt_act is not None and action == prompt_act:
            self._copy_agent_prompt(proj_name)
        elif action == del_act:
            dialog = CustomConfirmDialog(
                "Projeyi Sil",
                f"'{proj_name}' projesini silmek istediğinize emin misiniz?\nİçindeki görevler genel listeye aktarılacaktır.",
                confirm_text="Sil",
                parent=self
            )
            if dialog.exec_() == QDialog.Accepted:
                try:
                    self.task_manager.delete_project(proj_name)
                    self._select_project("Tümü")
                except (ValueError, OSError, sqlite3.Error) as exc:
                    CustomConfirmDialog('Proje silinemedi', str(exc), confirm_text='Tamam',
                                        is_destructive=False, parent=self, show_cancel=False).exec_()

    def _configure_connection(self, project):
        dialog = ProjectConnectionDialog(project, self.task_manager.bindings.get(project, {}), self)
        if dialog.exec_() == QDialog.Accepted:
            self._notify_sync_warnings()
            self._refresh_tasks()

    def _copy_agent_prompt(self, project):
        try:
            QApplication.clipboard().setText(agent_prompt(self.task_manager, project))
            self.tray_icon.showMessage('TaskFlow', 'Yönerge kopyalandı. Agent sohbetine yapıştırarak başlatabilirsiniz.',
                                       QSystemTrayIcon.Information, 3500)
        except (ValueError, OSError) as exc:
            CustomConfirmDialog('Bağlantı bilgisi', str(exc), confirm_text='Tamam',
                                is_destructive=False, parent=self, show_cancel=False).exec_()

    def _toggle_autostart(self, checked):
        enabled = bool(checked)
        self.task_manager.settings['autostart'] = enabled
        self.task_manager.save()
        if hasattr(self, 'tray_autostart_action'):
            self.tray_autostart_action.setChecked(enabled)
        try:
            autostart.set_autostart(enabled)
        except Exception as exc:
            CustomConfirmDialog('Otomatik başlatma güncellenemedi', str(exc), confirm_text='Tamam',
                                is_destructive=False, parent=self, show_cancel=False).exec_()

    def _poll_external_changes(self):
        try:
            busy = QApplication.activeModalWidget() is not None or QApplication.activePopupWidget() is not None
            changed = self.task_manager.reload_if_changed()
            if changed:
                if busy:
                    self._pending_external_refresh = True
                else:
                    self._apply_external_refresh()
            elif self._pending_external_refresh and not busy:
                self._apply_external_refresh()
            self._notify_sync_warnings()
            if self.cloud_timer.isActive() and self.task_manager._change != self._cloud_synced_change:
                # A local edit, or a result written by the agent bridge: push it soon.
                self.start_cloud_sync()
        except (OSError, ValueError, sqlite3.Error) as exc:
            if str(exc) != self._last_sync_warning:
                self.tray_icon.showMessage('TaskFlow', 'Görevler yenilenemedi: ' + str(exc), QSystemTrayIcon.Warning, 5000)
                self._last_sync_warning = str(exc)

    def _apply_external_refresh(self):
        self._pending_external_refresh = False
        if self.current_project not in ['Tümü'] + self.task_manager.projects:
            self.current_project = 'Tümü'
        self._refresh_project_tabs()
        self._refresh_tasks()

    # Cloud sync

    def _apply_cloud_config(self):
        config = cloud_sync.get_config(self.task_manager)
        if config and config.get('enabled'):
            self.cloud_timer.start()
            self._set_cloud_status({'state': 'syncing', 'message': 'Eşitleniyor...'})
            QTimer.singleShot(500, self.start_cloud_sync)
        else:
            self.cloud_timer.stop()
            self._set_cloud_status({'state': 'off', 'message': 'Bulut senkronu kapalı.'})

    def set_cloud_config(self, config):
        self.task_manager.settings[cloud_sync.SETTING] = config
        self.task_manager.save()
        self._cloud_synced_change = None
        self._apply_cloud_config()

    def start_cloud_sync(self, force=False):
        if self._cloud_running:
            return
        if not force and not self.cloud_timer.isActive():
            return
        if force:
            config = cloud_sync.get_config(self.task_manager)
            if not (config and config.get('enabled')):
                return
            self._set_cloud_status({'state': 'syncing', 'message': 'Eşitleniyor...'})
        self._cloud_running = True
        cloud, db_file, relay = self.cloud, self.task_manager.db_file, self.cloud_relay

        def work():
            try:
                status = cloud.run()
                status['change'] = cloud_sync.change_counter(db_file)
            except Exception as exc:  # Never let a worker failure stop future syncs.
                status = {'state': 'offline', 'message': 'Eşitlenemedi: {}'.format(exc)}
            relay.status.emit(status)
        threading.Thread(target=work, daemon=True).start()

    def _on_cloud_status(self, status):
        self._cloud_running = False
        if 'change' in status:
            self._cloud_synced_change = status['change']
        if status['state'] == 'signed_out' and self.cloud_status.get('state') != 'signed_out':
            self.tray_icon.showMessage('TaskFlow', status['message'], QSystemTrayIcon.Warning, 6000)
        if status['state'] in ('off', 'signed_out'):
            self.cloud_timer.stop()
        self._set_cloud_status(status)
        self._poll_external_changes()

    def _set_cloud_status(self, status):
        self.cloud_status = status
        color = self.CLOUD_COLORS.get(status['state'], '#71829e')
        self.cloud_btn.setIcon(make_icon('cloud', color, 20))
        tooltip = 'Bulut senkronu · ' + status['message']
        self.cloud_btn.setToolTip(tooltip)
        self.cloud_btn.setAccessibleName(tooltip)
        self.cloud_btn.setVisible(status['state'] != 'off')
        self.sparkle_lbl.setVisible(status['state'] == 'off')

    def show_cloud_dialog(self):
        if self.isHidden():
            self.show()
        CloudSyncDialog(self).exec_()

    def _notify_sync_warnings(self):
        message = '\n'.join(self.task_manager.sync_errors)
        if message and message != self._last_sync_warning:
            self.tray_icon.showMessage('TaskFlow', 'Görevler kaydedildi; OZI Brain güncellenemedi: ' + message,
                                       QSystemTrayIcon.Warning, 5000)
        self._last_sync_warning = message or None

    def _on_task_requeued(self, task_id):
        self.task_manager.requeue_task(task_id)
        self._refresh_tasks()

    def _on_task_publication(self, task_id, revision, evidence):
        task = next((t for t in self.task_manager.tasks if t['id'] == task_id), None)
        if task:
            try:
                self.task_manager.mark_published(task.get('project'), task_id, revision, evidence)
            except (ValueError, OSError, sqlite3.Error) as exc:
                CustomConfirmDialog('Yayın kaydedilemedi', str(exc), confirm_text='Tamam',
                                    is_destructive=False, parent=self, show_cancel=False).exec_()
            self._refresh_tasks()

    def _on_task_review_changed(self, task_id, required):
        self.task_manager.set_review_required(task_id, required)
        self._refresh_tasks()

    def _on_task_moved(self, task_id, target_project):
        try:
            self.task_manager.move_task_project(task_id, target_project)
        except (ValueError, OSError, sqlite3.Error) as exc:
            CustomConfirmDialog('Görev taşınamadı', str(exc), confirm_text='Tamam',
                                is_destructive=False, parent=self, show_cancel=False).exec_()
        self._refresh_tasks()

    def _refresh_tasks(self, reset_scroll=False):
        saved_scroll = 0 if reset_scroll else self.task_list_widget.verticalScrollBar().value()
        self.task_list_widget.clear()
        tasks = sorted(
            self.task_manager.get_tasks(self.current_project),
            key=lambda t: bool(t.get('completed'))
        )

        for task in tasks:
            item = QListWidgetItem()
            is_bound = bool(task.get('project') and task.get('project') in self.task_manager.bindings)
            item_widget = TaskItemWidget(task, self.task_manager.projects, is_bound=is_bound)
            item_widget.task_toggled.connect(self._on_task_toggled)
            item_widget.task_deleted.connect(self._on_task_deleted)
            item_widget.task_edited.connect(self._on_task_edited)
            item_widget.task_noted.connect(self._on_task_noted)
            item_widget.task_requeued.connect(self._on_task_requeued)
            item_widget.task_review_changed.connect(self._on_task_review_changed)
            item_widget.task_publication.connect(self._on_task_publication)
            item_widget.task_moved.connect(self._on_task_moved)

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

        def finalize():
            self._resize_task_cards()
            bar = self.task_list_widget.verticalScrollBar()
            bar.setValue(min(saved_scroll, bar.maximum()))

        bar = self.task_list_widget.verticalScrollBar()
        bar.setValue(min(saved_scroll, bar.maximum()))
        QTimer.singleShot(0, finalize)

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
        self._refresh_tasks(reset_scroll=True)

    def _on_task_toggled(self, task_id):
        task = next((t for t in self.task_manager.tasks if t['id'] == task_id), None)
        if task and task.get('completed') and (task.get('delivery') == 'published' or task.get('publication_evidence')):
            dialog = CustomConfirmDialog(
                'Yayın kaydı sıfırlanacak',
                'Bu görevin tikini kaldırmak kayıtlı yayın doğrulamasını temizler. Devam etmek istiyor musunuz?',
                confirm_text='Tiki kaldır',
                is_destructive=True,
                parent=self
            )
            if dialog.exec_() != QDialog.Accepted:
                self._refresh_tasks()
                return
        self.task_manager.toggle_task(task_id)
        self._refresh_tasks()

    def _on_task_deleted(self, task_id):
        snapshot = next((copy.deepcopy(t) for t in self.task_manager.tasks if t['id'] == task_id), None)
        if self.task_manager.delete_task(task_id) and snapshot is not None:
            self._show_undo_bar('delete', snapshot, 'Görev silindi.')
        self._refresh_tasks()

    def _show_undo_bar(self, kind, payload, message):
        self._undo_entry = (kind, payload)
        self.undo_lbl.setText(message)
        self.undo_bar.show()
        self._undo_timer.start(6000)

    def _hide_undo_bar(self):
        self._undo_timer.stop()
        self._undo_entry = None
        self.undo_bar.hide()

    def _undo_last_action(self):
        if not self._undo_entry:
            return
        kind, payload = self._undo_entry
        self._hide_undo_bar()
        if kind == 'delete':
            self.task_manager.restore_deleted_task(payload)
            self._refresh_tasks()

    def _on_task_edited(self, task_id, new_title):
        self.task_manager.edit_task(task_id, new_title)
        self._refresh_tasks()

    def _show_archive(self, project=None):
        dialog = TaskArchiveDialog(self.task_manager, project or self.current_project, self)
        dialog.exec_()
        self._refresh_tasks()

    def _confirm_clear_completed(self):
        total, completed = self.task_manager.get_stats(self.current_project)
        if completed == 0:
            return

        dialog = CustomConfirmDialog(
            "Tamamlananları Arşivle",
            f"{completed} tamamlanmış görev arşive taşınacak.\nSonuçlar korunur; görevleri arşivden geri getirebilirsiniz.",
            confirm_text="Arşivle",
            is_destructive=False,
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.task_manager.archive_completed(self.current_project)
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

    def bring_to_front(self):
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_window_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.bring_to_front()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_window_visibility()

    def closeEvent(self, event):
        event.ignore()
        self.hide_to_tray()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.undo_bar.isVisible():
                self._hide_undo_bar()
                event.accept()
                return
            if self.task_input.hasFocus():
                if self.task_input.text():
                    self.task_input.clear()
                else:
                    self.task_input.clearFocus()
                event.accept()
                return
            self.hide_to_tray()
        else:
            super().keyPressEvent(event)

    def _quit_app(self):
        self.tray_icon.hide()
        QApplication.quit()
