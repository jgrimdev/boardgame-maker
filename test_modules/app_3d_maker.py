import sys
import ezdxf
import trimesh
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.affinity import scale

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QDoubleSpinBox,
                             QRadioButton, QButtonGroup, QFileDialog, QMessageBox,
                             QGraphicsView, QGraphicsScene, QGraphicsPathItem, QGroupBox, QCheckBox)
from PyQt6.QtGui import QPainterPath, QPen, QBrush, QColor, QPainter


class Blender3DExporterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Generátor pro Blender (Import z DXF)")
        self.resize(1050, 750)

        self.original_polygons = []
        self.polygons = []
        self.orig_w = 0.0
        self.orig_h = 0.0
        self.is_updating_spins = False

        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # ====================
        # LEVÝ PANEL (Ovládání)
        # ====================
        left_panel = QWidget()
        left_panel.setFixedWidth(360)
        lyt_left = QVBoxLayout(left_panel)

        grp_load = QGroupBox("1. Vstupní data (DXF)")
        lyt_load = QVBoxLayout()
        self.btn_load = QPushButton("Načíst DXF soubor")
        self.btn_load.setFixedHeight(40)
        self.btn_load.clicked.connect(self.load_dxf_file)
        lyt_load.addWidget(self.btn_load)

        self.lbl_info = QLabel("Načteno tvarů: 0")
        self.lbl_info.setStyleSheet("color: gray; font-style: italic;")
        lyt_load.addWidget(self.lbl_info)

        self.lbl_orig_dims = QLabel("Původní rozměr: --- x --- mm")
        self.lbl_orig_dims.setStyleSheet("font-weight: bold; color: #d35400;")
        lyt_load.addWidget(self.lbl_orig_dims)

        self.chk_resize = QCheckBox("Změnit rozměry objektů")
        self.chk_resize.setEnabled(False)
        self.chk_resize.toggled.connect(self.toggle_resize_inputs)
        self.chk_resize.toggled.connect(self.apply_transformations)
        lyt_load.addWidget(self.chk_resize)

        self.chk_keep_aspect = QCheckBox("Uzamknout poměr stran")
        self.chk_keep_aspect.setChecked(True)
        self.chk_keep_aspect.setEnabled(False)
        lyt_load.addWidget(self.chk_keep_aspect)

        lyt_width = QHBoxLayout()
        lyt_width.addWidget(QLabel("Šířka (mm):"))
        self.spn_width = QDoubleSpinBox()
        self.spn_width.setRange(1.0, 10000.0)
        self.spn_width.setDecimals(2)
        self.spn_width.setEnabled(False)
        self.spn_width.valueChanged.connect(self.on_width_changed)
        lyt_width.addWidget(self.spn_width)
        lyt_load.addLayout(lyt_width)

        lyt_height = QHBoxLayout()
        lyt_height.addWidget(QLabel("Výška (mm):"))
        self.spn_height = QDoubleSpinBox()
        self.spn_height.setRange(1.0, 10000.0)
        self.spn_height.setDecimals(2)
        self.spn_height.setEnabled(False)
        self.spn_height.valueChanged.connect(self.on_height_changed)
        lyt_height.addWidget(self.spn_height)
        lyt_load.addLayout(lyt_height)

        grp_load.setLayout(lyt_load)
        lyt_left.addWidget(grp_load)

        grp_settings = QGroupBox("2. Nastavení generování")
        lyt_settings = QVBoxLayout()

        self.rad_solid = QRadioButton("Vysunout jako 3D Tvary (Žetony)")
        self.rad_hole = QRadioButton("Vyříznout do desky (Výřezy)")
        self.rad_solid.setChecked(True)

        self.btn_group = QButtonGroup()
        self.btn_group.addButton(self.rad_solid)
        self.btn_group.addButton(self.rad_hole)
        self.btn_group.buttonToggled.connect(self.update_preview)

        lyt_settings.addWidget(self.rad_solid)
        lyt_settings.addWidget(self.rad_hole)

        lyt_thick = QHBoxLayout()
        lyt_thick.addWidget(QLabel("Tloušťka materiálu (mm):"))
        self.spn_thick = QDoubleSpinBox()
        self.spn_thick.setRange(0.1, 500.0)
        self.spn_thick.setValue(3.0)
        lyt_thick.addWidget(self.spn_thick)
        lyt_settings.addLayout(lyt_thick)

        lyt_margin = QHBoxLayout()
        lyt_margin.addWidget(QLabel("Okraj vnější desky (mm):"))
        self.spn_margin = QDoubleSpinBox()
        self.spn_margin.setRange(0.0, 500.0)
        self.spn_margin.setValue(20.0)
        self.spn_margin.valueChanged.connect(self.update_preview)
        lyt_margin.addWidget(self.spn_margin)
        lyt_settings.addLayout(lyt_margin)

        self.lbl_final_dims = QLabel("Výsledný rozměr: --- x --- mm")
        self.lbl_final_dims.setStyleSheet("font-weight: bold; color: #2980b9; margin-top: 10px;")
        lyt_settings.addWidget(self.lbl_final_dims)

        grp_settings.setLayout(lyt_settings)
        lyt_left.addWidget(grp_settings)

        lyt_left.addStretch()

        grp_export = QGroupBox("3. Export do Blenderu")
        lyt_export = QVBoxLayout()
        self.btn_export = QPushButton("Exportovat jako OBJ")
        self.btn_export.setFixedHeight(50)
        self.btn_export.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_to_obj)
        lyt_export.addWidget(self.btn_export)
        grp_export.setLayout(lyt_export)
        lyt_left.addWidget(grp_export)

        main_layout.addWidget(left_panel)

        # ====================
        # PRAVÝ PANEL (Náhled)
        # ====================
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(QBrush(QColor("#2c3e50")))
        main_layout.addWidget(self.view)

        self.preview_item = QGraphicsPathItem()
        self.scene.addItem(self.preview_item)

    def load_dxf_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Vybrat DXF", "", "DXF soubory (*.dxf)")
        if not file_path: return

        try:
            doc = ezdxf.readfile(file_path)
            msp = doc.modelspace()

            raw_polygons = []
            for entity in msp.query('LWPOLYLINE'):
                pts = [(p[0], p[1]) for p in entity.get_points(format='xy')]
                if len(pts) >= 3:
                    poly = Polygon(pts)
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    if poly.area > 0:
                        raw_polygons.append(poly)

            if not raw_polygons:
                QMessageBox.warning(self, "Chyba", "V DXF nebyly nalezeny žádné křivky.")
                return

            # --- DETEKCE DĚR (Hierarchie polygonů) ---
            # 1. Seřadíme od největšího po nejmenší
            raw_polygons.sort(key=lambda p: p.area, reverse=True)

            # 2. Vytvoříme uzly s informacemi
            nodes = [{'poly': p, 'holes': [], 'is_hole': False} for p in raw_polygons]

            # 3. Určíme, co je uvnitř čeho
            for i in range(len(nodes)):
                parent_idx = -1
                # Zpětný chod najde ten NEJMENŠÍ polygon, do kterého se tento vejde
                for j in range(i - 1, -1, -1):
                    if nodes[j]['poly'].contains(nodes[i]['poly']):
                        parent_idx = j
                        break

                if parent_idx != -1:
                    # Pokud rodič není díra, tak toto JE díra
                    if not nodes[parent_idx]['is_hole']:
                        nodes[i]['is_hole'] = True
                        nodes[parent_idx]['holes'].append(nodes[i]['poly'].exterior)
                    else:
                        # Pokud je rodič díra, tohle je plný ostrůvek uvnitř díry!
                        nodes[i]['is_hole'] = False
                else:
                    nodes[i]['is_hole'] = False

            # 4. Sestavení finálních polygonů s definovanými dírami
            self.original_polygons = []
            for node in nodes:
                if not node['is_hole']:
                    # Vytvoření Shapely polygonu, který do sebe zapisuje i své vnitřní díry
                    final_poly = Polygon(node['poly'].exterior, node['holes'])
                    if not final_poly.is_valid:
                        final_poly = final_poly.buffer(0)
                    self.original_polygons.append(final_poly)

            self.lbl_info.setText(f"Načteno plných tvarů: {len(self.original_polygons)}")

            # Výpočet původní obálky
            minx = min(p.bounds[0] for p in self.original_polygons)
            miny = min(p.bounds[1] for p in self.original_polygons)
            maxx = max(p.bounds[2] for p in self.original_polygons)
            maxy = max(p.bounds[3] for p in self.original_polygons)
            self.orig_w = maxx - minx
            self.orig_h = maxy - miny

            self.lbl_orig_dims.setText(f"Původní rozměr: {self.orig_w:.1f} x {self.orig_h:.1f} mm")

            self.is_updating_spins = True
            self.spn_width.setValue(self.orig_w)
            self.spn_height.setValue(self.orig_h)
            self.is_updating_spins = False

            self.chk_resize.setEnabled(True)
            self.btn_export.setEnabled(True)

            self.apply_transformations()

        except Exception as e:
            QMessageBox.critical(self, "Chyba při čtení DXF", str(e))

    def toggle_resize_inputs(self, checked):
        self.chk_keep_aspect.setEnabled(checked)
        self.spn_width.setEnabled(checked)
        self.spn_height.setEnabled(checked)

    def on_width_changed(self, val):
        if self.is_updating_spins or self.orig_w == 0: return
        self.is_updating_spins = True

        if self.chk_keep_aspect.isChecked():
            ratio = val / self.orig_w
            self.spn_height.setValue(self.orig_h * ratio)

        self.apply_transformations()
        self.is_updating_spins = False

    def on_height_changed(self, val):
        if self.is_updating_spins or self.orig_h == 0: return
        self.is_updating_spins = True

        if self.chk_keep_aspect.isChecked():
            ratio = val / self.orig_h
            self.spn_width.setValue(self.orig_w * ratio)

        self.apply_transformations()
        self.is_updating_spins = False

    def apply_transformations(self):
        if not self.original_polygons or self.orig_w == 0 or self.orig_h == 0: return

        if self.chk_resize.isChecked():
            scale_x = self.spn_width.value() / self.orig_w
            scale_y = self.spn_height.value() / self.orig_h
        else:
            scale_x = 1.0
            scale_y = 1.0

        self.polygons = []
        for p in self.original_polygons:
            scaled_p = scale(p, xfact=scale_x, yfact=scale_y, origin=(0, 0))
            self.polygons.append(scaled_p)

        self.update_preview()

    def update_preview(self):
        if not self.polygons: return

        is_hole_mode = self.rad_hole.isChecked()
        self.spn_margin.setEnabled(is_hole_mode)

        minx = min(p.bounds[0] for p in self.polygons)
        miny = min(p.bounds[1] for p in self.polygons)
        maxx = max(p.bounds[2] for p in self.polygons)
        maxy = max(p.bounds[3] for p in self.polygons)
        cur_w = maxx - minx
        cur_h = maxy - miny

        margin = self.spn_margin.value() if is_hole_mode else 0.0

        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)

        if is_hole_mode:
            final_w = cur_w + 2 * margin
            final_h = cur_h + 2 * margin
            self.lbl_final_dims.setText(f"Výsledná deska: {final_w:.1f} x {final_h:.1f} mm")

            path.addRect(minx - margin, -(maxy + margin), final_w, final_h)
            for poly in self.polygons:
                self._add_polygon_to_path(poly, path)

            self.preview_item.setBrush(QBrush(QColor(150, 150, 150, 200)))
            self.preview_item.setPen(QPen(QColor(255, 255, 255), 1.0))
        else:
            self.lbl_final_dims.setText(f"Zabraná oblast: {cur_w:.1f} x {cur_h:.1f} mm")

            for poly in self.polygons:
                self._add_polygon_to_path(poly, path)

            self.preview_item.setBrush(QBrush(QColor(52, 152, 219, 200)))
            self.preview_item.setPen(QPen(QColor(41, 128, 185), 1.5))

        self.preview_item.setPath(path)
        self.view.fitInView(self.preview_item.boundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _add_polygon_to_path(self, poly, path):
        # 1. Přidání vnějšího obrysu
        coords = list(poly.exterior.coords)
        subpath = QPainterPath()
        subpath.moveTo(coords[0][0], -coords[0][1])
        for x, y in coords[1:]:
            subpath.lineTo(x, -y)
        path.addPath(subpath)

        # 2. Přidání vnitřních děr (Díky OddEvenFill to QPainterPath pochopí jako prázdno)
        for interior in poly.interiors:
            coords = list(interior.coords)
            subpath = QPainterPath()
            subpath.moveTo(coords[0][0], -coords[0][1])
            for x, y in coords[1:]:
                subpath.lineTo(x, -y)
            path.addPath(subpath)

    def export_to_obj(self):
        if not self.polygons: return

        save_path, _ = QFileDialog.getSaveFileName(self, "Uložit jako OBJ", "", "OBJ files (*.obj)")
        if not save_path: return

        try:
            self.setCursor(Qt.CursorShape.WaitCursor)
            thickness = self.spn_thick.value()
            meshes_to_combine = []

            if self.rad_solid.isChecked():
                for poly in self.polygons:
                    mesh = trimesh.creation.extrude_polygon(poly, height=thickness)
                    meshes_to_combine.append(mesh)
            else:
                minx = min(p.bounds[0] for p in self.polygons)
                miny = min(p.bounds[1] for p in self.polygons)
                maxx = max(p.bounds[2] for p in self.polygons)
                maxy = max(p.bounds[3] for p in self.polygons)

                margin = self.spn_margin.value()
                board_rect = box(minx - margin, miny - margin, maxx + margin, maxy + margin)

                all_holes = unary_union(self.polygons)
                board_with_holes = board_rect.difference(all_holes)

                if board_with_holes.geom_type == 'MultiPolygon':
                    for geom in board_with_holes.geoms:
                        mesh = trimesh.creation.extrude_polygon(geom, height=thickness)
                        meshes_to_combine.append(mesh)
                else:
                    mesh = trimesh.creation.extrude_polygon(board_with_holes, height=thickness)
                    meshes_to_combine.append(mesh)

            final_mesh = trimesh.util.concatenate(meshes_to_combine)
            final_mesh.export(save_path)

            QMessageBox.information(self, "Hotovo", f"Uloženo do:\n{save_path}")

        except ValueError as e:
            if "triangulation" in str(e).lower():
                QMessageBox.critical(self, "Chybí knihovna!",
                                     "Knihovna Trimesh nemůže rozřezat plochu (triangulace).\n\n"
                                     "Otevři terminál a nainstaluj:\n"
                                     "pip install mapbox-earcut")
            else:
                QMessageBox.critical(self, "Chyba Exportu", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Neznámá Chyba", str(e))
        finally:
            self.setCursor(Qt.CursorShape.ArrowCursor)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = Blender3DExporterGUI()
    window.show()
    sys.exit(app.exec())