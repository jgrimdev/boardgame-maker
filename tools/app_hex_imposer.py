import sys
import os
import math
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

DPI = 300
MM_TO_PX = DPI / 25.4

PAPER_SIZES = {
    "A3": (297, 420),
    "A4": (210, 297),
    "A5": (148, 210)
}

class HexImposerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Generátor Hexagonů v2.0 - Plástve")
        self.resize(1250, 850)

        self.loaded_images = []
        self.generated_pages = []
        self.pages_layout_data = []
        self.current_page_index = 0

        self.setup_ui()

    def setup_ui(self):
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)

        # --- LEVÝ PANEL ---
        self.left_panel_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel_widget)
        self.left_layout.setContentsMargins(10, 10, 10, 10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.left_panel_widget)
        scroll_area.setMinimumWidth(480)

        # 1. Nastavení papíru a Hexagonu
        gb_paper = QGroupBox("1. Nastavení rozvržení (Plástev)")
        lay_paper = QVBoxLayout()

        row_format = QHBoxLayout()
        row_format.addWidget(QLabel("Formát papíru:"))
        self.combo_paper = QComboBox()
        self.combo_paper.addItems(list(PAPER_SIZES.keys()))
        self.combo_paper.setCurrentText("A4")
        row_format.addWidget(self.combo_paper)
        lay_paper.addLayout(row_format)

        self.inp_margin = self.create_input(lay_paper, "Bezpečný okraj papíru (mm):", "10")
        self.inp_hex_w = self.create_input(lay_paper, "Šířka hexagonu hrana-hrana (mm):", "40")
        self.inp_gap = self.create_input(lay_paper, "Mezera mezi hexagony (mm):", "2")
        self.inp_bleed = self.create_input(lay_paper, "Spadávka (mm):", "0")

        self.chk_marks = QCheckBox("Bounding Box pro zarovnání s laserem")
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
        gb_data = QGroupBox("2. Obrázky a počet")
        lay_data = QVBoxLayout()

        btn_dummy = QPushButton("Přidat 1x testovací hexagon")
        btn_dummy.setStyleSheet("background-color: #ffe4b5;")
        btn_dummy.clicked.connect(self.load_dummy_data)
        lay_data.addWidget(btn_dummy)
        
        btn_dummy_page = QPushButton("Vyplnit celou stránku testovacími hexagony")
        btn_dummy_page.setStyleSheet("background-color: #ffb5b5;")
        btn_dummy_page.clicked.connect(self.fill_page_with_dummy)
        lay_data.addWidget(btn_dummy_page)

        btn_load = QPushButton("Vybrat obrázky...")
        btn_load.setStyleSheet("background-color: #b5e4ff; font-weight: bold;")
        btn_load.clicked.connect(self.load_files)
        lay_data.addWidget(btn_load)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Náhled", "Soubor", "Počet", "Akce"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(60)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 50)
        lay_data.addWidget(self.table)

        gb_data.setLayout(lay_data)
        self.left_layout.addWidget(gb_data)

        self.left_layout.addStretch()

        # Patička ovládání
        self.btn_preview = QPushButton("Generovat Plástve")
        self.btn_preview.setStyleSheet("background-color: lightblue; font-weight: bold; padding: 10px;")
        self.btn_preview.clicked.connect(lambda: self.generate_preview(silent=False))
        self.left_layout.addWidget(self.btn_preview)

        self.btn_save_pdf = QPushButton("Uložit Tiskové PDF")
        self.btn_save_pdf.setStyleSheet("background-color: lightgreen; font-weight: bold; padding: 8px;")
        self.btn_save_pdf.setEnabled(False)
        self.btn_save_pdf.clicked.connect(self.save_pdf)
        self.left_layout.addWidget(self.btn_save_pdf)

        self.btn_save_dxf = QPushButton("Uložit Řezací DXF")
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
        lbl.setMinimumWidth(200)
        inp = QLineEdit(default_val)
        inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inp.setFixedWidth(60)
        row.addWidget(lbl)
        row.addWidget(inp)
        layout.addLayout(row)
        return inp

    def load_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Vyberte obrázky pro hexagony", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if not files: return

        for full_path in files:
            try:
                self.loaded_images.append({
                    "path": full_path,
                    "name": os.path.basename(full_path),
                    "dummy": False,
                    "color": ""
                })
            except Exception:
                continue
        self.populate_table()

    def load_dummy_data(self):
        random_color = f"#{random.randint(0x888888, 0xFFFFFF):06x}"
        self.loaded_images.append({
            "path": "",
            "name": f"<Dummy Hexagon>",
            "dummy": True,
            "color": random_color
        })
        self.populate_table()

    def fill_page_with_dummy(self):
        try:
            w_flat_mm = float(self.inp_hex_w.text())
            gap_mm = float(self.inp_gap.text())
            margin_mm = float(self.inp_margin.text())
            paper_w_mm = PAPER_SIZES[self.combo_paper.currentText()][0]
            paper_h_mm = PAPER_SIZES[self.combo_paper.currentText()][1]
        except:
            return

        dx_mm = w_flat_mm + gap_mm
        dy_mm = dx_mm * math.sqrt(3) / 2
        H_point_mm = 2 * (w_flat_mm / math.sqrt(3))

        count = 0
        row_idx = 0
        while True:
            cy = margin_mm + H_point_mm/2 + row_idx * dy_mm
            if cy + (H_point_mm / 2) > paper_h_mm - margin_mm:
                break

            col = 0
            while True:
                cx = margin_mm + (w_flat_mm / 2) + col * dx_mm + (row_idx % 2) * (dx_mm / 2)
                if cx + (w_flat_mm / 2) > paper_w_mm - margin_mm:
                    break
                count += 1
                col += 1
            row_idx += 1

        if count == 0: count = 1

        random_color = f"#{random.randint(0x888888, 0xFFFFFF):06x}"
        self.loaded_images.append({
            "path": "",
            "name": f"Dummy Plná Strana ({count}x)",
            "dummy": True,
            "color": random_color
        })
        self.populate_table()
        # Nastavíme počet automaticky do tabulky (projdeme save_state)
        self.save_table_state()
        self.loaded_images[-1]["saved_c"] = count
        self.populate_table()
        self.auto_update_preview()

    def save_table_state(self):
        for r in range(len(self.loaded_images)):
            w_w = self.table.cellWidget(r, 2)
            if w_w:
                self.loaded_images[r]["saved_c"] = w_w.value()

    def delete_item(self, row):
        if 0 <= row < len(self.loaded_images):
            self.save_table_state()
            self.loaded_images.pop(row)
            self.populate_table()
            self.auto_update_preview()

    def populate_table(self):
        self.table.setRowCount(len(self.loaded_images))
        for row, data in enumerate(self.loaded_images):
            if data["dummy"]:
                bg_color = data.get("color", "red")
                img = Image.new('RGB', (50, 50), bg_color)
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

            self.table.setItem(row, 1, QTableWidgetItem(data["name"]))

            spin_count = QSpinBox()
            spin_count.setRange(0, 999)
            spin_count.setValue(data.get("saved_c", 1))
            self.table.setCellWidget(row, 2, spin_count)
            
            btn_del = QPushButton("❌")
            btn_del.setStyleSheet("color: red; font-weight: bold; background: transparent; border: none;")
            btn_del.clicked.connect(lambda checked, r=row: self.delete_item(r))
            self.table.setCellWidget(row, 3, btn_del)

    def auto_update_preview(self):
        if self.generated_pages and self.btn_preview.isEnabled():
            self.generate_preview(silent=True)

    def generate_preview(self, silent=False):
        if not silent: QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            w_flat_mm = float(self.inp_hex_w.text())
            gap_mm = float(self.inp_gap.text())
            bleed_mm = float(self.inp_bleed.text())
            margin_mm = float(self.inp_margin.text())

            w_flat_px = w_flat_mm * MM_TO_PX
            gap_px = gap_mm * MM_TO_PX
            bleed_px = bleed_mm * MM_TO_PX
            margin_px = margin_mm * MM_TO_PX
            
            # Parametry hexagonu (Orientace: Špičky nahoře a dole)
            # Vzdálenost středů horizontálně:
            dx_px = w_flat_px + gap_px
            # Vzdálenost středů vertikálně:
            dy_px = dx_px * math.sqrt(3) / 2
            
            # Poloměr k rohům (pro ořez a bleed masky)
            R_px = w_flat_px / math.sqrt(3)
            H_point_px = 2 * R_px

            items_to_pack = []
            for row, data in enumerate(self.loaded_images):
                count = self.table.cellWidget(row, 2).value()
                for _ in range(count):
                    items_to_pack.append(data)

            if not items_to_pack:
                if not silent: QMessageBox.warning(self, "Info", "Žádné položky ke generování.")
                self.generated_pages = []
                self.refresh_preview()
                return

            paper_w_px = int(PAPER_SIZES[self.combo_paper.currentText()][0] * MM_TO_PX)
            paper_h_px = int(PAPER_SIZES[self.combo_paper.currentText()][1] * MM_TO_PX)

            self.pages_layout_data = []
            current_page_items = []

            # Honeycomb layout algorithm
            col = 0
            row_idx = 0
            
            for item in items_to_pack:
                # Vypočítáme pozici středu hexagonu
                cx = margin_px + (w_flat_px / 2) + col * dx_px + (row_idx % 2) * (dx_px / 2)
                cy = margin_px + H_point_px/2 + row_idx * dy_px
                
                # Zkontrolujeme, zda nepřetéká doprava
                if cx + (w_flat_px / 2) > paper_w_px - margin_px:
                    row_idx += 1
                    col = 0
                    cx = margin_px + (w_flat_px / 2) + col * dx_px + (row_idx % 2) * (dx_px / 2)
                    cy = margin_px + H_point_px/2 + row_idx * dy_px
                
                # Zkontrolujeme, zda nepřetéká dolů
                if cy + (H_point_px / 2) > paper_h_px - margin_px:
                    self.pages_layout_data.append(current_page_items)
                    current_page_items = []
                    row_idx = 0
                    col = 0
                    cx = margin_px + (w_flat_px / 2) + col * dx_px + (row_idx % 2) * (dx_px / 2)
                    cy = margin_px + H_point_px/2 + row_idx * dy_px

                current_page_items.append({
                    "item": item,
                    "cx": cx,
                    "cy": cy
                })
                col += 1

            if current_page_items:
                self.pages_layout_data.append(current_page_items)

            # VYKRESLOVÁNÍ
            self.generated_pages = []
            
            # Předpřipravíme si tvar pro výřez / dummy barvu
            target_w = int(w_flat_px + 2*bleed_px)
            target_h = int(H_point_px + 2*bleed_px)

            for page_data in self.pages_layout_data:
                page_img = Image.new('RGB', (paper_w_px, paper_h_px), 'white')
                draw = ImageDraw.Draw(page_img)
                
                min_x, min_y, max_x, max_y = float('inf'), float('inf'), 0, 0

                for placement in page_data:
                    item = placement["item"]
                    cx, cy = placement["cx"], placement["cy"]
                    
                    paste_x = int(cx - target_w/2)
                    paste_y = int(cy - target_h/2)
                    
                    min_x = min(min_x, cx - target_w/2)
                    min_y = min(min_y, cy - target_h/2)
                    max_x = max(max_x, cx + target_w/2)
                    max_y = max(max_y, cy + target_h/2)

                    if item["dummy"]:
                        bg_color = item.get("color", "#ffe4b5")
                        hex_img = Image.new('RGB', (target_w, target_h), bg_color)
                    else:
                        with Image.open(item["path"]) as st:
                            if st.mode in ('RGBA', 'LA') or (st.mode == 'P' and 'transparency' in st.info):
                                bg = Image.new("RGB", st.size, (255, 255, 255))
                                bg.paste(st, mask=st.split()[3])
                                st = bg
                            else:
                                st = st.convert('RGB')
                            
                            # Oříznutí/změna velikosti (crop to fill)
                            st_ratio = st.width / st.height
                            target_ratio = target_w / target_h
                            if st_ratio > target_ratio:
                                new_w = int(st.height * target_ratio)
                                offset = (st.width - new_w) // 2
                                st = st.crop((offset, 0, offset + new_w, st.height))
                            else:
                                new_h = int(st.width / target_ratio)
                                offset = (st.height - new_h) // 2
                                st = st.crop((0, offset, st.width, offset + new_h))
                                
                            hex_img = st.resize((target_w, target_h), Image.Resampling.LANCZOS)

                    # Vytvoření masky ve tvaru hexagonu vč. bleedu
                    mask = Image.new("L", (target_w, target_h), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_pts = self.get_hex_points(target_w/2, target_h/2, (w_flat_px + 2*bleed_px)/math.sqrt(3))
                    mask_draw.polygon(mask_pts, fill=255)
                    
                    page_img.paste(hex_img, (paste_x, paste_y), mask)

                    # Ořezové linky
                    if self.chk_cut.isChecked():
                        cut_pts = self.get_hex_points(cx, cy, R_px)
                        draw.polygon(cut_pts, outline="#d9008e", width=3)

                if self.chk_marks.isChecked() and page_data:
                    l = 10
                    c = "red"
                    w = 3
                    # TL
                    draw.line([(min_x, min_y+l), (min_x, min_y), (min_x+l, min_y)], fill=c, width=w)
                    # TR
                    draw.line([(max_x-l, min_y), (max_x, min_y), (max_x, min_y+l)], fill=c, width=w)
                    # BL
                    draw.line([(min_x, max_y-l), (min_x, max_y), (min_x+l, max_y)], fill=c, width=w)
                    # BR
                    draw.line([(max_x-l, max_y), (max_x, max_y), (max_x, max_y-l)], fill=c, width=w)

                self.generated_pages.append(page_img)

            self.current_page_index = 0
            self.btn_save_pdf.setEnabled(True)
            self.btn_save_dxf.setEnabled(True)
            self.refresh_preview()

        except Exception as e:
            if not silent: QMessageBox.critical(self, "Chyba", str(e))
        finally:
            if not silent: QApplication.restoreOverrideCursor()
            
    def get_hex_points(self, cx, cy, R):
        pts = []
        # Špičky nahoře a dole -> úhly 30, 90, 150, 210, 270, 330
        for angle_deg in [30, 90, 150, 210, 270, 330]:
            angle_rad = math.radians(angle_deg)
            x = cx + R * math.cos(angle_rad)
            y = cy - R * math.sin(angle_rad) # Y je invertované na monitoru
            pts.append((x, y))
        return pts

    def prev_page(self):
        if self.generated_pages and self.current_page_index > 0:
            self.current_page_index -= 1
            self.refresh_preview()

    def next_page(self):
        if self.generated_pages and self.current_page_index < len(self.generated_pages) - 1:
            self.current_page_index += 1
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
            doc.layers.add(name="ZNACKY", color=1)

            paper_w_mm = PAPER_SIZES[self.combo_paper.currentText()][0]
            paper_h_mm = PAPER_SIZES[self.combo_paper.currentText()][1]

            w_flat_mm = float(self.inp_hex_w.text())
            bleed_mm = float(self.inp_bleed.text())
            R_mm = w_flat_mm / math.sqrt(3)

            offset_x_per_page = paper_w_mm + 20

            for page_idx, page_data in enumerate(self.pages_layout_data):
                page_offset_x = page_idx * offset_x_per_page
                
                min_x_mm, min_y_mm, max_x_mm, max_y_mm = float('inf'), float('inf'), 0, 0

                for placement in page_data:
                    cx_px = placement["cx"]
                    cy_px = placement["cy"]

                    # Převod z PX na MM
                    cx_mm = (cx_px / MM_TO_PX) + page_offset_x
                    cy_mm = cy_px / MM_TO_PX
                    
                    target_w_mm = w_flat_mm + 2*bleed_mm
                    target_h_mm = 2*R_mm + 2*bleed_mm

                    min_x_mm = min(min_x_mm, cx_mm - target_w_mm/2)
                    min_y_mm = min(min_y_mm, cy_mm - target_h_mm/2)
                    max_x_mm = max(max_x_mm, cx_mm + target_w_mm/2)
                    max_y_mm = max(max_y_mm, cy_mm + target_h_mm/2)

                    cad_y = paper_h_mm - cy_mm

                    pts = self.get_hex_points(cx_mm, cad_y, R_mm)
                    # DXF polygony
                    dxf_pts = [(p[0], p[1], 0, 0, 0) for p in pts]
                    msp.add_lwpolyline(dxf_pts, close=True, dxfattribs={'layer': 'REZANI'})
                    
                if self.chk_marks.isChecked() and page_data:
                    cad_y_top = paper_h_mm - min_y_mm
                    cad_y_bottom = paper_h_mm - max_y_mm
                    l = 10
                    msp.add_lwpolyline([(min_x_mm, cad_y_top-l), (min_x_mm, cad_y_top), (min_x_mm+l, cad_y_top)], dxfattribs={'layer': 'ZNACKY'})
                    msp.add_lwpolyline([(max_x_mm-l, cad_y_top), (max_x_mm, cad_y_top), (max_x_mm, cad_y_top-l)], dxfattribs={'layer': 'ZNACKY'})
                    msp.add_lwpolyline([(min_x_mm, cad_y_bottom+l), (min_x_mm, cad_y_bottom), (min_x_mm+l, cad_y_bottom)], dxfattribs={'layer': 'ZNACKY'})
                    msp.add_lwpolyline([(max_x_mm-l, cad_y_bottom), (max_x_mm, cad_y_bottom), (max_x_mm, cad_y_bottom+l)], dxfattribs={'layer': 'ZNACKY'})

            doc.saveas(f)
            QMessageBox.information(self, "Hotovo", "DXF uloženo.")

        except Exception as e:
            QMessageBox.critical(self, "Chyba při exportu DXF", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = HexImposerApp()
    window.show()
    sys.exit(app.exec())
