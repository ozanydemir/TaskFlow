import os
import sys
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QCheckBox, QComboBox, QSystemTrayIcon, QMenu, QAction,
    QMessageBox, QInputDialog, QFrame, QProgressBar, QSizePolicy
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

# Modern Dark Theme QSS
DARK_STYLE = """
QMainWindow {
    background-color: #14161b;
}

QWidget#CentralWidget {
    background-color: #14161b;
}

/* Header */
QLabel#AppTitle {
    color: #ffffff;
    font-size: 17px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

QPushButton.HeaderBtn {
    background-color: #1f232b;
    color: #9aa5b5;
    border: 1px solid #2d3340;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.HeaderBtn:hover {
    background-color: #2b3240;
    color: #ffffff;
    border-color: #3e4758;
}

QPushButton.HeaderBtn:checked {
    background-color: #00b488;
    color: #ffffff;
    border-color: #00d6a2;
}

/* Project Filter Tabs Bar */
QFrame#ProjectBar {
    background-color: #1a1d24;
    border-radius: 8px;
    padding: 3px;
}

QPushButton.TabBtn {
    background-color: transparent;
    color: #8c97a8;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton.TabBtn:hover {
    background-color: #262b35;
    color: #e1e7f0;
}

QPushButton.TabBtn:checked {
    background-color: #00b488;
    color: #ffffff;
}

QPushButton.AddTabBtn {
    background-color: #222731;
    color: #8c97a8;
    border: 1px dashed #363e4f;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
    font-weight: bold;
}

QPushButton.AddTabBtn:hover {
    background-color: #2d3442;
    color: #00d6a2;
    border-color: #00d6a2;
}

/* Input Section */
QLineEdit#TaskInput {
    background-color: #1a1d24;
    color: #ffffff;
    border: 1px solid #2d3340;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    selection-background-color: #00b488;
}

QLineEdit#TaskInput:focus {
    border: 1px solid #00b488;
    background-color: #1d2129;
}

QComboBox#ProjectSelect {
    background-color: #1a1d24;
    color: #d0d7de;
    border: 1px solid #2d3340;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 500;
}

QComboBox#ProjectSelect::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox#ProjectSelect QAbstractItemView {
    background-color: #1a1d24;
    color: #ffffff;
    selection-background-color: #00b488;
    border: 1px solid #2d3340;
    outline: none;
}

QPushButton#AddBtn {
    background-color: #00b488;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#AddBtn:hover {
    background-color: #00d6a2;
}

QPushButton#AddBtn:pressed {
    background-color: #009973;
}

/* Task List */
QListWidget#TaskList {
    background-color: transparent;
    border: none;
    outline: none;
}

QListWidget#TaskList::item {
    background-color: #191c23;
    border: 1px solid #252a35;
    border-radius: 8px;
    margin-bottom: 6px;
    padding: 2px;
}

QListWidget#TaskList::item:hover {
    background-color: #1e222b;
    border-color: #343c4c;
}

/* Status Bar */
QFrame#FooterBar {
    background-color: #111317;
    border-top: 1px solid #1f232b;
    padding: 6px 14px;
}

QLabel#FooterStats {
    color: #798596;
    font-size: 11px;
    font-weight: 500;
}

QPushButton.FooterBtn {
    background-color: transparent;
    color: #798596;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}

QPushButton.FooterBtn:hover {
    color: #f85149;
    background-color: #251c20;
}

QPushButton#AutostartBtn {
    color: #798596;
}

QPushButton#AutostartBtn:hover {
    color: #58a6ff;
    background-color: #182433;
}

/* Scrollbar */
QScrollBar:vertical {
    border: none;
    background: #14161b;
    width: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #2b3240;
    min-height: 20px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #3e4758;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

PROJECT_COLORS = {
    'Genel': ('#1b324a', '#58a6ff'),
    'İş': ('#2c2447', '#bc8cff'),
    'Kişisel': ('#1f382b', '#3fb950'),
    'Acil': ('#3d1f24', '#f85149')
}

def get_project_colors(proj_name):
    if proj_name in PROJECT_COLORS:
        return PROJECT_COLORS[proj_name]
    # Deterministic palette selection
    h = sum(ord(c) for c in proj_name) % 4
    palettes = [
        ('#332617', '#d29922'),
        ('#1b324a', '#58a6ff'),
        ('#2c2447', '#bc8cff'),
        ('#1f382b', '#3fb950')
    ]
    return palettes[h]


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
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.task.get('completed', False))
        self.checkbox.setCursor(Qt.PointingHandCursor)
        self.checkbox.stateChanged.connect(lambda: self.task_toggled.emit(self.task['id']))
        layout.addWidget(self.checkbox)

        # Task text
        self.title_label = QLabel(self.task.get('title', ''))
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.title_label.setWordWrap(True)
        self._update_label_style()
        layout.addWidget(self.title_label)

        # Project badge
        proj = self.task.get('project', 'Genel')
        bg_col, fg_col = get_project_colors(proj)
        self.badge = QLabel(f" {proj} ")
        self.badge.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_col};
                color: {fg_col};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
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
                color: #5c6677;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #381e22;
                color: #f85149;
            }
        """)
        self.del_btn.clicked.connect(lambda: self.task_deleted.emit(self.task['id']))
        layout.addWidget(self.del_btn)

    def _update_label_style(self):
        if self.task.get('completed'):
            self.title_label.setStyleSheet("""
                color: #5b6575;
                font-size: 13px;
                text-decoration: line-through;
            """)
        else:
            self.title_label.setStyleSheet("""
                color: #e6edf3;
                font-size: 13px;
                font-weight: 400;
            """)

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

        # Handle start minimized
        if not self.start_minimized:
            self.show()
        else:
            self.hide()
            self.tray_icon.showMessage(
                "FlowList Çalışıyor",
                "Uygulama arka planda sistem tepsisinde başlatıldı.",
                QSystemTrayIcon.Information,
                2000
            )

    def _setup_window(self):
        self.setWindowTitle("FlowList — Minimal To-Do")
        self.setMinimumSize(440, 560)
        self.resize(480, 640)

        # Set Icon
        icon_path = get_resource_path(os.path.join('resources', 'icon.png'))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Always on top state
        is_top = self.task_manager.settings.get('always_on_top', False)
        if is_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.setStyleSheet(DARK_STYLE)

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = get_resource_path(os.path.join('resources', 'icon.png'))
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self.windowIcon())

        self.tray_icon.setToolTip("FlowList To-Do")

        # Tray Menu
        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #1a1d24;
                color: #e6edf3;
                border: 1px solid #2d3340;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #00b488;
                color: #ffffff;
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

        # 1. Top Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        title_lbl = QLabel("FlowList")
        title_lbl.setObjectName("AppTitle")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()

        # Pin (Always on top) button
        self.pin_btn = QPushButton("📌 Sabitle")
        self.pin_btn.setProperty("class", "HeaderBtn")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(self.task_manager.settings.get('always_on_top', False))
        self.pin_btn.setToolTip("Pencereyi her zaman en üstte tut")
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.clicked.connect(self._toggle_pin)
        header_layout.addWidget(self.pin_btn)

        # Hide to tray button
        self.hide_btn = QPushButton("👁️ Gizle")
        self.hide_btn.setProperty("class", "HeaderBtn")
        self.hide_btn.setToolTip("Sistem tepsisine (sağ alta) küçült")
        self.hide_btn.setCursor(Qt.PointingHandCursor)
        self.hide_btn.clicked.connect(self.hide_to_tray)
        header_layout.addWidget(self.hide_btn)

        main_layout.addLayout(header_layout)

        # 2. Project Filter Tabs
        self.project_bar_frame = QFrame()
        self.project_bar_frame.setObjectName("ProjectBar")
        self.project_tabs_layout = QHBoxLayout(self.project_bar_frame)
        self.project_tabs_layout.setContentsMargins(4, 4, 4, 4)
        self.project_tabs_layout.setSpacing(6)
        main_layout.addWidget(self.project_bar_frame)

        # 3. Task Input Section
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)

        self.task_input = QLineEdit()
        self.task_input.setObjectName("TaskInput")
        self.task_input.setPlaceholderText("Yeni görev yazın... (Enter)")
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
        self.task_list_widget.setSpacing(4)
        main_layout.addWidget(self.task_list_widget)

        # 5. Footer / Status Bar
        footer_frame = QFrame()
        footer_frame.setObjectName("FooterBar")
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(14, 8, 14, 8)

        self.stats_lbl = QLabel("0 görev")
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
        # Clear existing tabs in layout
        while self.project_tabs_layout.count():
            item = self.project_tabs_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # "Tümü" tab
        all_btn = QPushButton("Tümü")
        all_btn.setProperty("class", "TabBtn")
        all_btn.setCheckable(True)
        all_btn.setChecked(self.current_project == "Tümü")
        all_btn.setCursor(Qt.PointingHandCursor)
        all_btn.clicked.connect(lambda: self._select_project("Tümü"))
        self.project_tabs_layout.addWidget(all_btn)

        # Project tabs
        for proj in self.task_manager.projects:
            p_btn = QPushButton(proj)
            p_btn.setProperty("class", "TabBtn")
            p_btn.setCheckable(True)
            p_btn.setChecked(self.current_project == proj)
            p_btn.setCursor(Qt.PointingHandCursor)
            p_btn.clicked.connect(lambda checked, p=proj: self._select_project(p))
            # Right click context menu to delete custom projects
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
        if self.current_project == "Tümü":
            self.stats_lbl.setText(f"{active} aktif görev  •  {completed} tamamlandı")
        else:
            self.stats_lbl.setText(f"[{self.current_project}] {active} aktif  •  {completed} tamamlandı")

        # Update tray tooltip with remaining tasks
        all_total, all_completed = self.task_manager.get_stats("Tümü")
        all_active = all_total - all_completed
        self.tray_icon.setToolTip(f"FlowList ({all_active} görev bekliyor)")

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

        msg = "FlowList artık Windows başlangıcında sessizce açılacak." if new_state else "Windows başlangıcından kaldırıldı."
        self.tray_icon.showMessage("Başlangıç Ayarı", msg, QSystemTrayIcon.Information, 1500)

    def _update_autostart_btn_text(self):
        enabled = autostart.is_autostart_enabled()
        self.tray_autostart_action.setChecked(enabled)
        if enabled:
            self.autostart_btn.setText("🚀 Başlangıç: Açık")
            self.autostart_btn.setStyleSheet("color: #3fb950;")
        else:
            self.autostart_btn.setText("🚀 Başlangıç: Kapalı")
            self.autostart_btn.setStyleSheet("color: #798596;")

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
        # Instead of quitting, minimize to tray
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