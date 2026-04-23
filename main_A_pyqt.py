import sys
import os
import math
import pandas as pd
from PIL import Image, ImageDraw
from io import BytesIO
import ezdxf

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QGroupBox, QLabel, QLineEdit, QComboBox, QCheckBox,
                             QPushButton, QFileDialog, QMessageBox, QScrollArea, QSizePolicy)
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
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class CardStudioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Card Imposer Studio v10.2 - Instant Checkbox Preview")
        self.resize(1150, 850)

        try:
            icon_path = resource_path("iconA.ico")
            self.setWindowIcon(QIcon(icon_path))
        except:
            pass

        self.df = None
        self.generated_pages = []
        self.current_page_index = 0

        self.loaded_file_path = ""
        self.images_dir_path = ""

        self.setup_ui()

    def setup_ui(self):
        # Hlavní rozdělovník okna (Splitter)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)

        # --- LEVÝ PANEL (Ovládání) ---
        self.left_panel_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel_widget)
        self.left_layout.setContentsMargins(10, 10, 10, 10)

        # Aby šel levý panel scrollovat na malých monitorech
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.left_panel_widget)
        scroll_area.setMinimumWidth(380)

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
        self.inp_bleed = self.create_input(lay_paper, "Spadávka (mm):", "0")
        self.inp_radius = self.create_input(lay_paper, "Poloměr rohů (mm):", "3")

        self.chk_marks = QCheckBox("Ořezové značky")
        self.chk_marks.setChecked(True)
        lay_paper.addWidget(self.chk_marks)

        self.chk_cut = QCheckBox("Zobrazit řezací křivky v náhledu")
        self.chk_cut.setChecked(True)
        self.chk_cut.setStyleSheet("color: #d9008e;")
        lay_paper.addWidget(self.chk_cut)

        self.chk_mirror = QCheckBox("Zrcadlit rozložení (Zadní str.)")
        self.chk_mirror.setStyleSheet("color: blue;")
        lay_paper.addWidget(self.chk_mirror)

        gb_paper.setLayout(lay_paper)
        self.left_layout.addWidget(gb_paper)

        # 2. Data a Obrázky
        gb_data = QGroupBox("2. Data a Obrázky")
        lay_data = QVBoxLayout()

        btn_dummy = QPushButton("Vytvořit testovací (Dummy) stránku")
        btn_dummy.setStyleSheet("background-color: #ffe4b5;")
        btn_dummy.clicked.connect(self.load_dummy_data)
        lay_data.addWidget(btn_dummy)

        btn_load_csv = QPushButton("Načíst CSV/Excel tabulku...")
        btn_load_csv.setStyleSheet("background-color: #e1e1e1;")
        btn_load_csv.clicked.connect(self.load_file)
        lay_data.addWidget(btn_load_csv)

        btn_load_folder = QPushButton("Načíst všechny obrázky ze složky (1 ks)")
        btn_load_folder.setStyleSheet("background-color: #b5e4ff;")
        btn_load_folder.clicked.connect(self.load_folder_only)
        lay_data.addWidget(btn_load_folder)

        lay_data.addWidget(QLabel("Soubor dat:"))
        self.inp_data_path = QLineEdit()
        self.inp_data_path.setReadOnly(True)
        lay_data.addWidget(self.inp_data_path)

        lay_data.addWidget(QLabel("Složka obrázků:"))
        row_img_dir = QHBoxLayout()
        self.inp_img_dir = QLineEdit()
        self.inp_img_dir.setReadOnly(True)
        btn_img_dir = QPushButton("...")
        btn_img_dir.setFixedWidth(40)
        btn_img_dir.clicked.connect(self.select_image_dir)
        row_img_dir.addWidget(self.inp_img_dir)
        row_img_dir.addWidget(btn_img_dir)
        lay_data.addLayout(row_img_dir)

        gb_data.setLayout(lay_data)
        self.left_layout.addWidget(gb_data)

        # 3. Mapování
        gb_map = QGroupBox("3. Mapování sloupců")
        lay_map = QVBoxLayout()

        row_map1 = QHBoxLayout()

        col_file_lay = QVBoxLayout()
        col_file_lay.addWidget(QLabel("Obrázek (Soubor):"))
        self.combo_file = QComboBox()
        col_file_lay.addWidget(self.combo_file)
        row_map1.addLayout(col_file_lay)

        col_count_lay = QVBoxLayout()
        col_count_lay.addWidget(QLabel("Množství (Počet):"))
        self.combo_count = QComboBox()
        col_count_lay.addWidget(self.combo_count)
        row_map1.addLayout(col_count_lay)

        lay_map.addLayout(row_map1)

        lay_map.addWidget(QLabel("Bez Offsetu/Spadávky (volitelné):"))
        self.combo_no_offset = QComboBox()
        lay_map.addWidget(self.combo_no_offset)
        lbl_hint = QLabel("(1, ano, true = žádná spadávka)")
        lbl_hint.setStyleSheet("color: #666; font-size: 10px;")
        lay_map.addWidget(lbl_hint)

        gb_map.setLayout(lay_map)
        self.left_layout.addWidget(gb_map)

        # Mezera pro roztáhnutí panelu
        self.left_layout.addStretch()

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

        # Navigace stran
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

        # Náhledový obrázek
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.right_layout.addWidget(self.preview_label)

        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([380, 720])

        # --- NAPOJENÍ NA OKAMŽITÝ ŽIVÝ NÁHLED (Pouze pro Checkboxy) ---
        self.chk_marks.stateChanged.connect(self.auto_update_preview)
        self.chk_cut.stateChanged.connect(self.auto_update_preview)
        self.chk_mirror.stateChanged.connect(self.auto_update_preview)

    def create_input(self, layout, label_text, default_val):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setMinimumWidth(130)
        inp = QLineEdit(default_val)
        inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inp.setFixedWidth(60)
        row.addWidget(lbl)
        row.addWidget(inp)
        layout.addLayout(row)
        return inp

    # --- LOGIKA NAČÍTÁNÍ ---
    def populate_combos(self, columns):
        self.combo_file.blockSignals(True)
        self.combo_count.blockSignals(True)
        self.combo_no_offset.blockSignals(True)

        self.combo_file.clear()
        self.combo_count.clear()
        self.combo_no_offset.clear()

        self.combo_file.addItems(columns)
        self.combo_count.addItems(columns)
        self.combo_no_offset.addItem("")
        self.combo_no_offset.addItems(columns)

        self.combo_file.blockSignals(False)
        self.combo_count.blockSignals(False)
        self.combo_no_offset.blockSignals(False)

    def load_folder_only(self):
        folder = QFileDialog.getExistingDirectory(self, "Vyberte složku s obrázky karet")
        if not folder: return

        valid_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
        files = [f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in valid_exts]

        if not files:
            QMessageBox.warning(self, "Info", "Ve vybrané složce nebyly nalezeny žádné podporované obrázky.")
            return

        self.df = pd.DataFrame({
            "Soubor": files,
            "Pocet": [1] * len(files),
            "Bez_Okraje": ["0"] * len(files)
        })

        self.images_dir_path = folder
        self.inp_data_path.setText(f"<Složka: {len(files)} obrázků>")
        self.inp_img_dir.setText(folder)

        cols = list(self.df.columns)
        self.populate_combos(cols)
        self.combo_file.setCurrentText("Soubor")
        self.combo_count.setCurrentText("Pocet")
        self.combo_no_offset.setCurrentText("Bez_Okraje")

        self.btn_preview.setEnabled(True)
        self.generate_preview(silent=False)

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
                "Pocet": [total_cards],
                "Bez_Okraje": ["0"]
            })

            cols_list = list(self.df.columns)
            self.populate_combos(cols_list)
            self.combo_file.setCurrentText("Soubor")
            self.combo_count.setCurrentText("Pocet")
            self.combo_no_offset.setCurrentText("Bez_Okraje")

            self.inp_data_path.setText("<Testovací Dummy Stránka>")
            self.images_dir_path = ""

            self.btn_preview.setEnabled(True)
            self.generate_preview(silent=False)
        except ValueError:
            QMessageBox.critical(self, "Chyba", "Zkontrolujte, že jsou rozměry zadány čísly.")

    def load_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Vybrat tabulku", "", "Data (*.csv *.xlsx *.xls)")
        if not f: return

        self.loaded_file_path = f
        self.inp_data_path.setText(f)

        if not self.images_dir_path:
            self.images_dir_path = os.path.dirname(f)
            self.inp_img_dir.setText(self.images_dir_path)

        try:
            self.df = pd.read_csv(f) if f.lower().endswith('.csv') else pd.read_excel(f)
            cols = list(self.df.columns)
            self.populate_combos(cols)

            for c in cols:
                cl = c.lower()
                if cl in ['file', 'soubor', 'img', 'obrazek', 'grafika', 'image']: self.combo_file.setCurrentText(c)
                if cl in ['count', 'pocet', 'mnozstvi', 'ks', 'qty']: self.combo_count.setCurrentText(c)
                if cl in ['offset', 'no_offset', 'bez_okraje', 'fix']: self.combo_no_offset.setCurrentText(c)

            self.btn_preview.setEnabled(True)
            self.generate_preview(silent=False)
        except Exception as e:
            QMessageBox.critical(self, "Chyba", str(e))

    def select_image_dir(self):
        p = QFileDialog.getExistingDirectory(self, "Vybrat složku obrázků")
        if p:
            self.images_dir_path = p
            self.inp_img_dir.setText(p)

    def render_card_image(self, full_path, target_w, target_h):
        if full_path and os.path.exists(full_path) and os.path.isfile(full_path):
            try:
                with Image.open(full_path) as img:
                    return img.resize((target_w, target_h), Image.Resampling.LANCZOS).convert('RGB')
            except:
                pass

        img = Image.new('RGB', (target_w, target_h), 'white')
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, target_w - 1, target_h - 1], outline='red', width=3)
        d.line([(0, 0), (target_w, target_h)], fill='red', width=3)
        d.line([(0, target_h), (target_w, 0)], fill='red', width=3)
        return img

    def is_offset_disabled(self, row, col_name):
        if not col_name: return False
        try:
            val = row[col_name]
            if pd.isna(val) or val is None or val == "": return False
            s_val = str(val).strip().lower()
            if s_val.endswith(".0"): s_val = s_val[:-2]
            return s_val in ['1', 'true', 'yes', 'ano', 'y', 'a']
        except:
            return False

    # --- JÁDRO GENERÁTORU ---
    def generate_sheets(self):
        if self.df is None: return []
        col_file = self.combo_file.currentText()
        col_count = self.combo_count.currentText()
        col_no_off = self.combo_no_offset.currentText()

        if not col_file or not col_count:
            return []

        try:
            cw_val = float(self.inp_w.text())
            ch_val = float(self.inp_h.text())
            gap_val = float(self.inp_gap.text())
            bleed_val = float(self.inp_bleed.text())
            r_px_val = float(self.inp_radius.text())
        except ValueError:
            return []  # Uživateli se zrovna v políčku objevilo prázdno (maže text), ignorujeme

        paper_w, paper_h = PAPER_SIZES.get(self.combo_paper.currentText(), (210, 297))
        sw, sh = int(paper_w * MM_TO_PX), int(paper_h * MM_TO_PX)
        cw = int(cw_val * MM_TO_PX)
        ch = int(ch_val * MM_TO_PX)
        gap = int(gap_val * MM_TO_PX)
        bleed = int(bleed_val * MM_TO_PX)

        if cw <= 0 or ch <= 0: return []

        cols = sw // (cw + gap)
        rows = sh // (ch + gap)
        if cols <= 0 or rows <= 0: return []

        mx = (sw - (cols * (cw + gap)) + gap) // 2
        my = (sh - (rows * (ch + gap)) + gap) // 2

        is_mirrored = self.chk_mirror.isChecked()
        pages = []
        curr_page = Image.new('RGB', (sw, sh), 'white')
        draw = ImageDraw.Draw(curr_page)

        marks_on_page = []
        cc, cr = 0, 0

        for _, row in self.df.iterrows():
            try:
                cnt = int(row[col_count])
            except:
                cnt = 0

            if cnt > 0:
                fname = str(row[col_file])
                full_path = os.path.join(self.images_dir_path, fname)

                disable_offset = self.is_offset_disabled(row, col_no_off)
                final_w = cw if disable_offset else cw + (2 * bleed)
                final_h = ch if disable_offset else ch + (2 * bleed)

                card_img = self.render_card_image(full_path, final_w, final_h)

                for _ in range(cnt):
                    final_col = (cols - 1 - cc) if is_mirrored else cc
                    x_cut = mx + final_col * (cw + gap)
                    y_cut = my + cr * (ch + gap)

                    if disable_offset:
                        curr_page.paste(card_img, (x_cut, y_cut))
                    else:
                        curr_page.paste(card_img, (x_cut - bleed, y_cut - bleed))

                    if self.chk_cut.isChecked():
                        r_px = int(r_px_val * MM_TO_PX)
                        draw.rounded_rectangle([x_cut, y_cut, x_cut + cw, y_cut + ch],
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
                            marks_on_page = []
                            pages.append(curr_page)
                            curr_page = Image.new('RGB', (sw, sh), 'white')
                            draw = ImageDraw.Draw(curr_page)
                            cr = 0

        if cc > 0 or cr > 0:
            for m_x, m_y, m_w, m_h in marks_on_page:
                self.draw_crop_marks(draw, m_x, m_y, m_w, m_h)
            pages.append(curr_page)

        return pages

    def draw_crop_marks(self, draw, x, y, w, h):
        l = 20;
        c = 'black'
        draw.line([(x, y), (x - l, y)], fill=c)
        draw.line([(x, y), (x, y - l)], fill=c)
        draw.line([(x + w, y), (x + w + l, y)], fill=c)
        draw.line([(x + w, y), (x + w, y - l)], fill=c)
        draw.line([(x, y + h), (x - l, y + h)], fill=c)
        draw.line([(x, y + h), (x, y + h + l)], fill=c)
        draw.line([(x + w, y + h), (x + w + l, y + h)], fill=c)
        draw.line([(x + w, y + h), (x + w, y + h + l)], fill=c)

    def auto_update_preview(self):
        # Spustí se okamžitě jen pokud je už něco vygenerované a svítí tlačítko
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

    # --- EXPORT ---
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
            QMessageBox.information(self, "Hotovo",
                                    f"DXF uloženo v jedné vrstvě.\n\nJsou v něm řezy karet a 4 zaměřovací tečky v rozích ořezových značek.")

        except Exception as e:
            QMessageBox.critical(self, "Chyba při exportu DXF", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = CardStudioApp()
    window.show()
    sys.exit(app.exec())