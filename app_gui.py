import os
import sys
from PyQt5.QtCore import Qt, QSize, QRectF, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QCheckBox, QComboBox, QSystemTrayIcon, QMenu, QAction,
    QMessageBox, QInputDialog, QFrame, QSizePolicy
)

import autostart
from task_manager import TaskManager

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

check_icon_path = get_resource_path(os.path.join('resources', 'check_mark.png')).replace('\\', '/')

HYBRID_DARK_STYLE = f"""
QMainWindow {{
    background-color: #0c1017;
}}

QWidget#CentralWidget {{
    background-color: #0c1017;
}}

/* Header */
QLabel#AppTitle {{
    color: #ffffff;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}

QPushButton.HeaderIconBtn {{
    background-color: #141a24;
    color: #8c9bb0;
    border: 1px solid #20293a;
    border-radius: 8px;
    font-size: 13px;
    font-weight: bold;
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
}}

QPushButton.HeaderIconBtn:hover {{
    background-color: #1c2433;
    color: #00f2fe;
    border-color: #00f2fe;
}}

QPushButton.HeaderIconBtn:checked {{
    background-color: #00f2fe;
    color: #081018;
    border-color: #00f2fe;
}}

/* Project Filter Tabs */
QFrame#ProjectBar {{
    background-color: transparent;
    border: none;
    padding: 0px;
}}

QPushButton.TabBtn {{
    background-color: #131822;
    color: #8fa0b5;
    border: 1px solid #202a3a;
    border-radius: 12px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton.TabBtn:hover {{
    background-color: #1a2230;
    color: #00f2fe;
    border-color: #2b394e;
}}

QPushButton.TabBtn:checked {{
    background-color: #00f2fe;
    color: #081018;
    border: 1px solid #00f2fe;
    font-weight: 700;
}}

QPushButton.AddTabBtn {{
    background-color: #131822;
    color: #8fa0b5;
    border: 1px dashed #283549;
    border-radius: 12px;
    padding: 5px 12px;
    font-size: 14px;
    font-weight: bold;
}}

QPushButton.AddTabBtn:hover {{
    background-color: #1a2230;
    color: #00f2fe;
    border-color: #00f2fe;
}}

/* Task Input Section */
QLineEdit#TaskInput {{
    background-color: #131822;
    color: #ffffff;
    border: 1px solid #202a3a;
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 13px;
    selection-background-color: #00f2fe;
    selection-color: #081018;
}}

QLineEdit#TaskInput:focus {{
    border: 1px solid #00f2fe;
    background-color: #161c28;
}}

QComboBox#ProjectSelect {{
    background-color: #131822;
    color: #d0d7de;
    border: 1px solid #202a3a;
    border-radius: 10px;
    padding: 7px 10px;
    font-size: 12px;
    font-weight: 500;
}}

QComboBox#ProjectSelect::drop-down {{
    border: none;
    padding-right: 6px;
}}

QComboBox#ProjectSelect QAbstractItemView {{
    background-color: #131822;
    color: #ffffff;
    selection-background-color: #00f2fe;
    selection-color: #081018;
    border: 1px solid #202a3a;
    outline: none;
}}

QPushButton#AddBtn {{
    background-color: #00f2fe;
    color: #081018;
    border: none;
    border-radius: 12px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#AddBtn:hover {{
    background-color: #33f5fe;
}}

QPushButton#AddBtn:pressed {{
    background-color: #00c7d1;
}}

/* Task List */
QListWidget#TaskList {{
    background-color: transparent;
    border: none;
    outline: none;
}}

QListWidget#TaskList::item {{
    background-color: #10141d;
    border: 1px solid #1c2432;
    border-radius: 10px;
    margin-bottom: 6px;
    padding: 2px;
}}

QListWidget#TaskList::item:hover {{
    background-color: #151b27;
    border-color: #2a374c;
}}

/* Checkbox */
QCheckBox {{
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid #283446;
    border-radius: 5px;
    background-color: #0c1017;
}}

QCheckBox::indicator:hover {{
    border-color: #00f2fe;
}}

QCheckBox::indicator:checked {{
    background-color: #00f2fe;
    border-color: #00f2fe;
    image: url({check_icon_path});
}}

/* Footer */
QFrame#FooterBar {{
    background-color: #090d13;
    border-top: 1px solid #171f2c;
    padding: 8px 14px;
}}

QLabel#FooterStats {{
    color: #728296;
    font-size: 11px;
    font-weight: 500;
}}

QPushButton.FooterBtn {{
    background-color: transparent;
    color: #728296;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}}

QPushButton.FooterBtn:hover {{
    color: #ff5370;
    background-color: #21151a;
}}

QPushButton#AutostartBtn {{
    color: #00f2fe;
}}

QPushButton#AutostartBtn:hover {{
    color: #33f5fe;
    background-color: #10212b;
}}

/* Scrollbar */
QScrollBar:vertical {{
    border: none;
    background: #0c1017;
    width: 5px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: #202a3a;
    min-height: 20px;
    border-radius: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background: #00f2fe;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""

PROJECT_NEON_STYLES = {
    'Genel': ('#0c1a26', '#00f2fe', '#00f2fe'),
    'İş': ('#211533', '#b388ff', '#b388ff'),
    'Kişisel': ('#0e261d', '#69f0ae', '#69f0ae'),
    'Acil': ('#2d1117', '#ff5370', '#ff5370'),
    'Dev': ('#0c1a26', '#00f2fe', '#00f2fe')
}

def get_project_neon_style(proj_name):
    if proj_name in PROJECT_NEON_STYLES:
        return PROJECT_NEON_STYLES[proj_name]
    h = sum(ord(c) for c in proj_name) % 4
    styles = [
        ('#211533', '#b388ff', '#b388ff'),
        ('#0c1a26', '#00f2fe', '#00f2fe'),
        ('#261e0e', '#ffd166', '#ffd166'),
        ('#0e261d', '#69f0ae', '#69f0ae')
    ]
    return styles[h]


class CircularProgressWidget(QWidget):
    """Draws a modern glowing circular progress ring widget (Concept 3 + Hybrid)"""
    def __init__(self, size=40, parent=None):
        super().__init__(parent)
        self.widget_size = size
        self.percentage = 0
        self.setFixedSize(size, size)
        self.setToolTip("Görev tamamlama yüzdesi")

    def set_percentage(self, val):
        self.percentage = max(0, min(100, int(val)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pen_width = 3.5
        margin = pen_width / 2.0 + 1.5
        rect = QRectF(margin, margin, self.widget_size - 2*margin, self.widget_size - 2*margin)

        # Background track arc
        bg_pen = QPen(QColor(24, 32, 45), pen_width)
        bg_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Glowing foreground progress arc
        if self.percentage > 0:
            fg_pen = QPen(QColor(0, 242, 254), pen_width)
            fg_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(fg_pen)
            start_angle = 90 * 16
            span_angle = -int(self.percentage * 3.6 * 16)
            painter.drawArc(rect, start_angle, span_angle)

        # Center percentage text
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, f"{self.percentage}%")


class TaskItemWidget(QWidget):
    task_toggled = pyqtSignal(str)
    task_deleted = pyqtSignal(str)
    task_edited = pyqtSignal(str, str)

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(10)

        # 1. Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.task.get('completed', False))
        self.checkbox.setCursor(Qt.PointingHandCursor)
        self.checkbox.stateChanged.connect(lambda: self.task_toggled.emit(self.task['id']))
        layout.addWidget(self.checkbox)

        # 2. Task title with strikethrough logic
        self.title_label = QLabel(self.task.get('title', ''))
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.title_label.setWordWrap(True)
        self._update_text_style()
        layout.addWidget(self.title_label)

        # 3. Project Neon Pill Badge
        proj = self.task.get('project', 'Genel')
        bg_col, fg_col, border_col = get_project_neon_style(proj)
        self.badge = QLabel(f" [{proj}] ")
        self.badge.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_col};
                color: {fg_col};
                border: 1px solid {border_col};
                border-radius: 6px;
                padding: 2px 7px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(self.badge)

        # 4. Delete button (subtle bin icon)
        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedSize(22, 22)
        self.del_btn.setCursor(Qt.PointingHandCursor)
        self.del_btn.setToolTip("Görevi Sil")
        self.del_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #4b586c;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38151c;
                color: #ff5370;
            }
        """)
        self.del_btn.clicked.connect(lambda: self.task_deleted.emit(self.task['id']))
        layout.addWidget(self.del_btn)

    def _update_text_style(self):
        font = self.title_label.font()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        if self.task.get('completed'):
            font.setStrikeOut(True)
            self.title_label.setFont(font)
            self.title_label.setStyleSheet("color: #4e5d72;")
        else:
            font.setStrikeOut(False)
            self.title_label.setFont(font)
            self.title_label.setStyleSheet("color: #e6edf3;")

    def mouseDoubleClickEvent(self, event):
        new_text, ok = QInputDialog.getText(
            self, "Görevi Düzenle", "Yeni görev metni:",
            text=self.task.get('title', '')
        )
        if ok and new_text.strip():
            self.task_edited.emit(self.task['id'], new_text.strip())


class FlowListApp(QMainWindow):
    def __init__(self, start_minimized=False):
        super().__init__()
        self.task_manager = TaskManager()
        self.current_project = self.task_manager.settings.get('selected_project', 'Tümü')
        self.start_minimized = start_minimized

        self._setup_window()
        self._setup_tray()
        self._setup_ui()
        self._refresh_project_tabs()
        self._refresh_tasks()
        self._update_autostart_btn_text()

        if not self.start_minimized:
            self.show()
        else:
            self.hide()
            self.tray_icon.showMessage(
                "TaskFlow Çalışıyor",
                "Uygulama arka planda sistem tepsisinde başlatıldı.",
                QSystemTrayIcon.Information,
                2000
            )

    def _setup_window(self):
        self.setWindowTitle("TaskFlow — Minimalist To-Do")
        self.setMinimumSize(440, 580)
        self.resize(480, 660)

        icon_path = get_resource_path(os.path.join('resources', 'icon.png'))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        is_top = self.task_manager.settings.get('always_on_top', False)
        if is_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.setStyleSheet(HYBRID_DARK_STYLE)

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = get_resource_path(os.path.join('resources', 'icon.png'))
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self.windowIcon())

        self.tray_icon.setToolTip("TaskFlow")

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #10141d;
                color: #e6edf3;
                border: 1px solid #1f2a3a;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #00f2fe;
                color: #081018;
                font-weight: bold;
            }
        """)

        show_action = QAction("Aç / Gizle", self)
        show_action.triggered.connect(self.toggle_window_visibility)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        self.tray_autostart_action = QAction("Windows ile Başlat", self, checkable=True)
        self.tray_autostart_action.setChecked(autostart.is_autostart_enabled())
        self.tray_autostart_action.triggered.connect(self._toggle_autostart_setting)
        tray_menu.addAction(self.tray_autostart_action)

        tray_menu.addSeparator()

        quit_action = QAction("Uygulamayı Kapat", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _setup_ui(self):
        central_widget = QWidget(self)
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 16, 18, 0)
        main_layout.setSpacing(14)

        # 1. Header Bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        # Circular Progress Ring
        self.progress_ring = CircularProgressWidget(size=40)
        header_layout.addWidget(self.progress_ring)

        # App Title
        title_lbl = QLabel("TaskFlow")
        title_lbl.setObjectName("AppTitle")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()

        # Pin (Always on top) button
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setProperty("class", "HeaderIconBtn")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(self.task_manager.settings.get('always_on_top', False))
        self.pin_btn.setToolTip("Pencereyi Her Zaman En Üstte Tut")
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.clicked.connect(self._toggle_pin)
        header_layout.addWidget(self.pin_btn)

        # Hide to tray button
        self.hide_btn = QPushButton("—")
        self.hide_btn.setProperty("class", "HeaderIconBtn")
        self.hide_btn.setToolTip("Sistem Tepsisine Gizle")
        self.hide_btn.setCursor(Qt.PointingHandCursor)
        self.hide_btn.clicked.connect(self.hide_to_tray)
        header_layout.addWidget(self.hide_btn)

        # Close button
        self.close_btn = QPushButton("✕")
        self.close_btn.setProperty("class", "HeaderIconBtn")
        self.close_btn.setToolTip("Pencereyi Kapat (Tepsiye Küçültür)")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.hide_to_tray)
        header_layout.addWidget(self.close_btn)

        main_layout.addLayout(header_layout)

        # 2. Project Filter Tabs Bar
        self.project_bar_frame = QFrame()
        self.project_bar_frame.setObjectName("ProjectBar")
        self.project_tabs_layout = QHBoxLayout(self.project_bar_frame)
        self.project_tabs_layout.setContentsMargins(0, 2, 0, 2)
        self.project_tabs_layout.setSpacing(6)
        main_layout.addWidget(self.project_bar_frame)

        # 3. Task Input Section
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)

        self.task_input = QLineEdit()
        self.task_input.setObjectName("TaskInput")
        self.task_input.setPlaceholderText("Yeni bir görev yazın... [Enter]")
        self.task_input.returnPressed.connect(self._add_task)
        input_layout.addWidget(self.task_input, 3)

        self.project_combo = QComboBox()
        self.project_combo.setObjectName("ProjectSelect")
        self.project_combo.setToolTip("Görev atanacak proje")
        input_layout.addWidget(self.project_combo, 1)

        self.add_btn = QPushButton("+ Ekle")
        self.add_btn.setObjectName("AddBtn")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.clicked.connect(self._add_task)
        input_layout.addWidget(self.add_btn)

        main_layout.addLayout(input_layout)

        # 4. Task List Widget
        self.task_list_widget = QListWidget()
        self.task_list_widget.setObjectName("TaskList")
        self.task_list_widget.setSpacing(3)
        main_layout.addWidget(self.task_list_widget)

        # 5. Footer / Status Bar
        footer_frame = QFrame()
        footer_frame.setObjectName("FooterBar")
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(14, 8, 14, 8)

        self.stats_lbl = QLabel("0 aktif görev")
        self.stats_lbl.setObjectName("FooterStats")
        footer_layout.addWidget(self.stats_lbl)

        footer_layout.addStretch()

        self.clear_btn = QPushButton("Tamamlananları Temizle")
        self.clear_btn.setProperty("class", "FooterBtn")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_completed)
        footer_layout.addWidget(self.clear_btn)

        self.autostart_btn = QPushButton("🚀 Başlangıç")
        self.autostart_btn.setObjectName("AutostartBtn")
        self.autostart_btn.setProperty("class", "FooterBtn")
        self.autostart_btn.setCursor(Qt.PointingHandCursor)
        self.autostart_btn.clicked.connect(self._toggle_autostart_setting)
        footer_layout.addWidget(self.autostart_btn)

        main_layout.addWidget(footer_frame)

    def _refresh_project_tabs(self):
        while self.project_tabs_layout.count():
            item = self.project_tabs_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # [All] tab
        all_btn = QPushButton("[All]")
        all_btn.setProperty("class", "TabBtn")
        all_btn.setCheckable(True)
        all_btn.setChecked(self.current_project == "Tümü")
        all_btn.setCursor(Qt.PointingHandCursor)
        all_btn.clicked.connect(lambda: self._select_project("Tümü"))
        self.project_tabs_layout.addWidget(all_btn)

        # Project tabs
        for proj in self.task_manager.projects:
            p_btn = QPushButton(f"[{proj}]")
            p_btn.setProperty("class", "TabBtn")
            p_btn.setCheckable(True)
            p_btn.setChecked(self.current_project == proj)
            p_btn.setCursor(Qt.PointingHandCursor)
            p_btn.clicked.connect(lambda checked, p=proj: self._select_project(p))
            if proj != 'Genel':
                p_btn.setContextMenuPolicy(Qt.CustomContextMenu)
                p_btn.customContextMenuRequested.connect(lambda pos, p=proj: self._show_project_menu(p))
            self.project_tabs_layout.addWidget(p_btn)

        # Add Project Button
        add_p_btn = QPushButton("+")
        add_p_btn.setProperty("class", "AddTabBtn")
        add_p_btn.setToolTip("Yeni Proje Sekmesi Ekle")
        add_p_btn.setCursor(Qt.PointingHandCursor)
        add_p_btn.clicked.connect(self._prompt_add_project)
        self.project_tabs_layout.addWidget(add_p_btn)

        self.project_tabs_layout.addStretch()

        # Update combo box
        self.project_combo.clear()
        for p in self.task_manager.projects:
            self.project_combo.addItem(p)
        if self.current_project in self.task_manager.projects:
            self.project_combo.setCurrentText(self.current_project)

    def _select_project(self, proj_name):
        self.current_project = proj_name
        self.task_manager.settings['selected_project'] = proj_name
        self.task_manager.save()
        self._refresh_project_tabs()
        self._refresh_tasks()

    def _prompt_add_project(self):
        name, ok = QInputDialog.getText(self, "Yeni Proje", "Proje / Kategori Adı:")
        if ok and name.strip():
            proj_name = name.strip()
            if self.task_manager.add_project(proj_name):
                self._select_project(proj_name)
            else:
                QMessageBox.information(self, "Bilgi", "Bu proje adı zaten mevcut!")

    def _show_project_menu(self, proj_name):
        menu = QMenu(self)
        del_act = menu.addAction(f"'{proj_name}' Projesini Sil")
        action = menu.exec_(self.cursor().pos())
        if action == del_act:
            reply = QMessageBox.question(
                self, "Projeyi Sil",
                f"'{proj_name}' projesini silmek istediğinize emin misiniz?\n(İçindeki görevler 'Genel'e aktarılacaktır)",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.task_manager.delete_project(proj_name)
                self._select_project("Tümü")

    def _refresh_tasks(self):
        self.task_list_widget.clear()
        tasks = self.task_manager.get_tasks(self.current_project)

        for task in tasks:
            item = QListWidgetItem(self.task_list_widget)
            item_widget = TaskItemWidget(task)
            item_widget.task_toggled.connect(self._on_task_toggled)
            item_widget.task_deleted.connect(self._on_task_deleted)
            item_widget.task_edited.connect(self._on_task_edited)

            item.setSizeHint(item_widget.sizeHint())
            self.task_list_widget.addItem(item)
            self.task_list_widget.setItemWidget(item, item_widget)

        total, completed = self.task_manager.get_stats(self.current_project)
        active = total - completed

        # Update circular progress
        percent = int((completed / total) * 100) if total > 0 else 0
        self.progress_ring.set_percentage(percent)

        if self.current_project == "Tümü":
            self.stats_lbl.setText(f"{active} aktif görev  •  Tepsi Aktif")
        else:
            self.stats_lbl.setText(f"[{self.current_project}] {active} aktif  •  Tepsi Aktif")

        all_total, all_completed = self.task_manager.get_stats("Tümü")
        all_active = all_total - all_completed
        self.tray_icon.setToolTip(f"TaskFlow ({all_active} aktif görev)")

    def _add_task(self):
        title = self.task_input.text().strip()
        if not title:
            return

        proj = self.project_combo.currentText()
        if not proj:
            proj = "Genel"

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

    def _clear_completed(self):
        self.task_manager.clear_completed(self.current_project)
        self._refresh_tasks()

    def _toggle_pin(self):
        is_checked = self.pin_btn.isChecked()
        self.task_manager.settings['always_on_top'] = is_checked
        self.task_manager.save()
        if is_checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()

    def _toggle_autostart_setting(self):
        new_state = autostart.toggle_autostart()
        self.task_manager.settings['autostart'] = new_state
        self.task_manager.save()
        self.tray_autostart_action.setChecked(new_state)
        self._update_autostart_btn_text()

        msg = "TaskFlow artık Windows başlangıcında sessizce açılacak." if new_state else "Windows başlangıcından kaldırıldı."
        self.tray_icon.showMessage("Başlangıç Ayarı", msg, QSystemTrayIcon.Information, 1500)

    def _update_autostart_btn_text(self):
        enabled = autostart.is_autostart_enabled()
        self.tray_autostart_action.setChecked(enabled)
        if enabled:
            self.autostart_btn.setText("🚀 Başlangıç: Açık")
            self.autostart_btn.setStyleSheet("color: #00f2fe;")
        else:
            self.autostart_btn.setText("🚀 Başlangıç: Kapalı")
            self.autostart_btn.setStyleSheet("color: #728296;")

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