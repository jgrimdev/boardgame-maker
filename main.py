import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt6.QtGui import QIcon

# --- IMPORT TVÝCH SAMOSTATNÝCH APLIKACÍ ---
from main_A_pyqt import CardStudioApp
from main_B_pyqt import ModernLaserGUI
from main_C_pyqt import CardGeneratorApp
from main_D_pyqt import StickerImposerApp
from main_E_pyqt import SlicerStudioApp


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

        # Moderní CSS stylování pro záložky, aby vypadaly jako v profi softwaru
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 12px 20px;
                font-weight: bold;
                font-size: 14px;
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

        self.setCentralWidget(self.tabs)

        # --- 1. Načtení aplikace A (Sazba karet) ---
        self.app_a = CardStudioApp()
        self.tabs.addTab(self.app_a, "📄 A: Sazba Karet a DXF")

        # --- 2. Načtení aplikace B (Laser detekce křivek) ---
        self.app_b = ModernLaserGUI()
        self.tabs.addTab(self.app_b, "🎯 B: Laser - Detekce Křivek")

        # --- 3. Načtení aplikace C (Generátor karet z Excelu) ---
        self.app_c = CardGeneratorApp()
        self.tabs.addTab(self.app_c, "🖼️ C: Generátor Karet z Dat")

        # --- 4. Načtení aplikace D (Sticker Imposer) ---
        self.app_d = StickerImposerApp()
        self.tabs.addTab(self.app_d, "🏷️ D: Sazba Žetonů/Samolepek")

        # --- 5. Načtení aplikace E (Sticker Imposer) ---
        self.app_d = SlicerStudioApp()
        self.tabs.addTab(self.app_d, "🏷️ E: Tilemap extruder")

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Moderní vzhled (Fusion funguje skvěle na Windows i Macu)
    app.setStyle("Fusion")

    window = MasterGUI()
    window.show()

    sys.exit(app.exec())