import sys
import os
from io import BytesIO
from PIL import Image

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QGroupBox, QLabel, QLineEdit, QComboBox, QCheckBox,
                             QPushButton, QFileDialog, QMessageBox, QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QIcon

# fitz (PyMuPDF) se importuje lazy – až při prvním použití PDF funkce,
# aby se záložka otevřela okamžitě (fitz je velká C extension ~80 ms).

MM_TO_PT = 72 / 25.4  # 1 mm = 2.8346 PDF bodů

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


class PdfImposerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Imposer – Vektorová archová montáž")
        self.resize(1100, 820)
        try:
            self.setWindowIcon(QIcon(resource_path("iconA.ico")))
        except:
            pass

        self.pdf_doc = None        # fitz.Document zdrojového PDF
        self.pdf_path = ""
        self.generated_pages = []  # Pillow Images – jen pro GUI náhled
        self.current_page_index = 0
        self.page_labels = []      # textové popisy stránek ("Líce 1/2", "Ruby 1/2"…)

        self.setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def setup_ui(self):
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)

        left_widget = QWidget()
        self.left_layout = QVBoxLayout(left_widget)
        self.left_layout.setContentsMargins(10, 10, 10, 10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left_widget)
        scroll.setMinimumWidth(370)

        # ── 1. Zdrojové PDF ──────────────────────────────────────────
        gb_src = QGroupBox("1. Zdrojové PDF")
        lay_src = QVBoxLayout()

        btn_load = QPushButton("Načíst PDF s kartami...")
        btn_load.setStyleSheet("background-color: #c8f0c8; font-weight: bold; padding: 6px;")
        btn_load.clicked.connect(self.load_pdf)
        lay_src.addWidget(btn_load)

        self.lbl_info = QLabel("Žádné PDF nenačteno")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet("color: #444; font-size: 10px; padding: 4px;")
        lay_src.addWidget(self.lbl_info)

        gb_src.setLayout(lay_src)
        self.left_layout.addWidget(gb_src)

        # ── 2. Zadní strana ──────────────────────────────────────────
        gb_back = QGroupBox("2. Zadní strana")
        lay_back = QVBoxLayout()

        lay_back.addWidget(QLabel("Typ zadní strany:"))
        self.combo_back = QComboBox()
        self.combo_back.addItems([
            "Žádná  (jednostranný tisk)",
            "Lichá = líc, sudá = rub  (str. 1,3,5… / 2,4,6…)",
            "Poslední stránka = sdílený rub pro všechny karty"
        ])
        lay_back.addWidget(self.combo_back)

        lbl_hint = QLabel(
            "• Střídání: stránka 1=karta1-líc, 2=karta1-rub, 3=karta2-líc…\n"
            "• Ruby se tisknou jako SEPARÁTNÍ archové stránky\n"
            "  se zrcadleným rozložením (sloupce obráceně),\n"
            "  aby po otočení papíru seděly na líce."
        )
        lbl_hint.setStyleSheet("color: #666; font-size: 9px;")
        lbl_hint.setWordWrap(True)
        lay_back.addWidget(lbl_hint)

        self.chk_mirror = QCheckBox("Zrcadlit rozložení rubů  (doporučeno)")
        self.chk_mirror.setChecked(True)
        self.chk_mirror.setStyleSheet("color: #0055aa; font-weight: bold;")
        lay_back.addWidget(self.chk_mirror)

        gb_back.setLayout(lay_back)
        self.left_layout.addWidget(gb_back)

        # ── 3. Papír a karta ─────────────────────────────────────────
        gb_paper = QGroupBox("3. Papír a rozměry karty")
        lay_paper = QVBoxLayout()

        row_fmt = QHBoxLayout()
        row_fmt.addWidget(QLabel("Formát papíru:"))
        self.combo_paper = QComboBox()
        self.combo_paper.addItems(list(PAPER_SIZES.keys()))
        self.combo_paper.setCurrentText("A4")
        row_fmt.addWidget(self.combo_paper)
        lay_paper.addLayout(row_fmt)

        self.inp_w       = self._add_input(lay_paper, "Šířka karty (mm):", "63")
        self.inp_h       = self._add_input(lay_paper, "Výška karty (mm):", "88")
        self.inp_gap     = self._add_input(lay_paper, "Mezera (mm):", "3")
        self.inp_bleed   = self._add_input(lay_paper, "Spadávka (mm):", "0")
        self.inp_marklen = self._add_input(lay_paper, "Délka zn. (mm):", "2")

        self.chk_marks = QCheckBox("Ořezové značky")
        self.chk_marks.setChecked(True)
        lay_paper.addWidget(self.chk_marks)

        self.chk_cut = QCheckBox("Řezací čára (viditelná v PDF)")
        self.chk_cut.setChecked(True)
        self.chk_cut.setStyleSheet("color: #d9008e;")
        lay_paper.addWidget(self.chk_cut)

        gb_paper.setLayout(lay_paper)
        self.left_layout.addWidget(gb_paper)

        self.left_layout.addStretch()

        # ── Tlačítka ─────────────────────────────────────────────────
        self.btn_preview = QPushButton("Generovat Náhled")
        self.btn_preview.setStyleSheet("background-color: lightblue; font-weight: bold; padding: 8px;")
        self.btn_preview.setEnabled(False)
        self.btn_preview.clicked.connect(self.generate_preview)
        self.left_layout.addWidget(self.btn_preview)

        self.btn_save_face = QPushButton("Uložit PDF – Líce")
        self.btn_save_face.setStyleSheet("background-color: #90ee90; font-weight: bold; padding: 8px;")
        self.btn_save_face.setEnabled(False)
        self.btn_save_face.clicked.connect(self.save_face_pdf)
        self.left_layout.addWidget(self.btn_save_face)

        self.btn_save_back = QPushButton("Uložit PDF – Ruby (zrcadlené)")
        self.btn_save_back.setStyleSheet("background-color: #ffd080; font-weight: bold; padding: 8px;")
        self.btn_save_back.setEnabled(False)
        self.btn_save_back.clicked.connect(self.save_back_pdf)
        self.left_layout.addWidget(self.btn_save_back)

        self.splitter.addWidget(scroll)

        # ── Pravý panel – náhled ──────────────────────────────────────
        right = QWidget()
        right.setStyleSheet("background-color: #404040;")
        rl = QVBoxLayout(right)

        nav = QHBoxLayout()
        nav.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_prev = QPushButton("<")
        self.btn_prev.setFixedWidth(40)
        self.btn_prev.clicked.connect(self.prev_page)

        self.lbl_page = QLabel("0 / 0")
        self.lbl_page.setStyleSheet("color: white; font-weight: bold;")
        self.lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_page.setMinimumWidth(140)

        self.btn_next = QPushButton(">")
        self.btn_next.setFixedWidth(40)
        self.btn_next.clicked.connect(self.next_page)

        nav.addWidget(self.btn_prev)
        nav.addWidget(self.lbl_page)
        nav.addWidget(self.btn_next)
        rl.addLayout(nav)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        rl.addWidget(self.preview_label)

        self.splitter.addWidget(right)
        self.splitter.setSizes([370, 700])

    def _add_input(self, layout, label, default):
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setMinimumWidth(150)
        inp = QLineEdit(default)
        inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inp.setFixedWidth(60)
        row.addWidget(lbl)
        row.addWidget(inp)
        layout.addLayout(row)
        return inp

    # ------------------------------------------------------------------
    # NAČTENÍ PDF  (fitz import je tady – lazy)
    # ------------------------------------------------------------------
    def load_pdf(self):
        import fitz  # lazy – záložka se otevře okamžitě, fitz se načte až tady
        path, _ = QFileDialog.getOpenFileName(self, "Vybrat PDF s kartami", "", "PDF soubory (*.pdf)")
        if not path:
            return
        try:
            doc = fitz.open(path)
            if doc.page_count == 0:
                QMessageBox.warning(self, "Chyba", "PDF neobsahuje žádné stránky.")
                return
            self.pdf_doc = doc
            self.pdf_path = path

            p0 = doc[0]
            pw_mm = p0.rect.width / MM_TO_PT
            ph_mm = p0.rect.height / MM_TO_PT
            self.inp_w.setText(f"{pw_mm:.1f}")
            self.inp_h.setText(f"{ph_mm:.1f}")

            self.lbl_info.setText(
                f"📄 {os.path.basename(path)}\n"
                f"Stránek: {doc.page_count}   |   Rozměr str.1: {pw_mm:.1f} × {ph_mm:.1f} mm"
            )
            self.btn_preview.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Chyba při načítání PDF", str(e))

    # ------------------------------------------------------------------
    # ROZDĚLENÍ STRÁNEK NA LÍCE / RUBY
    # ------------------------------------------------------------------
    def _split_face_back(self):
        """Vrátí (face_indices, back_indices) – stejně dlouhé seznamy.
        back_indices může obsahovat None (žádný rub pro danou kartu)."""
        total = self.pdf_doc.page_count
        mode = self.combo_back.currentIndex()

        if mode == 0:
            return list(range(total)), [None] * total

        if mode == 1:
            # stránky 0,2,4… = líce;  1,3,5… = ruby
            faces = list(range(0, total, 2))
            backs_src = list(range(1, total, 2))
            backs = [backs_src[i] if i < len(backs_src) else None
                     for i in range(len(faces))]
            return faces, backs

        # mode == 2 – poslední stránka sdílený rub
        if total < 2:
            return list(range(total)), [None] * total
        faces = list(range(total - 1))
        backs = [total - 1] * len(faces)
        return faces, backs

    # ------------------------------------------------------------------
    # SESTAVENÍ ARCHŮ (vektorové PDF pro jednu skupinu karet)
    # ------------------------------------------------------------------
    def _build_sheets(self, card_indices, mirrored: bool):
        """Sestaví fitz.Document s archovou montáží pro daný seznam stránek.
        card_indices: list[int | None] – indexy stránek zdrojového PDF.
        mirrored: True = sloupce zrcadlené (pro ruby)."""
        import fitz

        try:
            cw_mm = float(self.inp_w.text())
            ch_mm = float(self.inp_h.text())
            gap_mm = float(self.inp_gap.text())
            bleed_mm = float(self.inp_bleed.text())
            mark_mm = float(self.inp_marklen.text())
        except ValueError:
            return None

        paper_w_mm, paper_h_mm = PAPER_SIZES.get(self.combo_paper.currentText(), (210, 297))
        pw_pt = paper_w_mm * MM_TO_PT
        ph_pt = paper_h_mm * MM_TO_PT
        cw_pt = cw_mm * MM_TO_PT
        ch_pt = ch_mm * MM_TO_PT
        gap_pt = gap_mm * MM_TO_PT
        bleed_pt = bleed_mm * MM_TO_PT
        mark_pt = mark_mm * MM_TO_PT

        cols = int(paper_w_mm // (cw_mm + gap_mm))
        rows = int(paper_h_mm // (ch_mm + gap_mm))
        if cols <= 0 or rows <= 0:
            return None

        mx_pt = (pw_pt - cols * (cw_pt + gap_pt) + gap_pt) / 2
        my_pt = (ph_pt - rows * (ch_pt + gap_pt) + gap_pt) / 2

        do_marks = self.chk_marks.isChecked()
        do_cut = self.chk_cut.isChecked()
        src = self.pdf_doc
        out = fitz.open()

        if not card_indices:
            return None

        cc = cr = 0
        page = out.new_page(width=pw_pt, height=ph_pt)
        pending_marks = []

        def flush_marks(pg, mlist):
            if do_marks:
                for mx, my, mw, mh in mlist:
                    _draw_crop_marks(pg, fitz, mx, my, mw, mh, mark_pt)

        for src_idx in card_indices:
            final_col = (cols - 1 - cc) if mirrored else cc
            x = mx_pt + final_col * (cw_pt + gap_pt)
            y = my_pt + cr * (ch_pt + gap_pt)

            # Vektorové vložení PDF stránky (XObject, žádná rasterizace)
            if src_idx is not None:
                target = fitz.Rect(
                    x - bleed_pt, y - bleed_pt,
                    x + cw_pt + bleed_pt, y + ch_pt + bleed_pt
                )
                page.show_pdf_page(target, src, src_idx)

            # Řezací čára – jednoduché 4 úsečky (rychlé, vektorové)
            if do_cut:
                _draw_cut_rect(page, fitz, x, y, cw_pt, ch_pt)

            if do_marks:
                pending_marks.append((x, y, cw_pt, ch_pt))

            cc += 1
            if cc >= cols:
                cc = 0
                cr += 1
                if cr >= rows:
                    flush_marks(page, pending_marks)
                    pending_marks = []
                    page = out.new_page(width=pw_pt, height=ph_pt)
                    cr = 0

        if cc > 0 or cr > 0:
            flush_marks(page, pending_marks)
        else:
            out.delete_page(-1)  # prázdná stránka navíc

        return out if out.page_count > 0 else None

    # ------------------------------------------------------------------
    # NÁHLED
    # ------------------------------------------------------------------
    def generate_preview(self):
        import fitz
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            face_list, back_list = self._split_face_back()
            mirror = self.chk_mirror.isChecked()

            face_doc = self._build_sheets(face_list, mirrored=False)
            has_backs = any(b is not None for b in back_list)
            back_doc = self._build_sheets(back_list, mirrored=mirror) if has_backs else None

            if face_doc is None:
                QMessageBox.warning(self, "Info", "Prázdný výstup nebo neplatné rozměry.")
                return

            preview = []
            labels = []

            # Lícové stránky
            fn = face_doc.page_count
            for i in range(fn):
                pix = face_doc[i].get_pixmap(matrix=fitz.Matrix(96 / 72, 96 / 72), alpha=False)
                img = Image.open(BytesIO(pix.tobytes("png"))).copy()
                preview.append(img)
                labels.append(f"LÍCE  {i + 1}/{fn}")

            # Rubové stránky
            if back_doc:
                bn = back_doc.page_count
                for i in range(bn):
                    pix = back_doc[i].get_pixmap(matrix=fitz.Matrix(96 / 72, 96 / 72), alpha=False)
                    img = Image.open(BytesIO(pix.tobytes("png"))).copy()
                    preview.append(img)
                    labels.append(f"RUBY (zrcadlené)  {i + 1}/{bn}")

            self.generated_pages = preview
            self.page_labels = labels
            self.current_page_index = 0

            self.btn_save_face.setEnabled(True)
            self.btn_save_back.setEnabled(has_backs)
            self.refresh_preview()

        except Exception as e:
            QMessageBox.critical(self, "Chyba", str(e))
        finally:
            QApplication.restoreOverrideCursor()

    def refresh_preview(self):
        if not self.generated_pages:
            self.lbl_page.setText("0 / 0")
            self.preview_label.clear()
            return

        idx = self.current_page_index
        total = len(self.generated_pages)
        lbl_txt = self.page_labels[idx] if idx < len(self.page_labels) else f"{idx + 1}/{total}"
        self.lbl_page.setText(lbl_txt)

        img = self.generated_pages[idx]
        cw = self.preview_label.width()
        ch = self.preview_label.height()
        if cw < 20 or ch < 20:
            return

        iw, ih = img.size
        scale = min((cw - 10) / iw, (ch - 10) / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        if nw <= 0:
            return

        buf = BytesIO()
        img.resize((nw, nh), Image.Resampling.LANCZOS).save(buf, format="PNG")
        px = QPixmap()
        px.loadFromData(buf.getvalue())
        self.preview_label.setPixmap(px)

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

    # ------------------------------------------------------------------
    # ULOŽENÍ – dvě separátní tlačítka
    # ------------------------------------------------------------------
    def save_face_pdf(self):
        self._save_group(mirrored=False, label="líce")

    def save_back_pdf(self):
        self._save_group(mirrored=self.chk_mirror.isChecked(), label="ruby")

    def _save_group(self, mirrored: bool, label: str):
        face_list, back_list = self._split_face_back()
        card_indices = face_list if not mirrored else back_list

        # Pokud user chce ruby ale combo je na "žádná", back_list je samé None
        if all(b is None for b in card_indices):
            QMessageBox.information(self, "Info",
                "Pro zvolený typ zadní strany nejsou k dispozici žádné rubové stránky.")
            return

        f, _ = QFileDialog.getSaveFileName(
            self, f"Uložit PDF – {label}", "",  "PDF (*.pdf)"
        )
        if not f:
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            out = self._build_sheets(card_indices, mirrored=mirrored)
            if out and out.page_count > 0:
                out.save(f, garbage=4, deflate=True)
                QMessageBox.information(self, "Hotovo",
                    f"PDF ({label}) uloženo.\nStránek: {out.page_count}\n{f}")
            else:
                QMessageBox.warning(self, "Chyba", "Nepodařilo se vygenerovat stránky.")
        except Exception as e:
            QMessageBox.critical(self, "Chyba při ukládání", str(e))
        finally:
            QApplication.restoreOverrideCursor()


# ------------------------------------------------------------------
# KRESLICÍ HELPER FUNKCE
# ------------------------------------------------------------------

def _draw_crop_marks(page, fitz, x, y, w, h, ml):
    """Ořezové značky – 8 úseček vně rohů karty."""
    col = (0, 0, 0)
    lw = 0.5
    page.draw_line(fitz.Point(x,     y),     fitz.Point(x - ml, y),     color=col, width=lw)
    page.draw_line(fitz.Point(x,     y),     fitz.Point(x,     y - ml), color=col, width=lw)
    page.draw_line(fitz.Point(x + w, y),     fitz.Point(x+w+ml, y),     color=col, width=lw)
    page.draw_line(fitz.Point(x + w, y),     fitz.Point(x + w, y - ml), color=col, width=lw)
    page.draw_line(fitz.Point(x,     y + h), fitz.Point(x - ml, y + h), color=col, width=lw)
    page.draw_line(fitz.Point(x,     y + h), fitz.Point(x,     y+h+ml), color=col, width=lw)
    page.draw_line(fitz.Point(x + w, y + h), fitz.Point(x+w+ml, y+h),   color=col, width=lw)
    page.draw_line(fitz.Point(x + w, y + h), fitz.Point(x + w, y+h+ml), color=col, width=lw)


def _draw_cut_rect(page, fitz, x, y, w, h):
    """Řezací obdélník – 4 jednoduché úsečky (růžová, tenká). Rychlé."""
    col = (0.85, 0.0, 0.55)
    lw = 0.4
    page.draw_line(fitz.Point(x,     y),     fitz.Point(x + w, y),     color=col, width=lw)
    page.draw_line(fitz.Point(x + w, y),     fitz.Point(x + w, y + h), color=col, width=lw)
    page.draw_line(fitz.Point(x + w, y + h), fitz.Point(x,     y + h), color=col, width=lw)
    page.draw_line(fitz.Point(x,     y + h), fitz.Point(x,     y),     color=col, width=lw)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = PdfImposerApp()
    window.show()
    sys.exit(app.exec())
