import sys
import os
import math
import pandas as pd
from PIL import Image, ImageDraw
from io import BytesIO
import ezdxf

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QGroupBox, QLabel, QLineEdit, QComboBox, QCheckBox,
                             QPushButton, QFileDialog, QMessageBox, QScrollArea, QSizePolicy, 
                             QRadioButton, QButtonGroup, QTabWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QCursor, QIcon

# --- KONFIGURACE ---
DPI = 300
MM_TO_PX = DPI / 25.4

PAPER_SIZES = {
    "A3": (297, 420),
    "A4": (210, 297),
    "A5": (148, 210)
}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

class CardStudioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Card Imposer Studio v13 - Multi-Tab & Bleed Edition")
        self.resize(1150, 850)

        try:
            icon_path = resource_path("iconA.ico")
            self.setWindowIcon(QIcon(icon_path))
        except:
            pass

        self.df = None
        self.df2 = None
        self.generated_pages = []
        self.current_page_index = 0

        self.loaded_file_path = ""
        self.loaded_file2_path = ""
        self.images_dir_path = ""
        self.images_dir_path2 = ""

        self.setup_ui()

    def setup_ui(self):
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)

        # --- LEVÝ PANEL (Ovládání) ---
        self.left_panel_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel_widget)
        self.left_layout.setContentsMargins(10, 10, 10, 10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.left_panel_widget)
        scroll_area.setMinimumWidth(400)

        # 1. Nastavení papíru
        gb_paper = QGroupBox("1. Nastavení papíru")
        lay_paper = QVBoxLayout()

        row_format = QHBoxLayout()
        row_format.addWidget(QLabel("Formát:"))
        self.combo_paper = QComboBox()
        self.combo_paper.addItems(list(PAPER_SIZES.keys()))
        self.combo_paper.setCurrentText("A4")
        row_format.addWidget(self.combo_paper)
        lay_paper.addLayout(row_format)

        self.inp_w = self.create_input(lay_paper, "Šířka (mm):", "63")
        self.inp_h = self.create_input(lay_paper, "Výška (mm):", "88")
        self.inp_gap = self.create_input(lay_paper, "Mezera (mm):", "3")
        self.inp_radius = self.create_input(lay_paper, "Poloměr rohů (mm):", "3")

        self.chk_marks = QCheckBox("Ořezové značky")
        self.chk_marks.setChecked(True)
        lay_paper.addWidget(self.chk_marks)

        self.chk_cut = QCheckBox("Zobrazit řezací křivky v náhledu")
        self.chk_cut.setChecked(True)
        self.chk_cut.setStyleSheet("color: #d9008e;")
        lay_paper.addWidget(self.chk_cut)

        self.chk_mirror = QCheckBox("Zrcadlit rozložení pro rub (Líc k Rubu)")
        self.chk_mirror.setChecked(True)
        self.chk_mirror.setStyleSheet("color: blue;")
        lay_paper.addWidget(self.chk_mirror)

        gb_paper.setLayout(lay_paper)
        self.left_layout.addWidget(gb_paper)

        # 2. Záložky pro Líc a Rub (Data a Mapování)
        self.tabs = QTabWidget()
        
        # --- ZÁLOŽKA 1: LÍC ---
        self.tab_front = QWidget()
        lay_front = QVBoxLayout(self.tab_front)
        
        btn_dummy = QPushButton("Vytvořit testovací (Dummy) stránku")
        btn_dummy.setStyleSheet("background-color: #ffe4b5;")
        btn_dummy.clicked.connect(self.load_dummy_data)
        lay_front.addWidget(btn_dummy)
        
        btn_load_folder_front = QPushButton("Načíst všechny obrázky ze složky (LÍC)...")
        btn_load_folder_front.setStyleSheet("background-color: #b5e4ff;")
        btn_load_folder_front.clicked.connect(lambda: self.load_folder_only(is_back=False))
        lay_front.addWidget(btn_load_folder_front)

        btn_load_csv = QPushButton("Načíst tabulku (Líce)...")
        btn_load_csv.setStyleSheet("background-color: #e1e1e1;")
        btn_load_csv.clicked.connect(self.load_file)
        lay_front.addWidget(btn_load_csv)

        self.inp_data_path = QLineEdit()
        self.inp_data_path.setReadOnly(True)
        lay_front.addWidget(self.inp_data_path)

        lay_front.addWidget(QLabel("Složka obrázků (Líc):"))
        row_img_dir = QHBoxLayout()
        self.inp_img_dir = QLineEdit()
        self.inp_img_dir.setReadOnly(True)
        btn_img_dir = QPushButton("...")
        btn_img_dir.setFixedWidth(40)
        btn_img_dir.clicked.connect(self.select_image_dir)
        row_img_dir.addWidget(self.inp_img_dir)
        row_img_dir.addWidget(btn_img_dir)
        lay_front.addLayout(row_img_dir)
        
        lay_front.addWidget(QLabel("Mapování Líce:", styleSheet="font-weight: bold; margin-top: 10px;"))
        
        row_map1 = QHBoxLayout()
        col_file_lay = QVBoxLayout()
        col_file_lay.addWidget(QLabel("Soubor líce:"))
        self.combo_file = QComboBox()
        col_file_lay.addWidget(self.combo_file)
        row_map1.addLayout(col_file_lay)

        col_count_lay = QVBoxLayout()
        col_count_lay.addWidget(QLabel("Počet ks:"))
        self.combo_count = QComboBox()
        col_count_lay.addWidget(self.combo_count)
        row_map1.addLayout(col_count_lay)
        lay_front.addLayout(row_map1)

        self.inp_bleed_front = self.create_input(lay_front, "Spadávka LÍC (mm):", "0")

        lay_front.addWidget(QLabel("Bez Offsetu/Spadávky (vyřazení z tabulky):"))
        self.combo_no_offset_front = QComboBox()
        lay_front.addWidget(self.combo_no_offset_front)
        lay_front.addStretch()

        # --- ZÁLOŽKA 2: RUB ---
        self.tab_back = QWidget()
        lay_back = QVBoxLayout(self.tab_back)
        
        self.chk_enable_duplex = QCheckBox("Povolit generování zadních stran (Duplex)")
        self.chk_enable_duplex.setChecked(True)
        self.chk_enable_duplex.setStyleSheet("color: blue; font-weight: bold;")
        lay_back.addWidget(self.chk_enable_duplex)
        
        lay_back.addWidget(QLabel("Odkud načítat zadní strany:"))
        self.radio_mode_1 = QRadioButton("Z hlavní tabulky (1 společný soubor)")
        self.radio_mode_2 = QRadioButton("Z druhé tabulky (2 různé soubory)")
        self.radio_mode_1.setChecked(True)
        
        self.bg_mode = QButtonGroup()
        self.bg_mode.addButton(self.radio_mode_1)
        self.bg_mode.addButton(self.radio_mode_2)
        
        lay_back.addWidget(self.radio_mode_1)
        lay_back.addWidget(self.radio_mode_2)

        self.mode2_widget = QWidget()
        lay_mode2 = QVBoxLayout(self.mode2_widget)
        lay_mode2.setContentsMargins(0, 0, 0, 0)

        btn_load_folder_back = QPushButton("Načíst všechny obrázky ze složky (RUB)...")
        btn_load_folder_back.setStyleSheet("background-color: #b5e4ff;")
        btn_load_folder_back.clicked.connect(lambda: self.load_folder_only(is_back=True))
        lay_mode2.addWidget(btn_load_folder_back)

        btn_load_csv2 = QPushButton("Načíst 2. tabulku (Ruby)...")
        btn_load_csv2.setStyleSheet("background-color: #d1e8ff;")
        btn_load_csv2.clicked.connect(self.load_file2)
        lay_mode2.addWidget(btn_load_csv2)

        self.inp_data2_path = QLineEdit()
        self.inp_data2_path.setReadOnly(True)
        lay_mode2.addWidget(self.inp_data2_path)
        
        lay_mode2.addWidget(QLabel("Složka obrázků (Rub):"))
        row_img_dir2 = QHBoxLayout()
        self.inp_img_dir2 = QLineEdit()
        self.inp_img_dir2.setReadOnly(True)
        btn_img_dir2 = QPushButton("...")
        btn_img_dir2.setFixedWidth(40)
        btn_img_dir2.clicked.connect(self.select_image_dir2)
        row_img_dir2.addWidget(self.inp_img_dir2)
        row_img_dir2.addWidget(btn_img_dir2)
        lay_mode2.addLayout(row_img_dir2)
        
        lay_back.addWidget(self.mode2_widget)
        self.mode2_widget.setVisible(False)
        
        lay_back.addWidget(QLabel("Mapování Rubu:", styleSheet="font-weight: bold; margin-top: 10px;"))
        
        row_map2 = QHBoxLayout()
        col_back_file_lay = QVBoxLayout()
        col_back_file_lay.addWidget(QLabel("Soubor rubu:"))
        self.combo_back_file = QComboBox()
        col_back_file_lay.addWidget(self.combo_back_file)
        row_map2.addLayout(col_back_file_lay)
        
        col_back_count_lay = QVBoxLayout()
        col_back_count_lay.addWidget(QLabel("Počet ks (2. tabulka):"))
        self.combo_back_count = QComboBox()
        self.combo_back_count.setEnabled(False)
        col_back_count_lay.addWidget(self.combo_back_count)
        row_map2.addLayout(col_back_count_lay)
        lay_back.addLayout(row_map2)

        self.inp_bleed_back = self.create_input(lay_back, "Spadávka RUB (mm):", "0")

        lay_back.addWidget(QLabel("Bez Offsetu/Spadávky (vyřazení z tabulky):"))
        self.combo_no_offset_back = QComboBox()
        lay_back.addWidget(self.combo_no_offset_back)
        lay_back.addStretch()

        self.tabs.addTab(self.tab_front, "Líc (Přední strana)")
        self.tabs.addTab(self.tab_back, "Rub (Zadní strana)")
        
        self.left_layout.addWidget(self.tabs)

        self.radio_mode_1.toggled.connect(self.toggle_mode)
        self.chk_enable_duplex.toggled.connect(self.toggle_duplex)

        # Patička ovládání
        self.btn_preview = QPushButton("Generovat Náhled")
        self.btn_preview.setStyleSheet("background-color: lightblue; font-weight: bold; padding: 8px;")
        self.btn_preview.setEnabled(False)
        self.btn_preview.clicked.connect(lambda: self.generate_preview(silent=False))
        self.left_layout.addWidget(self.btn_preview)

        self.btn_save_pdf = QPushButton("Uložit PDF")
        self.btn_save_pdf.setStyleSheet("background-color: lightgreen; font-weight: bold; padding: 8px;")
        self.btn_save_pdf.setEnabled(False)
        self.btn_save_pdf.clicked.connect(self.save_pdf)
        self.left_layout.addWidget(self.btn_save_pdf)

        self.btn_save_dxf = QPushButton("Uložit DXF křivky")
        self.btn_save_dxf.setStyleSheet("background-color: #ffd700; font-weight: bold; padding: 8px;")
        self.btn_save_dxf.setEnabled(False)
        self.btn_save_dxf.clicked.connect(self.save_dxf)
        self.left_layout.addWidget(self.btn_save_dxf)

        self.splitter.addWidget(scroll_area)

        # --- PRAVÝ PANEL (Náhled) ---
        self.right_panel = QWidget()
        self.right_panel.setStyleSheet("background-color: #404040;")
        self.right_layout = QVBoxLayout(self.right_panel)

        self.nav_layout = QHBoxLayout()
        self.nav_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_prev = QPushButton("<")
        self.btn_prev.setFixedWidth(40)
        self.btn_prev.clicked.connect(self.prev_page)

        self.lbl_page = QLabel("0 / 0")
        self.lbl_page.setStyleSheet("color: white; font-weight: bold;")
        self.lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_page.setFixedWidth(80)

        self.btn_next = QPushButton(">")
        self.btn_next.setFixedWidth(40)
        self.btn_next.clicked.connect(self.next_page)

        self.nav_layout.addWidget(self.btn_prev)
        self.nav_layout.addWidget(self.lbl_page)
        self.nav_layout.addWidget(self.btn_next)

        self.right_layout.addLayout(self.nav_layout)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.right_layout.addWidget(self.preview_label)

        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([400, 750])

        self.chk_marks.stateChanged.connect(self.auto_update_preview)
        self.chk_cut.stateChanged.connect(self.auto_update_preview)
        self.chk_enable_duplex.stateChanged.connect(self.auto_update_preview)
        self.chk_mirror.stateChanged.connect(self.auto_update_preview)

    def create_input(self, layout, label_text, default_val):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setMinimumWidth(150)
        inp = QLineEdit(default_val)
        inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inp.setFixedWidth(60)
        row.addWidget(lbl)
        row.addWidget(inp)
        layout.addLayout(row)
        return inp

    def toggle_duplex(self):
        enabled = self.chk_enable_duplex.isChecked()
        self.radio_mode_1.setEnabled(enabled)
        self.radio_mode_2.setEnabled(enabled)
        self.mode2_widget.setEnabled(enabled)
        self.combo_back_file.setEnabled(enabled)
        self.combo_back_count.setEnabled(enabled and self.radio_mode_2.isChecked())
        self.combo_no_offset_back.setEnabled(enabled)
        self.inp_bleed_back.setEnabled(enabled)

    def toggle_mode(self):
        is_mode_2 = self.radio_mode_2.isChecked()
        self.mode2_widget.setVisible(is_mode_2)
        self.combo_back_count.setEnabled(is_mode_2 and self.chk_enable_duplex.isChecked())
        
        if is_mode_2:
            if self.df2 is not None:
                self.populate_back_combos(list(self.df2.columns))
            else:
                self.combo_back_file.clear()
                self.combo_back_count.clear()
                self.combo_no_offset_back.clear()
        else:
            if self.df is not None:
                self.populate_back_combos(list(self.df.columns))

    def populate_main_combos(self, columns):
        self.combo_file.blockSignals(True)
        self.combo_count.blockSignals(True)
        self.combo_no_offset_front.blockSignals(True)

        self.combo_file.clear()
        self.combo_count.clear()
        self.combo_no_offset_front.clear()

        self.combo_file.addItems(columns)
        self.combo_count.addItems(columns)
        self.combo_no_offset_front.addItem("")
        self.combo_no_offset_front.addItems(columns)

        self.combo_file.blockSignals(False)
        self.combo_count.blockSignals(False)
        self.combo_no_offset_front.blockSignals(False)

    def populate_back_combos(self, columns):
        self.combo_back_file.blockSignals(True)
        self.combo_back_count.blockSignals(True)
        self.combo_no_offset_back.blockSignals(True)
        
        self.combo_back_file.clear()
        self.combo_back_count.clear()
        self.combo_no_offset_back.clear()
        
        self.combo_back_file.addItem("")
        self.combo_back_file.addItems(columns)
        self.combo_back_count.addItems(columns)
        self.combo_no_offset_back.addItem("")
        self.combo_no_offset_back.addItems(columns)
        
        self.combo_back_file.blockSignals(False)
        self.combo_back_count.blockSignals(False)
        self.combo_no_offset_back.blockSignals(False)

    def load_dummy_data(self):
        try:
            paper_w, paper_h = PAPER_SIZES.get(self.combo_paper.currentText(), (210, 297))
            cw = float(self.inp_w.text())
            ch = float(self.inp_h.text())
            gap = float(self.inp_gap.text())

            cols = int(paper_w // (cw + gap))
            rows = int(paper_h // (ch + gap))
            total_cards = cols * rows

            if total_cards <= 0:
                QMessageBox.warning(self, "Chyba", "Zadaná karta se nevejde na papír ani jednou.")
                return

            self.df = pd.DataFrame({
                "Soubor": ["dummy_image_not_exists.png"],
                "Zadni": ["dummy_back_not_exists.png"],
                "Pocet": [total_cards],
                "Bez_Okraje": ["0"]
            })

            cols_list = list(self.df.columns)
            self.populate_main_combos(cols_list)
            self.combo_file.setCurrentText("Soubor")
            self.combo_count.setCurrentText("Pocet")
            self.combo_no_offset_front.setCurrentText("Bez_Okraje")
            
            if self.radio_mode_1.isChecked():
                self.populate_back_combos(cols_list)
                self.combo_back_file.setCurrentText("Zadni")
                self.combo_no_offset_back.setCurrentText("Bez_Okraje")

            self.inp_data_path.setText("<Testovací Dummy Stránka>")
            self.images_dir_path = ""

            self.btn_preview.setEnabled(True)
            self.generate_preview(silent=False)
        except ValueError:
            QMessageBox.critical(self, "Chyba", "Zkontrolujte, že jsou rozměry zadány čísly.")

    def load_folder_only(self, is_back=False):
        folder = QFileDialog.getExistingDirectory(self, "Vyberte složku s obrázky karet")
        if not folder: return

        valid_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
        files = [f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in valid_exts]

        if not files:
            QMessageBox.warning(self, "Info", "Ve vybrané složce nebyly nalezeny žádné podporované obrázky.")
            return

        new_df = pd.DataFrame({
            "Soubor": files,
            "Pocet": [1] * len(files),
            "Bez_Okraje": ["0"] * len(files)
        })

        cols = list(new_df.columns)
        
        if is_back:
            self.df2 = new_df
            self.images_dir_path2 = folder
            self.inp_data2_path.setText(f"<Složka: {len(files)} obrázků>")
            self.inp_img_dir2.setText(folder)
            
            self.radio_mode_2.setChecked(True)
            self.populate_back_combos(cols)
            self.combo_back_file.setCurrentText("Soubor")
            self.combo_back_count.setCurrentText("Pocet")
            self.combo_no_offset_back.setCurrentText("Bez_Okraje")
        else:
            self.df = new_df
            self.images_dir_path = folder
            self.inp_data_path.setText(f"<Složka: {len(files)} obrázků>")
            self.inp_img_dir.setText(folder)
            
            self.populate_main_combos(cols)
            self.combo_file.setCurrentText("Soubor")
            self.combo_count.setCurrentText("Pocet")
            self.combo_no_offset_front.setCurrentText("Bez_Okraje")

        if self.df is not None:
            self.btn_preview.setEnabled(True)
            self.generate_preview(silent=False)

    def load_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Vybrat tabulku (Líc)", "", "Data (*.csv *.xlsx *.xls)")
        if not f: return

        self.loaded_file_path = f
        self.inp_data_path.setText(f)

        if not self.images_dir_path:
            self.images_dir_path = os.path.dirname(f)
            self.inp_img_dir.setText(self.images_dir_path)

        try:
            self.df = pd.read_csv(f) if f.lower().endswith('.csv') else pd.read_excel(f)
            cols = list(self.df.columns)
            self.populate_main_combos(cols)

            if self.radio_mode_1.isChecked():
                self.populate_back_combos(cols)

            for c in cols:
                cl = c.lower()
                if cl in ['file', 'soubor', 'img', 'obrazek', 'grafika', 'image', 'front', 'lic']:
                    if self.combo_file.currentText() not in cols: self.combo_file.setCurrentText(c)
                if cl in ['count', 'pocet', 'mnozstvi', 'ks', 'qty']:
                    self.combo_count.setCurrentText(c)
                if cl in ['offset', 'no_offset', 'bez_okraje', 'fix']:
                    self.combo_no_offset_front.setCurrentText(c)
                
                if self.radio_mode_1.isChecked():
                    if cl in ['back', 'zadni', 'rub', 'zadni_strana', 'back_file']:
                        self.combo_back_file.setCurrentText(c)
                    if cl in ['offset_back', 'bez_okraje_rub', 'no_offset_back']:
                        self.combo_no_offset_back.setCurrentText(c)

            self.btn_preview.setEnabled(True)
            self.generate_preview(silent=False)
        except Exception as e:
            QMessageBox.critical(self, "Chyba", str(e))

    def load_file2(self):
        f, _ = QFileDialog.getOpenFileName(self, "Vybrat 2. tabulku (Rub)", "", "Data (*.csv *.xlsx *.xls)")
        if not f: return

        self.loaded_file2_path = f
        self.inp_data2_path.setText(f)

        if not self.images_dir_path2:
            self.images_dir_path2 = os.path.dirname(f)
            self.inp_img_dir2.setText(self.images_dir_path2)

        try:
            self.df2 = pd.read_csv(f) if f.lower().endswith('.csv') else pd.read_excel(f)
            cols = list(self.df2.columns)
            self.populate_back_combos(cols)

            for c in cols:
                cl = c.lower()
                if cl in ['file', 'soubor', 'img', 'obrazek', 'grafika', 'image', 'back', 'zadni', 'rub']:
                    self.combo_back_file.setCurrentText(c)
                if cl in ['count', 'pocet', 'mnozstvi', 'ks', 'qty']:
                    self.combo_back_count.setCurrentText(c)
                if cl in ['offset', 'no_offset', 'bez_okraje', 'fix', 'offset_back', 'bez_okraje_rub', 'no_offset_back']:
                    self.combo_no_offset_back.setCurrentText(c)

            if self.df is not None:
                self.generate_preview(silent=False)
        except Exception as e:
            QMessageBox.critical(self, "Chyba", str(e))

    def select_image_dir(self):
        p = QFileDialog.getExistingDirectory(self, "Vybrat složku obrázků (Líc)")
        if p:
            self.images_dir_path = p
            self.inp_img_dir.setText(p)

    def select_image_dir2(self):
        p = QFileDialog.getExistingDirectory(self, "Vybrat složku obrázků (Rub)")
        if p:
            self.images_dir_path2 = p
            self.inp_img_dir2.setText(p)

    def render_card_image(self, full_path, target_w, target_h, is_back=False):
        if full_path and os.path.exists(full_path) and os.path.isfile(full_path):
            try:
                with Image.open(full_path) as img:
                    return img.resize((target_w, target_h), Image.Resampling.LANCZOS).convert('RGB')
            except:
                pass

        img = Image.new('RGB', (target_w, target_h), 'white')
        d = ImageDraw.Draw(img)
        color = 'blue' if is_back else 'red'
        d.rectangle([0, 0, target_w - 1, target_h - 1], outline=color, width=3)
        d.line([(0, 0), (target_w, target_h)], fill=color, width=3)
        d.line([(0, target_h), (target_w, 0)], fill=color, width=3)
        return img

    def is_offset_disabled(self, df_row, col_name):
        if not col_name: return False
        try:
            val = df_row[col_name]
            if pd.isna(val) or val is None or val == "": return False
            s_val = str(val).strip().lower()
            if s_val.endswith(".0"): s_val = s_val[:-2]
            return s_val in ['1', 'true', 'yes', 'ano', 'y', 'a']
        except:
            return False

    def generate_sheets(self):
        if self.df is None: return []
        
        col_file = self.combo_file.currentText()
        col_count = self.combo_count.currentText()
        col_no_off_front = self.combo_no_offset_front.currentText()
        
        col_back_file = self.combo_back_file.currentText()
        col_back_count = self.combo_back_count.currentText()
        col_no_off_back = self.combo_no_offset_back.currentText()

        if not col_file or not col_count:
            return []

        try:
            cw_val = float(self.inp_w.text())
            ch_val = float(self.inp_h.text())
            gap_val = float(self.inp_gap.text())
            r_px_val = float(self.inp_radius.text())
            
            bleed_val_f = float(self.inp_bleed_front.text())
            bleed_val_b = float(self.inp_bleed_back.text())
        except ValueError:
            return []

        paper_w, paper_h = PAPER_SIZES.get(self.combo_paper.currentText(), (210, 297))
        sw, sh = int(paper_w * MM_TO_PX), int(paper_h * MM_TO_PX)
        cw = int(cw_val * MM_TO_PX)
        ch = int(ch_val * MM_TO_PX)
        gap = int(gap_val * MM_TO_PX)
        
        bleed_f = int(bleed_val_f * MM_TO_PX)
        bleed_b = int(bleed_val_b * MM_TO_PX)

        if cw <= 0 or ch <= 0: return []

        cols = sw // (cw + gap)
        rows = sh // (ch + gap)
        if cols <= 0 or rows <= 0: return []

        mx = (sw - (cols * (cw + gap)) + gap) // 2
        my = (sh - (rows * (ch + gap)) + gap) // 2

        is_mirrored = self.chk_mirror.isChecked()
        is_duplex = self.chk_enable_duplex.isChecked()

        # FLATTEN FRONT
        fronts_queue = []
        for _, row in self.df.iterrows():
            try:
                cnt = int(row[col_count])
            except:
                cnt = 0
            if cnt > 0:
                fname = str(row[col_file])
                disable_offset_f = self.is_offset_disabled(row, col_no_off_front)
                for _ in range(cnt):
                    fronts_queue.append((fname, disable_offset_f))

        # FLATTEN BACK
        backs_queue = []
        if is_duplex:
            if self.radio_mode_1.isChecked():
                if col_back_file:
                    for _, row in self.df.iterrows():
                        try:
                            cnt = int(row[col_count])
                        except:
                            cnt = 0
                        if cnt > 0:
                            bname = str(row.get(col_back_file, ""))
                            disable_offset_b = self.is_offset_disabled(row, col_no_off_back)
                            for _ in range(cnt):
                                backs_queue.append((bname, disable_offset_b))
            else:
                if self.df2 is not None and col_back_file and col_back_count:
                    for _, row in self.df2.iterrows():
                        try:
                            cnt = int(row[col_back_count])
                        except:
                            cnt = 0
                        if cnt > 0:
                            bname = str(row.get(col_back_file, ""))
                            disable_offset_b = self.is_offset_disabled(row, col_no_off_back)
                            for _ in range(cnt):
                                backs_queue.append((bname, disable_offset_b))

        total_cards = len(fronts_queue)
        if total_cards == 0:
            return []

        pages = []
        curr_page = Image.new('RGB', (sw, sh), 'white')
        draw = ImageDraw.Draw(curr_page)

        if is_duplex:
            curr_back_page = Image.new('RGB', (sw, sh), 'white')
            back_draw = ImageDraw.Draw(curr_back_page)
        else:
            curr_back_page = None
            back_draw = None

        marks_on_page = []
        cc, cr = 0, 0
        img_cache = {}

        for i in range(total_cards):
            fname, disable_offset_f = fronts_queue[i]
            
            final_w_f = cw if disable_offset_f else cw + (2 * bleed_f)
            final_h_f = ch if disable_offset_f else ch + (2 * bleed_f)

            # LÍC
            cache_key_f = f"f_{fname}_{final_w_f}_{final_h_f}"
            if cache_key_f not in img_cache:
                f_path = os.path.join(self.images_dir_path, fname)
                img_cache[cache_key_f] = self.render_card_image(f_path, final_w_f, final_h_f)
            card_img = img_cache[cache_key_f]

            # RUB
            if is_duplex:
                bname, disable_offset_b = backs_queue[i] if i < len(backs_queue) else ("", False)
                final_w_b = cw if disable_offset_b else cw + (2 * bleed_b)
                final_h_b = ch if disable_offset_b else ch + (2 * bleed_b)

                cache_key_b = f"b_{bname}_{final_w_b}_{final_h_b}"
                if cache_key_b not in img_cache:
                    if bname and bname != "nan" and bname != "None":
                        b_dir = self.images_dir_path2 if self.radio_mode_2.isChecked() else self.images_dir_path
                        if not b_dir: b_dir = self.images_dir_path
                        
                        b_path = os.path.join(b_dir, bname)
                        img_cache[cache_key_b] = self.render_card_image(b_path, final_w_b, final_h_b, is_back=True)
                    else:
                        img_cache[cache_key_b] = Image.new('RGB', (final_w_b, final_h_b), 'white')
                back_card_img = img_cache[cache_key_b]

            # Fyzická pozice na líci
            x_cut = mx + cc * (cw + gap)
            y_cut = my + cr * (ch + gap)

            if disable_offset_f:
                curr_page.paste(card_img, (x_cut, y_cut))
            else:
                curr_page.paste(card_img, (x_cut - bleed_f, y_cut - bleed_f))

            if self.chk_cut.isChecked():
                r_px = int(r_px_val * MM_TO_PX)
                draw.rounded_rectangle([x_cut, y_cut, x_cut + cw, y_cut + ch],
                                       radius=r_px, outline="#d9008e", width=3)

            # Pozice na rubu
            if is_duplex:
                back_col = (cols - 1 - cc) if is_mirrored else cc
                b_x_cut = mx + back_col * (cw + gap)
                b_y_cut = my + cr * (ch + gap)

                if disable_offset_b:
                    curr_back_page.paste(back_card_img, (b_x_cut, b_y_cut))
                else:
                    curr_back_page.paste(back_card_img, (b_x_cut - bleed_b, b_y_cut - bleed_b))
                    
                if self.chk_cut.isChecked():
                    back_draw.rounded_rectangle([b_x_cut, b_y_cut, b_x_cut + cw, b_y_cut + ch],
                                                radius=r_px, outline="#d9008e", width=3)

            if self.chk_marks.isChecked():
                marks_on_page.append((x_cut, y_cut, cw, ch))

            cc += 1
            if cc >= cols:
                cc = 0
                cr += 1
                if cr >= rows:
                    for m_x, m_y, m_w, m_h in marks_on_page:
                        self.draw_crop_marks(draw, m_x, m_y, m_w, m_h)
                        if is_duplex:
                            self.draw_crop_marks(back_draw, m_x, m_y, m_w, m_h)
                    
                    marks_on_page = []
                    pages.append(curr_page)
                    if is_duplex:
                        pages.append(curr_back_page)
                        
                    curr_page = Image.new('RGB', (sw, sh), 'white')
                    draw = ImageDraw.Draw(curr_page)
                    if is_duplex:
                        curr_back_page = Image.new('RGB', (sw, sh), 'white')
                        back_draw = ImageDraw.Draw(curr_back_page)
                    cr = 0

        if cc > 0 or cr > 0:
            for m_x, m_y, m_w, m_h in marks_on_page:
                self.draw_crop_marks(draw, m_x, m_y, m_w, m_h)
                if is_duplex:
                    self.draw_crop_marks(back_draw, m_x, m_y, m_w, m_h)
            pages.append(curr_page)
            if is_duplex:
                pages.append(curr_back_page)

        return pages

    def draw_crop_marks(self, draw, x, y, w, h):
        l = 20; c = 'black'
        draw.line([(x, y), (x - l, y)], fill=c)
        draw.line([(x, y), (x, y - l)], fill=c)
        draw.line([(x + w, y), (x + w + l, y)], fill=c)
        draw.line([(x + w, y), (x + w, y - l)], fill=c)
        draw.line([(x, y + h), (x - l, y + h)], fill=c)
        draw.line([(x, y + h), (x, y + h + l)], fill=c)
        draw.line([(x + w, y + h), (x + w + l, y + h)], fill=c)
        draw.line([(x + w, y + h), (x + w, y + h + l)], fill=c)

    def auto_update_preview(self):
        if self.generated_pages and self.btn_preview.isEnabled():
            self.generate_preview(silent=True)

    def generate_preview(self, silent=False):
        if not silent: QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.generated_pages = self.generate_sheets()
            if self.generated_pages:
                if self.current_page_index >= len(self.generated_pages):
                    self.current_page_index = 0
                self.btn_save_pdf.setEnabled(True)
                self.btn_save_dxf.setEnabled(True)
                self.refresh_preview()
            else:
                self.generated_pages = []
                self.refresh_preview()
                if not silent: QMessageBox.warning(self, "Info", "Prázdný výstup nebo neplatné rozměry.")
        except Exception as e:
            if not silent: QMessageBox.critical(self, "Chyba", str(e))
        finally:
            if not silent: QApplication.restoreOverrideCursor()

    def prev_page(self):
        if self.generated_pages and self.current_page_index > 0:
            self.current_page_index -= 1
            self.refresh_preview()

    def next_page(self):
        if self.generated_pages and self.current_page_index < len(self.generated_pages) - 1:
            self.current_page_index += 1
            self.refresh_preview()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_preview()

    def refresh_preview(self):
        if not self.generated_pages:
            self.lbl_page.setText("0 / 0")
            self.preview_label.clear()
            return

        self.lbl_page.setText(f"{self.current_page_index + 1} / {len(self.generated_pages)}")
        img_to_show = self.generated_pages[self.current_page_index]

        cw = self.preview_label.width()
        ch = self.preview_label.height()
        if cw < 20 or ch < 20: return

        img_w, img_h = img_to_show.size
        scale = min((cw - 10) / img_w, (ch - 10) / img_h)
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        if new_w <= 0: return

        resized = img_to_show.resize((new_w, new_h), Image.Resampling.LANCZOS)

        bytes_io = BytesIO()
        resized.save(bytes_io, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(bytes_io.getvalue())

        self.preview_label.setPixmap(pixmap)

    def save_pdf(self):
        f, _ = QFileDialog.getSaveFileName(self, "Uložit PDF", "", "PDF (*.pdf)")
        if f and self.generated_pages:
            self.generated_pages[0].save(f, save_all=True, append_images=self.generated_pages[1:], resolution=DPI)
            QMessageBox.information(self, "Hotovo", "PDF úspěšně uloženo.")

    def save_dxf(self):
        f, _ = QFileDialog.getSaveFileName(self, "Uložit DXF", "", "AutoCAD DXF (*.dxf)")
        if not f: return

        try:
            doc = ezdxf.new('R2010')
            doc.units = ezdxf.units.MM
            msp = doc.modelspace()
            doc.layers.add(name="REZANI", color=1)

            paper_w, paper_h = PAPER_SIZES.get(self.combo_paper.currentText(), (210, 297))
            cw = float(self.inp_w.text())
            ch = float(self.inp_h.text())
            gap = float(self.inp_gap.text())
            r = float(self.inp_radius.text())

            cols = int(paper_w // (cw + gap))
            rows = int(paper_h // (ch + gap))

            mx = (paper_w - (cols * (cw + gap)) + gap) / 2
            my = (paper_h - (rows * (ch + gap)) + gap) / 2
            bulge = 0.41421356

            for r_idx in range(rows):
                for c_idx in range(cols):
                    x = mx + c_idx * (cw + gap)
                    y = my + r_idx * (ch + gap)
                    cad_y = paper_h - y - ch

                    points = [
                        (x + r, cad_y, 0, 0, 0),
                        (x + cw - r, cad_y, 0, 0, bulge),
                        (x + cw, cad_y + r, 0, 0, 0),
                        (x + cw, cad_y + ch - r, 0, 0, bulge),
                        (x + cw - r, cad_y + ch, 0, 0, 0),
                        (x + r, cad_y + ch, 0, 0, bulge),
                        (x, cad_y + ch - r, 0, 0, 0),
                        (x, cad_y + r, 0, 0, bulge)
                    ]
                    msp.add_lwpolyline(points, close=True, dxfattribs={'layer': 'REZANI'})

            grid_w = cols * cw + (cols - 1) * gap
            grid_h = rows * ch + (rows - 1) * gap

            cad_top_y = paper_h - my
            cad_bottom_y = paper_h - my - grid_h
            cad_left_x = mx
            cad_right_x = mx + grid_w
            dot_radius = 0.2

            msp.add_circle((cad_left_x, cad_top_y), radius=dot_radius, dxfattribs={'layer': 'REZANI'})
            msp.add_circle((cad_right_x, cad_top_y), radius=dot_radius, dxfattribs={'layer': 'REZANI'})
            msp.add_circle((cad_right_x, cad_bottom_y), radius=dot_radius, dxfattribs={'layer': 'REZANI'})
            msp.add_circle((cad_left_x, cad_bottom_y), radius=dot_radius, dxfattribs={'layer': 'REZANI'})

            doc.saveas(f)
            QMessageBox.information(self, "Hotovo", "DXF uloženo v jedné vrstvě.")
        except Exception as e:
            QMessageBox.critical(self, "Chyba při exportu DXF", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = CardStudioApp()
    window.show()
    sys.exit(app.exec())
