import sys
import ezdxf
import trimesh
import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.affinity import scale

from trimesh.visual.material import PBRMaterial
from trimesh.visual import TextureVisuals

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QDoubleSpinBox,
                             QRadioButton, QButtonGroup, QFileDialog, QMessageBox,
                             QGraphicsView, QGraphicsScene, QGraphicsPathItem, QGroupBox, QCheckBox,
                             QTabWidget)
from PyQt6.QtGui import QPainterPath, QPen, QBrush, QColor, QPainter

# Pokus o import knihoven pro 3D náhled
try:
    import pyqtgraph.opengl as gl

    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False


class Blender3DExporterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Generátor pro Blender (CAD Shading & Toggle)")
        self.resize(1200, 800)

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
        left_panel.setFixedWidth(380)
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

        grp_settings = QGroupBox("2. Nastavení sestavy")
        lyt_settings = QVBoxLayout()

        self.rad_solid = QRadioButton("Vysunout jako 3D Tvary (Žetony)")
        self.rad_hole = QRadioButton("Sestava cedule (Přední, Zadní, LED)")
        self.rad_hole.setChecked(True)

        self.btn_group = QButtonGroup()
        self.btn_group.addButton(self.rad_solid)
        self.btn_group.addButton(self.rad_hole)
        self.btn_group.buttonToggled.connect(self.update_preview)

        lyt_settings.addWidget(self.rad_solid)
        lyt_settings.addWidget(self.rad_hole)

        lyt_thick = QHBoxLayout()
        lyt_thick.addWidget(QLabel("Tloušťka překližky (mm):"))
        self.spn_thick = QDoubleSpinBox()
        self.spn_thick.setRange(0.1, 50.0)
        self.spn_thick.setValue(5.0)
        self.spn_thick.valueChanged.connect(self.update_preview)
        lyt_thick.addWidget(self.spn_thick)
        lyt_settings.addLayout(lyt_thick)

        lyt_gap = QHBoxLayout()
        lyt_gap.addWidget(QLabel("Mezera pro LED (mm):"))
        self.spn_gap = QDoubleSpinBox()
        self.spn_gap.setRange(5.0, 100.0)
        self.spn_gap.setValue(25.0)
        self.spn_gap.valueChanged.connect(self.update_preview)
        lyt_gap.addWidget(self.spn_gap)
        lyt_settings.addLayout(lyt_gap)

        lyt_margin = QHBoxLayout()
        lyt_margin.addWidget(QLabel("Okraj vnější desky (mm):"))
        self.spn_margin = QDoubleSpinBox()
        self.spn_margin.setRange(0.0, 500.0)
        self.spn_margin.setValue(35.0)
        self.spn_margin.valueChanged.connect(self.update_preview)
        lyt_margin.addWidget(self.spn_margin)
        lyt_settings.addLayout(lyt_margin)

        lyt_standoff = QHBoxLayout()
        lyt_standoff.addWidget(QLabel("Sloupky od okraje (mm):"))
        self.spn_standoff_margin = QDoubleSpinBox()
        self.spn_standoff_margin.setRange(5.0, 100.0)
        self.spn_standoff_margin.setValue(15.0)
        self.spn_standoff_margin.valueChanged.connect(self.update_preview)
        lyt_standoff.addWidget(self.spn_standoff_margin)
        lyt_settings.addLayout(lyt_standoff)

        self.chk_screws = QCheckBox("Přidat spojovací šrouby zepředu")
        self.chk_screws.setChecked(True)
        self.chk_screws.stateChanged.connect(self.update_preview)
        self.chk_screws.stateChanged.connect(lambda: self.spn_screw_dia.setEnabled(self.chk_screws.isChecked()))
        lyt_settings.addWidget(self.chk_screws)

        lyt_screw_size = QHBoxLayout()
        lyt_screw_size.addWidget(QLabel("Průměr hlavy šroubu (mm):"))
        self.spn_screw_dia = QDoubleSpinBox()
        self.spn_screw_dia.setRange(2.0, 50.0)
        self.spn_screw_dia.setValue(7.6)
        self.spn_screw_dia.valueChanged.connect(self.update_preview)
        lyt_screw_size.addWidget(self.spn_screw_dia)
        lyt_settings.addLayout(lyt_screw_size)

        # NOVÉ: Přepínač hran ve 3D
        self.chk_wireframe = QCheckBox("Zobrazit hrany ve 3D náhledu (Wireframe)")
        self.chk_wireframe.setChecked(False)
        self.chk_wireframe.stateChanged.connect(self.update_preview)
        self.chk_wireframe.setStyleSheet("font-weight: bold; color: #8e44ad; margin-top: 10px;")
        lyt_settings.addWidget(self.chk_wireframe)

        self.lbl_final_dims = QLabel("Výsledný rozměr: --- x --- mm")
        self.lbl_final_dims.setStyleSheet("font-weight: bold; color: #2980b9; margin-top: 5px;")
        lyt_settings.addWidget(self.lbl_final_dims)

        grp_settings.setLayout(lyt_settings)
        lyt_left.addWidget(grp_settings)

        lyt_left.addStretch()

        grp_export = QGroupBox("3. Export do Blenderu")
        lyt_export = QVBoxLayout()
        self.btn_export = QPushButton("Exportovat jako GLB")
        self.btn_export.setFixedHeight(50)
        self.btn_export.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_to_glb)
        lyt_export.addWidget(self.btn_export)
        grp_export.setLayout(lyt_export)
        lyt_left.addWidget(grp_export)

        main_layout.addWidget(left_panel)

        # ====================
        # PRAVÝ PANEL (Karty 2D/3D)
        # ====================
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Karta 1: 2D Náhled
        self.scene_2d = QGraphicsScene()
        self.view_2d = QGraphicsView(self.scene_2d)
        self.view_2d.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view_2d.setBackgroundBrush(QBrush(QColor("#2c3e50")))

        self.preview_item = QGraphicsPathItem()
        self.scene_2d.addItem(self.preview_item)

        self.screws_2d_item = QGraphicsPathItem()
        self.screws_2d_item.setBrush(QBrush(QColor(180, 180, 180, 255)))
        self.screws_2d_item.setPen(QPen(QColor(100, 100, 100), 1.0))
        self.scene_2d.addItem(self.screws_2d_item)

        self.tabs.addTab(self.view_2d, "2D Vektorový náhled")

        # Karta 2: 3D Náhled
        if HAS_PYQTGRAPH:
            self.view_3d = gl.GLViewWidget()
            # Tmavší a elegantnější pozadí
            self.view_3d.setBackgroundColor((35, 45, 55, 255))
            self.tabs.addTab(self.view_3d, "3D Prostorový náhled")
        else:
            lbl_no3d = QLabel(
                "Pro 3D náhled chybí knihovny.\nOtevři terminál a napiš:\n\npip install pyqtgraph PyOpenGL")
            lbl_no3d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_no3d.setStyleSheet("font-size: 16px; color: red;")
            self.tabs.addTab(lbl_no3d, "3D Prostorový náhled (Nedostupné)")

        self.tabs.currentChanged.connect(self.update_preview)

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

            raw_polygons.sort(key=lambda p: p.area, reverse=True)
            nodes = [{'poly': p, 'holes': [], 'is_hole': False} for p in raw_polygons]

            for i in range(len(nodes)):
                parent_idx = -1
                for j in range(i - 1, -1, -1):
                    if nodes[j]['poly'].contains(nodes[i]['poly']):
                        parent_idx = j
                        break

                if parent_idx != -1:
                    if not nodes[parent_idx]['is_hole']:
                        nodes[i]['is_hole'] = True
                        nodes[parent_idx]['holes'].append(nodes[i]['poly'].exterior)
                    else:
                        nodes[i]['is_hole'] = False
                else:
                    nodes[i]['is_hole'] = False

            self.original_polygons = []
            for node in nodes:
                if not node['is_hole']:
                    final_poly = Polygon(node['poly'].exterior, node['holes'])
                    if not final_poly.is_valid:
                        final_poly = final_poly.buffer(0)
                    self.original_polygons.append(final_poly)

            self.lbl_info.setText(f"Načteno plných tvarů: {len(self.original_polygons)}")

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

    def _get_standoff_points(self, minx, miny, maxx, maxy, margin, standoff_margin):
        points = [
            (minx - margin + standoff_margin, miny - margin + standoff_margin),
            (maxx + margin - standoff_margin, miny - margin + standoff_margin),
            (minx - margin + standoff_margin, maxy + margin - standoff_margin),
            (maxx + margin - standoff_margin, maxy + margin - standoff_margin)
        ]

        for poly in self.polygons:
            for interior in poly.interiors:
                island = Polygon(interior)
                points.append((island.centroid.x, island.centroid.y))

        return points

    def generate_scene_objects(self):
        objects = []
        if not self.polygons: return objects

        thickness = self.spn_thick.value()
        gap = self.spn_gap.value()
        margin = self.spn_margin.value()
        standoff_margin = self.spn_standoff_margin.value()
        screw_dia = self.spn_screw_dia.value()

        # Materiály pro GLB export
        mat_front = PBRMaterial(name="Mat_Wood_Front", baseColorFactor=[210, 180, 140, 255])
        mat_back = PBRMaterial(name="Mat_Wood_Back", baseColorFactor=[160, 130, 90, 255])
        mat_metal = PBRMaterial(name="Mat_Metal_Standoff", baseColorFactor=[200, 200, 200, 255], metallicFactor=1.0,
                                roughnessFactor=0.3)
        mat_led = PBRMaterial(name="Mat_Emission_LED", baseColorFactor=[255, 230, 100, 255])
        mat_solid = PBRMaterial(name="Mat_Solid_Shape", baseColorFactor=[52, 152, 219, 255])

        if self.rad_solid.isChecked():
            for i, poly in enumerate(self.polygons):
                mesh = trimesh.creation.extrude_polygon(poly, height=thickness)
                objects.append({'mesh': mesh, 'name': f"Shape_{i}", 'color': [52, 152, 219, 255], 'mat': mat_solid})
        else:
            minx = min(p.bounds[0] for p in self.polygons)
            miny = min(p.bounds[1] for p in self.polygons)
            maxx = max(p.bounds[2] for p in self.polygons)
            maxy = max(p.bounds[3] for p in self.polygons)

            board_rect = box(minx - margin, miny - margin, maxx + margin, maxy + margin)
            all_holes = unary_union(self.polygons)
            board_with_holes = board_rect.difference(all_holes)

            if board_with_holes.geom_type == 'MultiPolygon':
                front_meshes = [trimesh.creation.extrude_polygon(geom, height=thickness) for geom in
                                board_with_holes.geoms]
                front_mesh = trimesh.util.concatenate(front_meshes)
            else:
                front_mesh = trimesh.creation.extrude_polygon(board_with_holes, height=thickness)
            objects.append({'mesh': front_mesh, 'name': "Front_Board", 'color': [210, 180, 140, 255], 'mat': mat_front})

            back_mesh = trimesh.creation.extrude_polygon(board_rect, height=thickness)
            back_mesh.apply_translation([0, 0, -gap - thickness])
            objects.append({'mesh': back_mesh, 'name': "Back_Board", 'color': [160, 130, 90, 255], 'mat': mat_back})

            standoff_points = self._get_standoff_points(minx, miny, maxx, maxy, margin, standoff_margin)

            post_meshes = []
            screw_meshes = []
            head_radius = screw_dia / 2.0

            for cx, cy in standoff_points:
                cylinder = trimesh.creation.cylinder(radius=6.0, height=gap)
                cylinder.apply_translation([cx, cy, -gap / 2])
                post_meshes.append(cylinder)

                if self.chk_screws.isChecked():
                    screw = trimesh.creation.cylinder(radius=head_radius, height=1.0)
                    screw.apply_translation([cx, cy, thickness + 0.5])
                    screw_meshes.append(screw)

            if post_meshes:
                standoffs_combined = trimesh.util.concatenate(post_meshes)
                objects.append(
                    {'mesh': standoffs_combined, 'name': "Standoffs", 'color': [200, 200, 200, 255], 'mat': mat_metal})
            if screw_meshes:
                screws_combined = trimesh.util.concatenate(screw_meshes)
                objects.append(
                    {'mesh': screws_combined, 'name': "Screws", 'color': [180, 180, 180, 255], 'mat': mat_metal})

            led_thickness = 10.0
            led_outer = box(standoff_points[0][0], standoff_points[0][1], standoff_points[3][0], standoff_points[3][1])
            led_inner = led_outer.buffer(-6.0)
            led_poly = led_outer.difference(led_inner)

            led_mesh = trimesh.creation.extrude_polygon(led_poly, height=led_thickness)
            led_mesh.apply_translation([0, 0, -led_thickness - 2.0])
            objects.append({'mesh': led_mesh, 'name': "LED_Strip_Frame", 'color': [255, 230, 100, 255], 'mat': mat_led})

        return objects

    def update_preview(self):
        if not self.polygons: return

        # -----------------------------
        # AKTUALIZACE 2D ZÁLOŽKY
        # -----------------------------
        is_hole_mode = self.rad_hole.isChecked()
        self.spn_margin.setEnabled(is_hole_mode)
        self.spn_gap.setEnabled(is_hole_mode)
        self.spn_standoff_margin.setEnabled(is_hole_mode)
        self.chk_screws.setEnabled(is_hole_mode)
        self.spn_screw_dia.setEnabled(is_hole_mode and self.chk_screws.isChecked())

        minx = min(p.bounds[0] for p in self.polygons)
        miny = min(p.bounds[1] for p in self.polygons)
        maxx = max(p.bounds[2] for p in self.polygons)
        maxy = max(p.bounds[3] for p in self.polygons)
        cur_w = maxx - minx
        cur_h = maxy - miny
        margin = self.spn_margin.value() if is_hole_mode else 0.0

        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        screw_path = QPainterPath()

        if is_hole_mode:
            final_w = cur_w + 2 * margin
            final_h = cur_h + 2 * margin
            self.lbl_final_dims.setText(f"Výsledná deska: {final_w:.1f} x {final_h:.1f} mm")

            path.addRect(minx - margin, -(maxy + margin), final_w, final_h)
            for poly in self.polygons:
                self._add_polygon_to_path(poly, path)

            self.preview_item.setBrush(QBrush(QColor(210, 180, 140, 200)))
            self.preview_item.setPen(QPen(QColor(139, 69, 19), 1.5))

            if self.chk_screws.isChecked():
                standoff_margin = self.spn_standoff_margin.value()
                head_radius = self.spn_screw_dia.value() / 2.0
                pts = self._get_standoff_points(minx, miny, maxx, maxy, margin, standoff_margin)
                for cx, cy in pts:
                    screw_path.addEllipse(cx - head_radius, -cy - head_radius, head_radius * 2, head_radius * 2)

        else:
            self.lbl_final_dims.setText(f"Zabraná oblast: {cur_w:.1f} x {cur_h:.1f} mm")
            for poly in self.polygons:
                self._add_polygon_to_path(poly, path)
            self.preview_item.setBrush(QBrush(QColor(52, 152, 219, 200)))
            self.preview_item.setPen(QPen(QColor(41, 128, 185), 1.5))

        self.preview_item.setPath(path)
        self.screws_2d_item.setPath(screw_path)

        self.view_2d.fitInView(self.preview_item.boundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

        # -----------------------------
        # AKTUALIZACE 3D ZÁLOŽKY
        # -----------------------------
        if HAS_PYQTGRAPH and self.tabs.currentIndex() == 1:
            self.view_3d.clear()
            scene_objects = self.generate_scene_objects()

            # Nastavení virtuálního světla pro náš Flat Shading
            light_dir = np.array([0.4, -0.6, 0.8])
            light_dir = light_dir / np.linalg.norm(light_dir)
            ambient_light = 0.4

            show_wireframe = self.chk_wireframe.isChecked()

            for obj in scene_objects:
                mesh = obj['mesh']
                if mesh.is_empty: continue

                verts = mesh.vertices
                faces = mesh.faces
                c = obj['color']

                # Základní barva plochy (RGBA 0.0 - 1.0)
                base_color = np.array([c[0] / 255, c[1] / 255, c[2] / 255, 1.0])

                # --- VÝPOČET FLAT SHADINGU (Ploché stínování CAD stylu) ---
                normals = mesh.face_normals
                # Vypočítáme, jak moc světlo dopadá na danou plochu (Dot product)
                diffuse_light = np.clip(np.dot(normals, light_dir), 0, 1) * 0.6
                intensity = ambient_light + diffuse_light

                # Aplikujeme spočítanou intenzitu světla na každou plochu zvlášť
                face_colors = np.tile(base_color, (len(faces), 1))
                face_colors[:, :3] *= intensity[:, np.newaxis]

                mesh_item = gl.GLMeshItem(
                    vertexes=verts,
                    faces=faces,
                    faceColors=face_colors,  # Předáváme naše nasvícené barvy
                    smooth=False,  # Nechceme rozmazané/kulaté stíny
                    drawEdges=show_wireframe,  # Přepínač hran
                    edgeColor=(0, 0, 0, 0.5),  # Poloprůhledná černá pro hrany
                    shader=None  # Vypneme integrované ošklivé shadery!
                )
                self.view_3d.addItem(mesh_item)

            self.view_3d.opts['distance'] = max(cur_w, cur_h) * 1.5
            self.view_3d.opts['center'] = pg.Vector(minx + cur_w / 2, miny + cur_h / 2,
                                                    0) if 'pg' in globals() else None

    def _add_polygon_to_path(self, poly, path):
        coords = list(poly.exterior.coords)
        subpath = QPainterPath()
        subpath.moveTo(coords[0][0], -coords[0][1])
        for x, y in coords[1:]:
            subpath.lineTo(x, -y)
        path.addPath(subpath)

        for interior in poly.interiors:
            coords = list(interior.coords)
            subpath = QPainterPath()
            subpath.moveTo(coords[0][0], -coords[0][1])
            for x, y in coords[1:]:
                subpath.lineTo(x, -y)
            path.addPath(subpath)

    def export_to_glb(self):
        if not self.polygons: return

        save_path, _ = QFileDialog.getSaveFileName(self, "Uložit jako GLB", "", "GLB files (*.glb)")
        if not save_path: return

        try:
            self.setCursor(Qt.CursorShape.WaitCursor)

            scene_objects = self.generate_scene_objects()
            scene = trimesh.Scene()

            for obj in scene_objects:
                mesh = obj['mesh']
                mesh.visual = TextureVisuals(material=obj['mat'])
                scene.add_geometry(mesh, node_name=obj['name'], geom_name=obj['name'])

            scene.export(save_path)
            QMessageBox.information(self, "Hotovo", f"Sestava uložena do:\n{save_path}")

        except Exception as e:
            QMessageBox.critical(self, "Chyba Exportu", str(e))
        finally:
            self.setCursor(Qt.CursorShape.ArrowCursor)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    if HAS_PYQTGRAPH:
        import pyqtgraph as pg

    window = Blender3DExporterGUI()
    window.show()
    sys.exit(app.exec())