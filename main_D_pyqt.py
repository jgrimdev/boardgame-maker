import sys
import os
import random
from PIL import Image, ImageDraw
from io import BytesIO
import ezdxf

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QGroupBox, QLabel, QLineEdit, QCheckBox, QComboBox,
                             QPushButton, QFileDialog, QMessageBox, QScrollArea, QSizePolicy,
                             QTableWidget, QTableWidgetItem, QSpinBox, QDoubleSpinBox, QHeaderView)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

# --- KONFIGURACE ---
DPI = 300
MM_TO_PX = DPI / 25.4

PAPER_SIZES = {
    "A3": (297, 420),
    "A4": (210, 297),
    "A5": (148, 210)
}


class StickerImposerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sticker Imposer v3.1 - Zámek poměru & Náhodné žetony")
        self.resize(1250, 850)

        self.loaded_images = []  # path, name, w_px, h_px, dummy, color
        self.generated_pages = []
        self.pages_layout_data = []
        self.current_page_index = 0

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
        scroll_area.setMinimumWidth(480)

        # 1. Nastavení papíru
        gb_paper = QGroupBox("1. Nastavení rozvržení")
        lay_paper = QVBoxLayout()

        row_format = QHBoxLayout()
        row_format.addWidget(QLabel("Formát papíru:"))
        self.combo_paper = QComboBox()
        self.combo_paper.addItems(list(PAPER_SIZES.keys()))
        self.combo_paper.setCurrentText("A4")
        row_format.addWidget(self.combo_paper)
        lay_paper.addLayout(row_format)

        self.inp_margin = self.create_input(lay_paper, "Bezpečný okraj (mm):", "10")
        self.inp_gap = self.create_input(lay_paper, "Mezera mezi (mm):", "3")
        self.inp_bleed = self.create_input(lay_paper, "Spadávka (mm):", "0")
        self.inp_radius = self.create_input(lay_paper, "Poloměr rohů (mm):", "3")

        self.chk_marks = QCheckBox("Křížky (Ořezové značky)")
        self.chk_marks.setChecked(True)
        self.chk_marks.stateChanged.connect(self.auto_update_preview)
        lay_paper.addWidget(self.chk_marks)

        self.chk_cut = QCheckBox("Zobrazit řezací křivky v náhledu")
        self.chk_cut.setChecked(True)
        self.chk_cut.setStyleSheet("color: #d9008e;")
        self.chk_cut.stateChanged.connect(self.auto_update_preview)
        lay_paper.addWidget(self.chk_cut)

        gb_paper.setLayout(lay_paper)
        self.left_layout.addWidget(gb_paper)

        # 2. Data a Obrázky
        gb_data = QGroupBox("2. Obrázky a rozměry")
        lay_data = QVBoxLayout()

        btn_dummy = QPushButton("Přidat náhodný testovací žeton")
        btn_dummy.setStyleSheet("background-color: #ffe4b5;")
        btn_dummy.clicked.connect(self.load_dummy_data)
        lay_data.addWidget(btn_dummy)

        btn_load = QPushButton("Vybrat obrázky...")
        btn_load.setStyleSheet("background-color: #b5e4ff; font-weight: bold;")
        btn_load.clicked.connect(self.load_files)
        lay_data.addWidget(btn_load)

        self.chk_lock_ratio = QCheckBox("Zachovat poměr stran při změně rozměru")
        self.chk_lock_ratio.setChecked(True)
        lay_data.addWidget(self.chk_lock_ratio)

        # Tabulka
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Náhled", "Soubor", "Šířka (mm)", "Výška (mm)", "Počet"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(60)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(2, 75)
        self.table.setColumnWidth(3, 75)
        self.table.setColumnWidth(4, 60)
        lay_data.addWidget(self.table)

        gb_data.setLayout(lay_data)
        self.left_layout.addWidget(gb_data)

        self.left_layout.addStretch()

        # Patička ovládání
        self.btn_preview = QPushButton("Generovat / Přepočítat")
        self.btn_preview.setStyleSheet("background-color: lightblue; font-weight: bold; padding: 10px;")
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
        self.btn_prev = QPushButton("<")
        self.btn_prev.clicked.connect(self.prev_page)
        self.lbl_page = QLabel("0 / 0")
        self.lbl_page.setStyleSheet("color: white; font-weight: bold;")
        self.lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_next = QPushButton(">")
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
        self.splitter.setSizes([480, 750])

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
    def load_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Vyberte obrázky", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if not files: return

        for full_path in files:
            try:
                with Image.open(full_path) as img:
                    w, h = img.size
                    self.loaded_images.append({
                        "path": full_path,
                        "name": os.path.basename(full_path),
                        "w_px": w,
                        "h_px": h,
                        "dummy": False,
                        "color": ""
                    })
            except Exception:
                continue
        self.populate_table()

    def load_dummy_data(self):
        w_mm = random.randint(30, 80)
        h_mm = random.randint(30, 80)
        # Generuje spíše světlejší barvy (pastely), aby byly dobře vidět černé ořezové značky
        random_color = f"#{random.randint(0x888888, 0xFFFFFF):06x}"

        self.loaded_images.append({
            "path": "",
            "name": f"<Dummy {w_mm}x{h_mm}mm>",
            "w_px": int(w_mm * MM_TO_PX),
            "h_px": int(h_mm * MM_TO_PX),
            "dummy": True,
            "color": random_color
        })
        self.populate_table()

    def populate_table(self):
        self.table.setRowCount(len(self.loaded_images))
        for row, data in enumerate(self.loaded_images):
            # Náhled
            if data["dummy"]:
                bg_color = data.get("color", "red")
                img = Image.new('RGB', (50, 50), bg_color)
                d = ImageDraw.Draw(img)
                d.rectangle([0, 0, 49, 49], outline='black', width=2)
            else:
                img = Image.open(data["path"])
                img.thumbnail((50, 50))

            bio = BytesIO()
            img.save(bio, format="PNG")
            pix = QPixmap()
            pix.loadFromData(bio.getvalue())

            lbl_icon = QLabel()
            lbl_icon.setPixmap(pix)
            lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(row, 0, lbl_icon)

            # Jméno
            self.table.setItem(row, 1, QTableWidgetItem(data["name"]))

            # Šířka (mm) a Výška (mm)
            w_mm = data["w_px"] / MM_TO_PX
            h_mm = data["h_px"] / MM_TO_PX

            spin_w = QDoubleSpinBox()
            spin_w.setRange(5, 500)
            spin_w.setDecimals(1)
            spin_w.setValue(w_mm)
            self.table.setCellWidget(row, 2, spin_w)

            spin_h = QDoubleSpinBox()
            spin_h.setRange(5, 500)
            spin_h.setDecimals(1)
            spin_h.setValue(h_mm)
            self.table.setCellWidget(row, 3, spin_h)

            # Výpočet původního poměru stran
            ratio = w_mm / h_mm if h_mm > 0 else 1

            # Logika pro zámek poměru stran
            def make_w_callback(sw, sh, r):
                def cb(val):
                    if self.chk_lock_ratio.isChecked() and r > 0:
                        sh.blockSignals(True)
                        sh.setValue(val / r)
                        sh.blockSignals(False)

                return cb

            def make_h_callback(sw, sh, r):
                def cb(val):
                    if self.chk_lock_ratio.isChecked() and r > 0:
                        sw.blockSignals(True)
                        sw.setValue(val * r)
                        sw.blockSignals(False)

                return cb

            spin_w.valueChanged.connect(make_w_callback(spin_w, spin_h, ratio))
            spin_h.valueChanged.connect(make_h_callback(spin_w, spin_h, ratio))

            # Počet kusů
            spin_count = QSpinBox()
            spin_count.setRange(0, 999)
            spin_count.setValue(1)
            self.table.setCellWidget(row, 4, spin_count)

    # --- JÁDRO GENERÁTORU ---
    def auto_update_preview(self):
        if self.generated_pages and self.btn_preview.isEnabled():
            self.generate_preview(silent=True)

    def generate_preview(self, silent=False):
        if not silent: QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            gap_px = int(float(self.inp_gap.text()) * MM_TO_PX)
            bleed_px = int(float(self.inp_bleed.text()) * MM_TO_PX)
            r_px = int(float(self.inp_radius.text()) * MM_TO_PX)
            margin_px = int(float(self.inp_margin.text()) * MM_TO_PX)

            items_to_pack = []

            for row, data in enumerate(self.loaded_images):
                count = self.table.cellWidget(row, 4).value()
                w_mm = self.table.cellWidget(row, 2).value()
                h_mm = self.table.cellWidget(row, 3).value()

                for _ in range(count):
                    items_to_pack.append({
                        "path": data["path"],
                        "name": data["name"],
                        "w_px": int(w_mm * MM_TO_PX),
                        "h_px": int(h_mm * MM_TO_PX),
                        "dummy": data["dummy"],
                        "color": data.get("color", ""),
                        "group_id": row
                    })

            if not items_to_pack:
                if not silent: QMessageBox.warning(self, "Info", "Žádné položky ke generování.")
                self.generated_pages = []
                self.pages_layout_data = []
                self.refresh_preview()
                return

            paper_w_px = int(PAPER_SIZES[self.combo_paper.currentText()][0] * MM_TO_PX)
            paper_h_px = int(PAPER_SIZES[self.combo_paper.currentText()][1] * MM_TO_PX)

            self.pages_layout_data = []
            current_page_items = []

            cx, cy = margin_px, margin_px
            current_row_h = 0
            current_group_id = -1

            # --- SKLÁDÁNÍ (JEDEN DRUH NA ŘÁDEK) ---
            for item in items_to_pack:
                footprint_w = item["w_px"] + (2 * bleed_px) + gap_px
                footprint_h = item["h_px"] + (2 * bleed_px) + gap_px

                if current_group_id != -1 and current_group_id != item["group_id"] and cx > margin_px:
                    cy += current_row_h
                    cx = margin_px
                    current_row_h = 0

                if cx + footprint_w - gap_px > paper_w_px - margin_px:
                    cy += current_row_h
                    cx = margin_px
                    current_row_h = 0

                if cy + footprint_h - gap_px > paper_h_px - margin_px:
                    self.pages_layout_data.append(current_page_items)
                    current_page_items = []
                    cy = margin_px
                    cx = margin_px
                    current_row_h = 0

                cut_x = cx + bleed_px
                cut_y = cy + bleed_px

                current_page_items.append({
                    "item": item,
                    "cut_x": cut_x,
                    "cut_y": cut_y,
                    "w": item["w_px"],
                    "h": item["h_px"]
                })

                cx += footprint_w
                current_row_h = max(current_row_h, footprint_h)
                current_group_id = item["group_id"]

            if current_page_items:
                self.pages_layout_data.append(current_page_items)

            # --- VYKRESLENÍ ---
            self.generated_pages = []
            for page_data in self.pages_layout_data:
                page_img = Image.new('RGB', (paper_w_px, paper_h_px), 'white')
                draw = ImageDraw.Draw(page_img)

                # První průchod: Nalepíme obrázky
                for placement in page_data:
                    item = placement["item"]
                    cut_x, cut_y = placement["cut_x"], placement["cut_y"]
                    w, h = placement["w"], placement["h"]

                    target_w = w + (2 * bleed_px)
                    target_h = h + (2 * bleed_px)
                    paste_x = cut_x - bleed_px
                    paste_y = cut_y - bleed_px

                    if item["dummy"]:
                        bg_color = item.get("color", "#ffe4b5")
                        sticker = Image.new('RGB', (target_w, target_h), bg_color)
                        d = ImageDraw.Draw(sticker)
                        d.rectangle([0, 0, target_w - 1, target_h - 1], outline='black', width=2)
                    else:
                        with Image.open(item["path"]) as st:
                            if st.mode in ('RGBA', 'LA') or (st.mode == 'P' and 'transparency' in st.info):
                                bg = Image.new("RGB", st.size, (255, 255, 255))
                                bg.paste(st, mask=st.split()[3])
                                st = bg
                            else:
                                st = st.convert('RGB')
                            sticker = st.resize((target_w, target_h), Image.Resampling.LANCZOS)

                    page_img.paste(sticker, (paste_x, paste_y))

                # Druhý průchod: Vykreslíme křivky a křížky (aby byly vždy nad obrázky)
                for placement in page_data:
                    cut_x, cut_y = placement["cut_x"], placement["cut_y"]
                    w, h = placement["w"], placement["h"]

                    if self.chk_cut.isChecked():
                        draw.rounded_rectangle([cut_x, cut_y, cut_x + w, cut_y + h],
                                               radius=r_px, outline="#d9008e", width=3)

                    if self.chk_marks.isChecked():
                        self.draw_crop_marks(draw, cut_x, cut_y, w, h)

                self.generated_pages.append(page_img)

            self.current_page_index = 0
            self.btn_save_pdf.setEnabled(True)
            self.btn_save_dxf.setEnabled(True)
            self.refresh_preview()

        except Exception as e:
            if not silent: QMessageBox.critical(self, "Chyba", str(e))
        finally:
            if not silent: QApplication.restoreOverrideCursor()

    def draw_crop_marks(self, draw, x, y, w, h):
        l = 15
        c = 'black'
        draw.line([(x, y), (x - l, y)], fill=c)
        draw.line([(x, y), (x, y - l)], fill=c)
        draw.line([(x + w, y), (x + w + l, y)], fill=c)
        draw.line([(x + w, y), (x + w, y - l)], fill=c)
        draw.line([(x, y + h), (x - l, y + h)], fill=c)
        draw.line([(x, y + h), (x, y + h + l)], fill=c)
        draw.line([(x + w, y + h), (x + w + l, y + h)], fill=c)
        draw.line([(x + w, y + h), (x + w, y + h + l)], fill=c)

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

            paper_w_mm = PAPER_SIZES[self.combo_paper.currentText()][0]
            paper_h_mm = PAPER_SIZES[self.combo_paper.currentText()][1]
            r = float(self.inp_radius.text())
            bulge = 0.41421356

            offset_x_per_page = paper_w_mm + 20

            for page_idx, page_data in enumerate(self.pages_layout_data):
                page_offset_x = page_idx * offset_x_per_page

                for placement in page_data:
                    w = placement["w"] / MM_TO_PX
                    h = placement["h"] / MM_TO_PX
                    x = (placement["cut_x"] / MM_TO_PX) + page_offset_x
                    y = placement["cut_y"] / MM_TO_PX

                    cad_y = paper_h_mm - y - h

                    points = [
                        (x + r, cad_y, 0, 0, 0),
                        (x + w - r, cad_y, 0, 0, bulge),
                        (x + w, cad_y + r, 0, 0, 0),
                        (x + w, cad_y + h - r, 0, 0, bulge),
                        (x + w - r, cad_y + h, 0, 0, 0),
                        (x + r, cad_y + h, 0, 0, bulge),
                        (x, cad_y + h - r, 0, 0, 0),
                        (x, cad_y + r, 0, 0, bulge)
                    ]
                    msp.add_lwpolyline(points, close=True, dxfattribs={'layer': 'REZANI'})

            doc.saveas(f)
            QMessageBox.information(self, "Hotovo", "DXF uloženo.")

        except Exception as e:
            QMessageBox.critical(self, "Chyba při exportu DXF", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = StickerImposerApp()
    window.show()
    sys.exit(app.exec())