import sys
import ezdxf
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QGroupBox, QLabel, QLineEdit, QComboBox,
                             QPushButton, QFileDialog, QMessageBox, QGraphicsView,
                             QGraphicsScene, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPen, QColor


class GraphicsViewZoom(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.zoom_factor = 1.15

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            factor = self.zoom_factor
        else:
            factor = 1.0 / self.zoom_factor
        self.scale(factor, factor)


class BoxGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Generator v1.0 - Krabičky na míru")
        self.resize(1100, 750)

        self.lines_cut = []
        self.lines_fold = []

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.generate_preview)

        self.setup_ui()
        self.generate_preview()

    def setup_ui(self):
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)

        # --- LEVÝ PANEL ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        gb_type = QGroupBox("1. Typ a Materiál")
        lyt_type = QVBoxLayout()
        self.combo_type = QComboBox()
        self.combo_type.addItems([
            "Tuck Box (Papír - 1 kus)", 
            "Dno a Víko (Papír - 2 kusy)", 
            "Otevřený Box / Šuplík (Dřevo - Laser)",
            "Dno a Víko (Dřevo - Laser)",
            "Zasouvací víko (Dřevo - Laser)"
        ])
        self.combo_type.currentIndexChanged.connect(self.on_type_changed)
        lyt_type.addWidget(self.combo_type)
        gb_type.setLayout(lyt_type)
        left_layout.addWidget(gb_type)

        gb_dims = QGroupBox("2. Vnitřní rozměry (mm)")
        lyt_dims = QVBoxLayout()
        self.inp_w = self.create_input(lyt_dims, "Šířka (W):", "65")
        self.inp_h = self.create_input(lyt_dims, "Výška (H):", "90")
        self.inp_d = self.create_input(lyt_dims, "Hloubka (D):", "20")
        gb_dims.setLayout(lyt_dims)
        left_layout.addWidget(gb_dims)

        gb_adv = QGroupBox("3. Pokročilé / Dřevo")
        lyt_adv = QVBoxLayout()
        self.inp_lid_depth = self.create_input(lyt_adv, "Hloubka víka (mm):", "20")
        self.inp_tolerance = self.create_input(lyt_adv, "Vůle víka (mm):", "1.0")
        self.inp_wood_thick = self.create_input(lyt_adv, "Tloušťka dřeva (mm):", "3.0")
        self.inp_tooth = self.create_input(lyt_adv, "Velikost zubu (mm):", "10.0")

        self.lbl_hint = QLabel("<i>Tip: Pro Dno a Víko musí mít víko vůli<br>(cca 1 mm) oproti dnu, aby šlo zavřít.</i>")
        self.lbl_hint.setStyleSheet("color: gray;")
        lyt_adv.addWidget(self.lbl_hint)
        gb_adv.setLayout(lyt_adv)
        left_layout.addWidget(gb_adv)
        
        self.on_type_changed()

        left_layout.addStretch()

        self.btn_export = QPushButton("Uložit DXF křivky")
        self.btn_export.setStyleSheet("background-color: #ffd700; font-weight: bold; padding: 12px;")
        self.btn_export.clicked.connect(self.export_dxf)
        left_layout.addWidget(self.btn_export)

        self.splitter.addWidget(left_widget)

        # --- PRAVÝ PANEL (Náhled) ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_widget.setStyleSheet("background-color: #2b2b2b;")

        self.scene = QGraphicsScene()
        self.view = GraphicsViewZoom(self.scene)
        self.view.setStyleSheet("background-color: #2b2b2b; border: none;")
        right_layout.addWidget(self.view)

        self.splitter.addWidget(right_widget)
        self.splitter.setSizes([350, 750])

    def create_input(self, layout, label, default):
        row = QHBoxLayout()
        lbl = QLabel(label)
        inp = QLineEdit(default)
        inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inp.setFixedWidth(60)
        inp.textChanged.connect(self.timer.start)
        row.addWidget(lbl)
        row.addWidget(inp)
        layout.addLayout(row)
        return inp

    def get_values(self):
        try:
            return (
                float(self.inp_w.text().replace(',', '.')),
                float(self.inp_h.text().replace(',', '.')),
                float(self.inp_d.text().replace(',', '.')),
                float(self.inp_lid_depth.text().replace(',', '.')),
                float(self.inp_tolerance.text().replace(',', '.'))
            )
        except ValueError:
            return None

    def on_type_changed(self):
        idx = self.combo_type.currentIndex()
        if idx >= 2:
            self.inp_wood_thick.setEnabled(True)
            self.inp_tooth.setEnabled(True)
            self.lbl_hint.setText("<i>Tip: Laserové boxy mají přesně vypočítané zámky (zuby)<br>s kompenzací pro rohy.</i>")
        else:
            self.inp_wood_thick.setEnabled(False)
            self.inp_tooth.setEnabled(False)
            self.lbl_hint.setText("<i>Tip: Papírová krabička z jednoho nebo dvou kusů.</i>")
        self.timer.start()

    def generate_preview(self):
        vals = self.get_values()
        if not vals: return
        w, h, d, lid_d, tol = vals
        try:
            wood_t = float(self.inp_wood_thick.text().replace(',', '.'))
            tooth_sz = float(self.inp_tooth.text().replace(',', '.'))
        except:
            wood_t = 3.0
            tooth_sz = 10.0

        self.lines_cut.clear()
        self.lines_fold.clear()

        box_type = self.combo_type.currentIndex()

        if box_type == 0:
            self.calc_tuck_box(w, h, d)
        elif box_type == 1:
            self.calc_base_and_lid(w, h, d, lid_d, tol)
        elif box_type == 2:
            self._calc_wood_tray(0, 0, w, h, d, wood_t, tooth_sz)
        elif box_type == 3:
            self.calc_wood_box_baselid(w, h, d, lid_d, tol, wood_t, tooth_sz)
        elif box_type == 4:
            self.calc_wood_box_sliding(w, h, d, tol, wood_t, tooth_sz)

        self.scene.clear()

        # Kosmetické pero (tloušťka 0 znamená, že se neškáluje při zoomování!)
        pen_cut = QPen(QColor(255, 50, 50), 0)
        pen_fold = QPen(QColor(50, 150, 255), 0, Qt.PenStyle.DashLine)

        for line in self.lines_cut:
            self.scene.addLine(line[0], line[1], line[2], line[3], pen_cut)

        for line in self.lines_fold:
            self.scene.addLine(line[0], line[1], line[2], line[3], pen_fold)

        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # ==========================================
    # MATEMATIKA: TUCK BOX (Klasická krabička)
    # ==========================================
    def calc_tuck_box(self, w, h, d):
        glue = 15
        tuck = min(15.0, d - 2)

        x0, x1, x2, x3, x4, x5 = 0, glue, glue + d, glue + d + w, glue + 2 * d + w, glue + 2 * d + 2 * w
        y0, y1 = 0, h

        # --- SVISLÉ OHYBY ---
        self.lines_fold.extend([
            (x1, y0, x1, y1), (x2, y0, x2, y1),
            (x3, y0, x3, y1), (x4, y0, x4, y1)
        ])

        # --- HLAVNÍ TĚLO KŘIVKY (Řez) ---
        self.lines_cut.extend([
            (x0, y0 + 5, x0, y1 - 5),  # Lepicí chlopeň zleva
            (x0, y1 - 5, x1, y1),  # Zkosení nahoru
            (x0, y0 + 5, x1, y0),  # Zkosení dolů
            (x4, y0, x5, y0),  # Spodek zadní strany
            (x4, y1, x5, y1),  # Vršek zadní strany
            (x5, y0, x5, y1)  # Pravý okraj
        ])

        # --- HORNÍ CHLOPNĚ ---
        # Prachové chlopně (Dust flaps)
        self.lines_fold.extend([(x1, y1, x2, y1), (x3, y1, x4, y1)])
        self.lines_cut.extend([
            (x1, y1, x1 + 3, y1 + d - 3), (x1 + 3, y1 + d - 3, x2 - 3, y1 + d - 3), (x2 - 3, y1 + d - 3, x2, y1),
            # Levá
            (x3, y1, x3 + 3, y1 + d - 3), (x3 + 3, y1 + d - 3, x4 - 3, y1 + d - 3), (x4 - 3, y1 + d - 3, x4, y1)
            # Pravá
        ])

        # Hlavní zavírací chlopeň
        self.lines_fold.append((x2, y1, x3, y1))  # Spodní ohyb
        self.lines_fold.append((x2, y1 + d, x3, y1 + d))  # Ohyb před zasunutím
        self.lines_cut.extend([
            (x2, y1, x2, y1 + d),  # Levý bok
            (x3, y1, x3, y1 + d),  # Pravý bok
            (x2, y1 + d, x2 + 5, y1 + d + tuck),  # Zkosení zasouvání
            (x3, y1 + d, x3 - 5, y1 + d + tuck),
            (x2 + 5, y1 + d + tuck, x3 - 5, y1 + d + tuck)  # Vršek
        ])

        # --- SPODNÍ CHLOPNĚ ---
        # Prachové chlopně
        self.lines_fold.extend([(x1, y0, x2, y0), (x3, y0, x4, y0)])
        self.lines_cut.extend([
            (x1, y0, x1 + 3, y0 - d + 3), (x1 + 3, y0 - d + 3, x2 - 3, y0 - d + 3), (x2 - 3, y0 - d + 3, x2, y0),
            (x3, y0, x3 + 3, y0 - d + 3), (x3 + 3, y0 - d + 3, x4 - 3, y0 - d + 3), (x4 - 3, y0 - d + 3, x4, y0)
        ])

        # Spodní zavírací chlopeň
        self.lines_fold.append((x2, y0, x3, y0))
        self.lines_fold.append((x2, y0 - d, x3, y0 - d))
        self.lines_cut.extend([
            (x2, y0, x2, y0 - d),
            (x3, y0, x3, y0 - d),
            (x2, y0 - d, x2 + 5, y0 - d - tuck),
            (x3, y0 - d, x3 - 5, y0 - d - tuck),
            (x2 + 5, y0 - d - tuck, x3 - 5, y0 - d - tuck)
        ])

    # ==========================================
    # MATEMATIKA: DNO A VÍKO
    # ==========================================
    def calc_base_and_lid(self, w, h, d, lid_d, tol):
        # 1. Vykreslí dno
        self._calc_tray(0, 0, w, h, d)

        # 2. Vykreslí víko (posunuté doprava, zvětšené o toleranci)
        offset_x = w + 2 * d + 30
        self._calc_tray(offset_x, 0, w + tol, h + tol, lid_d)

    def _calc_tray(self, start_x, start_y, w, h, d):
        glue = 15  # Lepicí záložky v rozích

        x0, x1, x2, x3 = start_x, start_x + d, start_x + d + w, start_x + 2 * d + w
        y0, y1, y2, y3 = start_y, start_y + d, start_y + d + h, start_y + 2 * d + h

        # --- OHYBY (FOLD) ---
        self.lines_fold.extend([
            # Stěny vůči dnu
            (x1, y1, x2, y1), (x1, y2, x2, y2),  # Nahoře, dole
            (x1, y1, x1, y2), (x2, y1, x2, y2),  # Vlevo, vpravo

            # Lepicí chlopně vůči levé a pravé stěně
            (x0, y1, x1, y1), (x0, y2, x1, y2),  # Levá stěna - horní/spodní chlopeň
            (x2, y1, x3, y1), (x2, y2, x3, y2)  # Pravá stěna - horní/spodní chlopeň
        ])

        # --- ŘEZY (CUT) ---
        self.lines_cut.extend([
            # Vnější svislé hrany levé a pravé stěny
            (x0, y1, x0, y2), (x3, y1, x3, y2),

            # Vnější hrany horní a spodní stěny (vč. bočních řezů)
            (x1, y0, x2, y0), (x1, y3, x2, y3),  # Horizontální krajní
            (x1, y0, x1, y1), (x2, y0, x2, y1),  # Svislé k horní stěně
            (x1, y2, x1, y3), (x2, y2, x2, y3),  # Svislé ke spodní stěně

            # Lepicí chlopně k levé stěně (nahoře)
            (x0 + 3, y1 - glue, x1 - 3, y1 - glue),  # Horní vodorovná
            (x0, y1, x0 + 3, y1 - glue),  # Levé zkosení
            (x1, y1, x1 - 3, y1 - glue),  # Pravé zkosení (k horní stěně)

            # Lepicí chlopně k levé stěně (dole)
            (x0 + 3, y2 + glue, x1 - 3, y2 + glue),
            (x0, y2, x0 + 3, y2 + glue),
            (x1, y2, x1 - 3, y2 + glue),

            # Lepicí chlopně k pravé stěně (nahoře)
            (x2 + 3, y1 - glue, x3 - 3, y1 - glue),
            (x2, y1, x2 + 3, y1 - glue),
            (x3, y1, x3 - 3, y1 - glue),

            # Lepicí chlopně k pravé stěně (dole)
            (x2 + 3, y2 + glue, x3 - 3, y2 + glue),
            (x2, y2, x2 + 3, y2 + glue),
            (x3, y2, x3 - 3, y2 + glue)
        ])

    # ==========================================
    # MATEMATIKA: DŘEVĚNÁ KRABIČKA (FINGER JOINTS)
    # ==========================================
    def calc_wood_box_baselid(self, w, h, d, lid_d, tol, t, sz):
        self._calc_wood_tray(0, 0, w, h, d, t, sz)
        inner_w = w + 2*t + tol
        inner_h = h + 2*t + tol
        offset_x = w + 2*d + h + 50
        self._calc_wood_tray(offset_x, 0, inner_w, inner_h, lid_d, t, sz)

    def calc_wood_box_sliding(self, w, h, d, tol, t, sz):
        self._calc_wood_tray(0, 0, w, h, d, t, sz)
        # Ploché víko
        offset_x = w + 2*d + h + 50
        lid_w = w - tol
        lid_h = h - tol
        self._draw_toothed_rect(offset_x, 0, lid_w, lid_h, t, sz, top=None, right=None, bottom=None, left=None)

    def _calc_wood_tray(self, start_x, start_y, w, h, d, t, sz):
        gap = 10
        bx, by = start_x + d + gap, start_y + d + gap
        self._draw_toothed_rect(bx, by, w, h, t, sz, top=True, right=True, bottom=True, left=True)
        tx, ty = bx, by - d - gap
        self._draw_toothed_rect(tx, ty, w, d, t, sz, top=None, right=True, bottom=False, left=True)
        box, boy = bx, by + h + gap
        self._draw_toothed_rect(box, boy, w, d, t, sz, top=False, right=True, bottom=None, left=True)
        lx, ly = bx - d - gap, by
        self._draw_toothed_rect(lx, ly, d, h, t, sz, top=False, right=False, bottom=False, left=None)
        rx, ry = bx + w + gap, by
        self._draw_toothed_rect(rx, ry, d, h, t, sz, top=False, right=None, bottom=False, left=False)

    def _get_teeth_path(self, length, tooth_size, is_out, thickness):
        if is_out is None:
            return [(0, 0), (length, 0)]
        n = max(3, int(length / tooth_size))
        if n % 2 == 0: n += 1
        ts = length / n
        pts = []
        for i in range(n):
            out = is_out if (i % 2 == 0) else not is_out
            off = thickness if out else 0
            pts.append((i * ts, off))
            pts.append(((i + 1) * ts, off))
        return pts

    def _draw_toothed_rect(self, X, Y, W, H, t, sz, top, right, bottom, left):
        pts_T = self._get_teeth_path(W, sz, top, t)
        pts_R = self._get_teeth_path(H, sz, right, t)
        pts_B = self._get_teeth_path(W, sz, bottom, t)
        pts_L = self._get_teeth_path(H, sz, left, t)
        
        glob_T = [(X + pos, Y - off) for pos, off in pts_T]
        glob_R = [(X + W + off, Y + pos) for pos, off in pts_R]
        glob_B = [(X + W - pos, Y + H + off) for pos, off in pts_B]
        glob_L = [(X - off, Y + H - pos) for pos, off in pts_L]
        
        poly = []
        poly.extend(glob_T)
        poly.append((glob_R[0][0], glob_T[-1][1])) # TR Corner
        poly.extend(glob_R)
        poly.append((glob_R[-1][0], glob_B[0][1])) # BR Corner
        poly.extend(glob_B)
        poly.append((glob_L[0][0], glob_B[-1][1])) # BL Corner
        poly.extend(glob_L)
        poly.append((glob_L[-1][0], glob_T[0][1])) # TL Corner
        
        for i in range(len(poly)):
            p1 = poly[i]
            p2 = poly[(i+1) % len(poly)]
            if p1 != p2:
                self.lines_cut.append((p1[0], p1[1], p2[0], p2[1]))

    # ==========================================
    # EXPORT DXF
    # ==========================================
    def export_dxf(self):
        if not self.lines_cut: return

        save_path, _ = QFileDialog.getSaveFileName(self, "Uložit DXF křivky", "", "DXF soubory (*.dxf)")
        if not save_path: return

        try:
            doc = ezdxf.new('R2010')
            doc.units = ezdxf.units.MM
            msp = doc.modelspace()

            doc.layers.add(name="CUT", color=1)  # Červená pro řez
            doc.layers.add(name="FOLD", color=5)  # Modrá pro bigování/ohyb

            for line in self.lines_cut:
                msp.add_line((line[0], line[1]), (line[2], line[3]), dxfattribs={'layer': 'CUT'})

            for line in self.lines_fold:
                msp.add_line((line[0], line[1]), (line[2], line[3]), dxfattribs={'layer': 'FOLD'})

            doc.saveas(save_path)
            QMessageBox.information(self, "Hotovo",
                                    f"Uloženo do:\n{save_path}\n\nČervená vrstva = Řez\nModrá vrstva = Ohyb (Bigování)")

        except Exception as e:
            QMessageBox.critical(self, "Chyba", str(e))


if __name__ == "__main__":
    import os
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = BoxGeneratorApp()
    window.show()
    sys.exit(app.exec())