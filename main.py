import sys
import os
import json
import importlib
import ctypes
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, 
                             QVBoxLayout, QLabel, QPushButton, QDialog, 
                             QCheckBox, QDialogButtonBox, QMenuBar, QMenu)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QAction

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

def resource_path(relative_path):
    """ Získá absolutní cestu k souboru, funguje pro dev i pro PyInstaller exe """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class MasterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multitool Studio - Master App")
        self.resize(1350, 900)

        try:
            icon_path = resource_path("iconA.ico")
            self.setWindowIcon(QIcon(icon_path))
        except:
            pass

        # Vytvoření přepínače (Záložek)
        self.tabs = QTabWidget()

        # Moderní CSS stylování pro záložky (menší a kompaktnější)
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 6px 10px;
                font-weight: bold;
                font-size: 12px;
                background-color: #e0e0e0;
                border: 1px solid #c0c0c0;
                border-bottom-color: #c0c0c0;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                border-bottom-color: #ffffff;
                color: #2e7d32;
            }
            QTabBar::tab:hover {
                background-color: #f0f0f0;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                top: -1px;
            }
        """)

        # LAZY LOADING - Definice všech modulů, které se načtou až po kliknutí
        self.tab_classes = [
            ("📄 A: Sazba Karet a DXF", "tools.app_card_imposer", "CardStudioApp"),
            ("🎯 B: Laser - Detekce Křivek", "tools.app_laser_dxf", "ModernLaserGUI"),
            ("🖼️ C: Generátor Karet z Dat", "tools.app_card_generator", "CardGeneratorApp"),
            ("🏷️ D: Sazba Žetonů/Samolepek", "tools.app_sticker_imposer", "StickerImposerApp"),
            ("✂️ E: Sprite Slicer", "tools.app_sprite_slicer", "SlicerStudioApp"),
            ("📦 F: Generátor Krabiček", "tools.app_box_generator", "BoxGeneratorApp"),
            ("⬡ G: Sazba Hexagonů", "tools.app_hex_imposer", "HexImposerApp"),
            ("🖌️ H: Vizuální Editor (BETA)", "tools.app_visual_editor", "VisualEditorApp"),
            ("📑 I: PDF Imposer (Vektorový)", "tools.app_pdf_imposer", "PdfImposerApp")
        ]

        self.loaded_apps = [None] * len(self.tab_classes)
        
        # Načtení konfigurace (viditelnosti)
        self.config = load_config()
        self.enabled_modules = self.config.get("enabled_modules", [True] * len(self.tab_classes))
        while len(self.enabled_modules) < len(self.tab_classes):
            self.enabled_modules.append(True)

        for index, (title, module, cls_name) in enumerate(self.tab_classes):
            placeholder = QWidget()
            layout = QVBoxLayout(placeholder)
            label = QLabel(f"Načítám modul...\n(Kliknutím sem nebo na jinou záložku se modul zaktivuje)")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 16px; color: gray;")
            layout.addWidget(label)
            self.tabs.addTab(placeholder, title)
            self.tabs.setTabVisible(index, self.enabled_modules[index])
            
        # Vytvoření hlavního systémového menu
        self._create_menu_bar()

        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self.load_tab)
        
        # Načteme rovnou první zapnutý tab
        for i in range(len(self.tab_classes)):
            if self.enabled_modules[i]:
                self.tabs.setCurrentIndex(i)
                self.load_tab(i)
                break

    def _create_menu_bar(self):
        menubar = self.menuBar()
        
        # Menu Zobrazení
        view_menu = menubar.addMenu("Zobrazení")
        settings_action = QAction("⚙️ Nastavení zobrazených modulů", self)
        settings_action.triggered.connect(self.open_settings)
        view_menu.addAction(settings_action)

    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Nastavení zobrazených modulů")
        layout = QVBoxLayout(dialog)
        
        lbl_info = QLabel("Zde můžeš skrýt moduly, které zrovna nepoužíváš.\nUšetří to místo na liště.")
        layout.addWidget(lbl_info)
        
        checkboxes = []
        for i, (title, _, _) in enumerate(self.tab_classes):
            chk = QCheckBox(title)
            chk.setChecked(self.enabled_modules[i])
            layout.addWidget(chk)
            checkboxes.append(chk)
            
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)
        
        if dialog.exec():
            for i, chk in enumerate(checkboxes):
                self.enabled_modules[i] = chk.isChecked()
                self.tabs.setTabVisible(i, self.enabled_modules[i])
            self.config["enabled_modules"] = self.enabled_modules
            save_config(self.config)

    def load_tab(self, index):
        """ Dynamicky naimportuje a spustí modul až ve chvíli, kdy uživatel otevře záložku """
        if index < 0 or index >= len(self.loaded_apps):
            return
        if self.loaded_apps[index] is not None:
            return # Tento modul už je načtený
        
        title, module_name, cls_name = self.tab_classes[index]
        
        # Vyměníme popisek na dočasném tabu za informaci, že právě probíhá import
        current_widget = self.tabs.widget(index)
        if current_widget:
            lbl = current_widget.findChild(QLabel)
            if lbl:
                lbl.setText(f"Spouštím nástroj: {title}\nProsím čekejte...")
                QApplication.processEvents() # Přinutíme UI, aby se překreslilo hned

        try:
            # Import a inicializace
            module = importlib.import_module(module_name)
            app_class = getattr(module, cls_name)
            app_instance = app_class()
            self.loaded_apps[index] = app_instance
            
            # Nahrazení placeholderu (dočasného widgetu) za plnohodnotný nástroj
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, app_instance, title)
            self.tabs.setCurrentIndex(index)
        except Exception as e:
            if current_widget:
                lbl = current_widget.findChild(QLabel)
                if lbl:
                    lbl.setText(f"Chyba při načítání modulu:\n{e}\n\nZkontroluj, zda soubor {module_name}.py existuje.")
                    lbl.setStyleSheet("font-size: 14px; color: red;")

if __name__ == "__main__":
    # Nastavení Windows Taskbar ikony
    try:
        myappid = 'jgrimdev.multitool.studio.2'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)

    # Moderní vzhled
    app.setStyle("Fusion")

    window = MasterGUI()
    window.show()

    sys.exit(app.exec())