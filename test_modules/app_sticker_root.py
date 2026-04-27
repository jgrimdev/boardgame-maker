import sys
import cv2
import numpy as np
import fitz  # PyMuPDF
import ezdxf
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QSlider, QCheckBox,
                             QGroupBox, QFileDialog, QMessageBox, QGraphicsView,
                             QGraphicsScene, QGraphicsPixmapItem, QFrame,
                             QTabWidget, QSpinBox, QDoubleSpinBox, QComboBox,
                             QFormLayout, QRadioButton, QScrollArea)
from PyQt6.QtGui import QImage, QPixmap, QPainter


class GraphicsViewZoom(QGraphicsView):
    clicked_scene = pyqtSignal(float, float)

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.zoom_factor = 1.15
        self.mouse_action = "none"

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            factor = self.zoom_factor
        else:
            factor = 1.0 / self.zoom_factor

        old_pos = self.mapToScene(event.position().toPoint())
        self.scale(factor, factor)
        new_pos = self.mapToScene(event.position().toPoint())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

    def mousePressEvent(self, event):
        if self.mouse_action != "none" and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            self.clicked_scene.emit(scene_pos.x(), scene_pos.y())
            return
        super().mousePressEvent(event)


class ModernLaserGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self._ui_loaded = False
        self.setWindowTitle("Generátor DXF - Ultimátní PnP Nástroj (Kráječ + Detekce)")
        self.resize(1550, 950)

        self.dpi = 300
        self.fiducial_radius_mm = 0.2

        self.cv_img_bgr = None
        self.img_height_px = 0
        self.img_width_px = 0

        self.auto_contours = []
        self.edge_contours = []
        self.fiducial_points = []

        self.calc_timer = QTimer()
        self.calc_timer.setSingleShot(True)
        self.calc_timer.timeout.connect(self.run_calculations)

        self._init_ui()
        self._ui_loaded = True

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        self.scene = QGraphicsScene()
        self.view = GraphicsViewZoom(self.scene)
        self.view.setStyleSheet("background-color: #1e1e1e;")
        self.view.clicked_scene.connect(self.handle_scene_click)

        self.img_item = QGraphicsPixmapItem()
        self.cut_item = QGraphicsPixmapItem()
        self.scene.addItem(self.img_item)
        self.scene.addItem(self.cut_item)

        # ==========================================
        # LEVÝ PANEL
        # ==========================================
        scroll_panel = QScrollArea()
        scroll_panel.setFixedWidth(440)
        scroll_panel.setWidgetResizable(True)
        scroll_panel.setFrameShape(QFrame.Shape.NoFrame)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(10)

        # --- 1. VSTUP ---
        grp_load = QGroupBox("1. Vstupní data")
        lyt_load = QVBoxLayout()
        self.btn_load = QPushButton("Načíst Soubor (PDF / PNG / JPG)")
        self.btn_load.setFixedHeight(40)
        self.btn_load.clicked.connect(self.load_file)
        self.chk_force_a4 = QCheckBox("Vynutit formát A4 (Zruš pro absolutně přesné mm!)")
        self.chk_force_a4.setChecked(False)
        self.chk_force_a4.setStyleSheet("color: #d32f2f; font-weight: bold;")
        lyt_load.addWidget(self.btn_load)
        lyt_load.addWidget(self.chk_force_a4)
        grp_load.setLayout(lyt_load)
        left_layout.addWidget(grp_load)

        # --- 2. GLOBLÁLNÍ ROZMĚRY TVARŮ ---
        grp_dims = QGroupBox("2. Rozměry tvarů (v mm)")
        grp_dims.setStyleSheet("background-color: #e3f2fd;")
        form_dims = QFormLayout(grp_dims)

        self.dim_circle_d = self._create_double_spinbox(1.0, 500.0, 19.7, self.queue_calc)
        self.dim_sq_w = self._create_double_spinbox(1.0, 500.0, 17.6, self.queue_calc)
        self.dim_sq_h = self._create_double_spinbox(1.0, 500.0, 17.6, self.queue_calc)
        self.dim_sq_r = self._create_double_spinbox(0.0, 100.0, 2.0, self.queue_calc)

        form_dims.addRow(QLabel("<b>Kolečko:</b>"))
        form_dims.addRow("Průměr (mm):", self.dim_circle_d)
        form_dims.addRow(QLabel("<b>Čtvereček / Obdélník:</b>"))
        form_dims.addRow("Šířka (mm):", self.dim_sq_w)
        form_dims.addRow("Výška (mm):", self.dim_sq_h)
        form_dims.addRow("Zaoblení rohů (mm):", self.dim_sq_r)
        left_layout.addWidget(grp_dims)

        # --- 3. ZÁLOŽKY DETEKCE ---
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.tab_changed)

        # TAB A: AUTO DETEKCE (Fleky)
        tab_auto = QWidget()
        lyt_auto = QVBoxLayout(tab_auto)

        self.lbl_thresh = QLabel("Práh kontrastu: 240")
        self.sld_thresh = self._create_slider(100, 254, 240, self.lbl_thresh, "Práh kontrastu: {}")
        self.chk_inner_holes = QCheckBox("Vyříznout i vnitřní otvory (Holes)")
        self.chk_inner_holes.toggled.connect(self.queue_calc)

        # TYHLE DVA POSUVNÍKY ZPŮSOBOVALY CHYBU - VRÁCENY!
        self.lbl_noise = QLabel("Odstranit tenké čáry: 0 px")
        self.sld_noise = self._create_slider(0, 20, 0, self.lbl_noise, "Odstranit tenké čáry: {} px")
        self.lbl_offset = QLabel("Ofset (- ven, + dovnitř): 5 px")
        self.sld_offset = self._create_slider(-30, 30, 5, self.lbl_offset, "Ofset (- ven, + dovnitř): {} px")

        self.lbl_close = QLabel("Zacelení děr: 5 px")
        self.sld_close = self._create_slider(0, 50, 5, self.lbl_close, "Zacelení děr: {} px")

        lyt_auto.addWidget(self.lbl_thresh)
        lyt_auto.addWidget(self.sld_thresh)
        lyt_auto.addWidget(self.chk_inner_holes)
        lyt_auto.addWidget(self.lbl_noise)
        lyt_auto.addWidget(self.sld_noise)
        lyt_auto.addWidget(self.lbl_close)
        lyt_auto.addWidget(self.sld_close)
        lyt_auto.addWidget(self.lbl_offset)
        lyt_auto.addWidget(self.sld_offset)

        # ROZKRÁJEČ
        grp_split = QGroupBox("Rozkrájet velké spojené objekty (černý kříž)")
        form_split = QFormLayout(grp_split)
        self.chk_split = QCheckBox("Rozkrájet do mřížky podle rozměrů nahoře")
        self.chk_split.setChecked(True)
        self.chk_split.toggled.connect(self.queue_calc)
        self.cmb_split_shape = QComboBox()
        self.cmb_split_shape.addItems(["Kolečko", "Čtvereček"])
        self.cmb_split_shape.currentIndexChanged.connect(self.queue_calc)
        form_split.addRow(self.chk_split)
        form_split.addRow("Výplň mřížky:", self.cmb_split_shape)
        lyt_auto.addWidget(grp_split)

        self.lbl_area = QLabel("Min. plocha objektu: 500 px")
        self.sld_area = self._create_slider(50, 2000, 500, self.lbl_area, "Min. plocha: {} px", step=50)
        lyt_auto.addWidget(self.lbl_area)
        lyt_auto.addWidget(self.sld_area)
        lyt_auto.addStretch()

        # TAB B: DETEKCE LINEK (Hnědé objekty s bílými linkami)
        tab_edge = QWidget()
        lyt_edge = QVBoxLayout(tab_edge)

        grp_edge_det = QGroupBox("Nastavení hledání linek")
        lyt_edge_det = QVBoxLayout(grp_edge_det)

        self.cmb_edge_shape = QComboBox()
        self.cmb_edge_shape.addItems(["Hledat Zaoblené Čtverce", "Hledat Kolečka"])
        self.cmb_edge_shape.currentIndexChanged.connect(self.queue_calc)
        lyt_edge_det.addWidget(QLabel("Výchozí tvar pro tuto záložku:"))
        lyt_edge_det.addWidget(self.cmb_edge_shape)

        self.lbl_canny = QLabel("Citlivost hledání linek (Nižší = víc linek): 50")
        self.sld_canny = self._create_slider(10, 200, 50, self.lbl_canny, "Citlivost: {}")
        self.lbl_edge_tol = QLabel("Tolerance odchylky rozměru: 30 %")
        self.sld_edge_tol = self._create_slider(5, 80, 30, self.lbl_edge_tol, "Tolerance odchylky rozměru: {} %")
        lyt_edge_det.addWidget(self.lbl_canny)
        lyt_edge_det.addWidget(self.sld_canny)
        lyt_edge_det.addWidget(self.lbl_edge_tol)
        lyt_edge_det.addWidget(self.sld_edge_tol)

        lyt_edge.addWidget(grp_edge_det)
        lyt_edge.addStretch()

        self.tabs.addTab(tab_auto, "Auto Detekce (Krájení Fleků)")
        self.tabs.addTab(tab_edge, "Detekce Linek")
        left_layout.addWidget(self.tabs)

        # --- 4. NÁSTROJE MYŠI ---
        grp_tools = QGroupBox("Nástroje Myši (Klikni do plátna)")
        lyt_tools = QVBoxLayout(grp_tools)

        self.rad_move = QRadioButton("🖐️ Posun plátna (Nic nedělat)")
        self.rad_move.setChecked(True)
        self.rad_move.toggled.connect(self.update_mouse_mode)

        self.rad_stamp_circ = QRadioButton("🟢 Vložit Kolečko (Razítko)")
        self.rad_stamp_circ.toggled.connect(self.update_mouse_mode)

        self.rad_stamp_sq = QRadioButton("🟦 Vložit Čtverec (Razítko)")
        self.rad_stamp_sq.toggled.connect(self.update_mouse_mode)

        self.rad_erase = QRadioButton("🔴 Guma (Smaže tvar)")
        self.rad_erase.toggled.connect(self.update_mouse_mode)

        self.rad_toggle = QRadioButton("🔄 Přepnout tvar (Kruh <-> Čtverec)")
        self.rad_toggle.toggled.connect(self.update_mouse_mode)

        lyt_tools.addWidget(self.rad_move)
        lyt_tools.addWidget(self.rad_stamp_circ)
        lyt_tools.addWidget(self.rad_stamp_sq)
        lyt_tools.addWidget(self.rad_erase)
        lyt_tools.addWidget(self.rad_toggle)

        btn_row = QHBoxLayout()
        self.btn_clear_all = QPushButton("🗑️ Vymazat vše")
        self.btn_clear_all.clicked.connect(self.clear_all_shapes)
        self.btn_regen = QPushButton("⚡ Znovu vygenerovat")
        self.btn_regen.setStyleSheet("background-color: #f57c00; color: white;")
        self.btn_regen.clicked.connect(self.queue_calc)
        btn_row.addWidget(self.btn_clear_all)
        btn_row.addWidget(self.btn_regen)
        lyt_tools.addLayout(btn_row)

        left_layout.addWidget(grp_tools)

        # --- 5. ZOBRAZENÍ A EXPORT ---
        grp_view = QGroupBox("Zobrazení a Export")
        lyt_view = QVBoxLayout()
        self.btn_fit = QPushButton("Přizpůsobit plátno oknu")
        self.btn_fit.clicked.connect(self.fit_view)
        lyt_view.addWidget(self.btn_fit)

        self.chk_show_img = QCheckBox("Ukázat Tisk")
        self.chk_show_img.setChecked(True)
        self.chk_show_img.toggled.connect(self.update_layer_visibility)

        self.lbl_alpha_img = QLabel("Průhlednost tisku: 60%")
        self.sld_alpha_img = self._create_slider(0, 100, 60, self.lbl_alpha_img, "Průhlednost tisku: {}%")
        self.sld_alpha_img.valueChanged.connect(self.update_layer_opacity)

        self.chk_show_cut = QCheckBox("Ukázat Křivky a Značky")
        self.chk_show_cut.setChecked(True)
        self.chk_show_cut.toggled.connect(self.update_layer_visibility)

        self.lbl_alpha_cut = QLabel("Průhlednost křivek: 100%")
        self.sld_alpha_cut = self._create_slider(0, 100, 100, self.lbl_alpha_cut, "Průhlednost křivek: {}%")
        self.sld_alpha_cut.valueChanged.connect(self.update_layer_opacity)

        lyt_view.addWidget(self.chk_show_img)
        lyt_view.addWidget(self.sld_alpha_img)
        lyt_view.addWidget(self.chk_show_cut)
        lyt_view.addWidget(self.lbl_alpha_cut)
        lyt_view.addWidget(self.sld_alpha_cut)

        self.btn_save = QPushButton("Uložit DXF pro Laser")
        self.btn_save.setFixedHeight(50)
        self.btn_save.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #2e7d32; color: white;")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_dxf)
        lyt_view.addWidget(self.btn_save)

        grp_view.setLayout(lyt_view)
        left_layout.addWidget(grp_view)

        left_layout.addStretch()
        scroll_panel.setWidget(left_panel)
        main_layout.addWidget(scroll_panel)
        main_layout.addWidget(self.view)

    # --- POMOCNÉ FUNKCE UI ---
    def _create_slider(self, v_min, v_max, v_default, label_widget, text_format, step=1):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(v_min)
        slider.setMaximum(v_max)
        slider.setValue(v_default)
        slider.setSingleStep(step)

        def update_label(val):
            label_widget.setText(text_format.format(val))

        update_label(v_default)
        slider.valueChanged.connect(update_label)
        slider.valueChanged.connect(self.queue_calc)
        return slider

    def _create_double_spinbox(self, v_min, v_max, v_default, callback):
        spin = QDoubleSpinBox()
        spin.setRange(v_min, v_max)
        spin.setDecimals(1)
        spin.setSingleStep(0.5)
        spin.setValue(v_default)
        spin.valueChanged.connect(callback)
        return spin

    def mm_to_px(self, mm_value):
        return (mm_value * self.dpi) / 25.4

    def px_to_mm(self, px_value):
        return (px_value * 25.4) / self.dpi

    def tab_changed(self, index, *args):
        self.run_calculations()

    def update_mouse_mode(self, *args):
        if self.rad_move.isChecked():
            self.view.mouse_action = "none"
            self.view.setCursor(Qt.CursorShape.ArrowCursor)
            self.view.edit_mode = False
        else:
            self.view.edit_mode = True
            if self.rad_stamp_circ.isChecked():
                self.view.mouse_action = "stamp_circ"
                self.view.setCursor(Qt.CursorShape.CrossCursor)
            elif self.rad_stamp_sq.isChecked():
                self.view.mouse_action = "stamp_sq"
                self.view.setCursor(Qt.CursorShape.CrossCursor)
            elif self.rad_erase.isChecked():
                self.view.mouse_action = "delete"
                self.view.setCursor(Qt.CursorShape.CrossCursor)
            elif self.rad_toggle.isChecked():
                self.view.mouse_action = "toggle"
                self.view.setCursor(Qt.CursorShape.PointingHandCursor)

    def get_active_list(self):
        idx = self.tabs.currentIndex()
        if idx == 0:
            return self.auto_contours
        else:
            return self.edge_contours

    def clear_all_shapes(self):
        active_list = self.get_active_list()
        active_list.clear()
        self._calc_fiducials()
        self.draw_overlay_layer()

    def handle_scene_click(self, x, y):
        if self.cv_img_bgr is None: return
        active_list = self.get_active_list()

        # Vložení razítka
        if self.view.mouse_action == "stamp_circ":
            d_px = self.mm_to_px(self.dim_circle_d.value())
            new_shape = self.create_circle_contour(x, y, d_px / 2.0)
            active_list.append(new_shape)
            self._calc_fiducials()
            self.draw_overlay_layer()
            return

        if self.view.mouse_action == "stamp_sq":
            w_px = self.mm_to_px(self.dim_sq_w.value())
            h_px = self.mm_to_px(self.dim_sq_h.value())
            r_px = self.mm_to_px(self.dim_sq_r.value())
            new_shape = self.get_rounded_rect_contour(x, y, w_px, h_px, r_px)
            active_list.append(new_shape)
            self._calc_fiducials()
            self.draw_overlay_layer()
            return

        # Nástroje vyžadující kliknutí na existující tvar
        for i, cnt in enumerate(active_list):
            cnt_cv = np.round(cnt).astype(np.int32)
            if cv2.pointPolygonTest(cnt_cv, (x, y), False) >= 0:

                if self.view.mouse_action == "delete":
                    active_list.pop(i)
                    self._calc_fiducials()
                    self.draw_overlay_layer()
                    break

                elif self.view.mouse_action == "toggle":
                    bx, by, bw, bh = cv2.boundingRect(cnt_cv)
                    cx, cy = bx + bw / 2.0, by + bh / 2.0
                    is_circle = (len(cnt) == 100)

                    if is_circle:
                        w_px = self.mm_to_px(self.dim_sq_w.value())
                        h_px = self.mm_to_px(self.dim_sq_h.value())
                        r_px = self.mm_to_px(self.dim_sq_r.value())
                        new_shape = self.get_rounded_rect_contour(cx, cy, w_px, h_px, r_px)
                    else:
                        d_px = self.mm_to_px(self.dim_circle_d.value())
                        new_shape = self.create_circle_contour(cx, cy, d_px / 2.0)

                    active_list[i] = new_shape
                    self.draw_overlay_layer()
                    break

    def queue_calc(self, *args):
        if not self._ui_loaded: return
        if self.cv_img_bgr is not None:
            self.calc_timer.start(250)

    # --- NAČÍTÁNÍ SOUBORU ---
    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Vybrat soubor k tisku", "", "Podporované formáty (*.pdf *.png *.jpg *.jpeg)"
        )
        if not file_path: return

        try:
            self.setCursor(Qt.CursorShape.WaitCursor)
            if file_path.lower().endswith('.pdf'):
                doc = fitz.open(file_path)
                page = doc.load_page(0)
                mat = fitz.Matrix(self.dpi / 72.0, self.dpi / 72.0)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                if pix.n == 3:
                    self.cv_img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                else:
                    self.cv_img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            else:
                self.cv_img_bgr = cv2.imread(file_path)
                if self.cv_img_bgr is None: raise Exception("Obrázek se nepodařilo načíst.")

            self.img_height_px, self.img_width_px = self.cv_img_bgr.shape[:2]

            rgb_img = cv2.cvtColor(self.cv_img_bgr, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_img.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

            self.img_item.setPixmap(QPixmap.fromImage(qimg))
            self.btn_save.setEnabled(True)

            self.run_calculations()
            self.fit_view()
            self.update_layer_opacity()

        except Exception as e:
            QMessageBox.critical(self, "Chyba", f"Chyba při načítání:\n{str(e)}")
        finally:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    # --- GEOMETRIE A MATEMATIKA ---
    def get_rounded_rect_contour(self, cx, cy, w, h, r, pts_per_corner=15):
        r = min(r, w / 2.0, h / 2.0)
        x = cx - w / 2.0
        y = cy - h / 2.0

        if r <= 0:
            return np.array([[[x, y]], [[x + w, y]], [[x + w, y + h]], [[x, y + h]]], dtype=float)

        tl = np.column_stack((x + r + r * np.cos(np.linspace(np.pi, 1.5 * np.pi, pts_per_corner)),
                              y + r + r * np.sin(np.linspace(np.pi, 1.5 * np.pi, pts_per_corner))))
        tr = np.column_stack((x + w - r + r * np.cos(np.linspace(1.5 * np.pi, 2 * np.pi, pts_per_corner)),
                              y + r + r * np.sin(np.linspace(1.5 * np.pi, 2 * np.pi, pts_per_corner))))
        br = np.column_stack((x + w - r + r * np.cos(np.linspace(0, 0.5 * np.pi, pts_per_corner)),
                              y + h - r + r * np.sin(np.linspace(0, 0.5 * np.pi, pts_per_corner))))
        bl = np.column_stack((x + r + r * np.cos(np.linspace(0.5 * np.pi, np.pi, pts_per_corner)),
                              y + h - r + r * np.sin(np.linspace(0.5 * np.pi, np.pi, pts_per_corner))))

        poly = np.vstack((tl, tr, br, bl))
        return poly.reshape(-1, 1, 2)

    def create_circle_contour(self, cx, cy, radius):
        angles = np.linspace(0, 2 * np.pi, 100, endpoint=False)
        cnt = np.empty((100, 1, 2), dtype=float)
        cnt[:, 0, 0] = cx + radius * np.cos(angles)
        cnt[:, 0, 1] = cy + radius * np.sin(angles)
        return cnt

    def create_single_shape(self, cx, cy, shape_type, w, h, r):
        if "Kolečko" in shape_type:
            return self.create_circle_contour(cx, cy, w / 2.0)
        else:
            return self.get_rounded_rect_contour(cx, cy, w, h, r)

    # --- LOGIKA ZÁLOŽEK ---
    def run_calculations(self, *args):
        if not self._ui_loaded or self.cv_img_bgr is None: return

        if self.tabs.currentIndex() == 0:
            self._calc_auto_mode()
        else:
            self._calc_edge_mode()

        self._calc_fiducials()
        self.draw_overlay_layer()

    def _calc_auto_mode(self):
        threshold_val = self.sld_thresh.value()
        noise_val = self.sld_noise.value()
        close_val = self.sld_close.value()
        offset = self.sld_offset.value()
        min_area = self.sld_area.value()

        use_split = self.chk_split.isChecked()
        split_shape = self.cmb_split_shape.currentText()

        sq_w = self.mm_to_px(self.dim_sq_w.value())
        sq_h = self.mm_to_px(self.dim_sq_h.value())
        sq_r = self.mm_to_px(self.dim_sq_r.value())
        circ_d = self.mm_to_px(self.dim_circle_d.value())

        retrieval_mode = cv2.RETR_LIST if self.chk_inner_holes.isChecked() else cv2.RETR_EXTERNAL

        gray = cv2.cvtColor(self.cv_img_bgr, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, threshold_val, 255, cv2.THRESH_BINARY_INV)

        if noise_val > 0:
            kernel_noise = np.ones((noise_val, noise_val), np.uint8)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_noise)
        if close_val > 0:
            kernel_close = np.ones((close_val, close_val), np.uint8)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_close)

        if offset > 0:
            kernel_off = np.ones((offset, offset), np.uint8)
            thresh = cv2.erode(thresh, kernel_off, iterations=1)
        elif offset < 0:
            abs_offset = abs(offset)
            kernel_off = np.ones((abs_offset, abs_offset), np.uint8)
            thresh = cv2.dilate(thresh, kernel_off, iterations=1)

        raw_contours, _ = cv2.findContours(thresh, retrieval_mode, cv2.CHAIN_APPROX_SIMPLE)

        self.auto_contours = []
        for cnt in raw_contours:
            area = cv2.contourArea(cnt)
            if area > min_area:

                # --- MAGIE ROZKRÁJENÍ (SPLIT) VELKÝCH TVARŮ ---
                if use_split:
                    bx, by, bw, bh = cv2.boundingRect(np.round(cnt).astype(np.int32))

                    # Logika: pokud je najitý flek alespoň 1.3x širší nebo vyšší, než náš jeden tvar,
                    # je to "slepenec" a my ho rozřežeme do mřížky.
                    expected_w = circ_d if "Kolečko" in split_shape else sq_w
                    expected_h = circ_d if "Kolečko" in split_shape else sq_h

                    if bw > expected_w * 1.3 or bh > expected_h * 1.3:
                        cols = max(1, int(round(bw / expected_w)))
                        rows = max(1, int(round(bh / expected_h)))

                        step_x = bw / cols
                        step_y = bh / rows

                        for row in range(rows):
                            for col in range(cols):
                                cx = bx + col * step_x + step_x / 2.0
                                cy = by + row * step_y + step_y / 2.0

                                if "Kolečko" in split_shape:
                                    new_cnt = self.create_circle_contour(cx, cy, circ_d / 2.0)
                                else:
                                    new_cnt = self.get_rounded_rect_contour(cx, cy, sq_w, sq_h, sq_r)

                                self.auto_contours.append(new_cnt)
                        continue  # Pokud jsme to rozkrájeli, nepřidáváme původní flek

                # Běžné tvary (nebo pokud rozkrájení není aktivní)
                processed_cnt = cnt.astype(float)
                self.auto_contours.append(processed_cnt)

    def _calc_edge_mode(self):
        """Hledání jemných linek uvnitř slepených tvarů."""
        shape_type = self.cmb_edge_shape.currentText()
        if "Kolečka" in shape_type:
            target_w_px = self.mm_to_px(self.dim_circle_d.value())
            target_h_px = target_w_px
            target_r_px = 0
            insert_shape = "Kolečko"
        else:
            target_w_px = self.mm_to_px(self.dim_sq_w.value())
            target_h_px = self.mm_to_px(self.dim_sq_h.value())
            target_r_px = self.mm_to_px(self.dim_sq_r.value())
            insert_shape = "Čtverec"

        tolerance = self.sld_edge_tol.value() / 100.0

        gray = cv2.cvtColor(self.cv_img_bgr, cv2.COLOR_BGR2GRAY)
        t1 = self.sld_canny.value()
        edges = cv2.Canny(gray, t1, t1 * 3)
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        self.edge_contours = []
        found_centers = []

        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)

            if (target_w_px * (1 - tolerance) <= bw <= target_w_px * (1 + tolerance)) and \
                    (target_h_px * (1 - tolerance) <= bh <= target_h_px * (1 + tolerance)):

                cx = bx + bw / 2.0
                cy = by + bh / 2.0

                is_duplicate = False
                for fcx, fcy in found_centers:
                    if abs(cx - fcx) < 15 and abs(cy - fcy) < 15:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    found_centers.append((cx, cy))
                    new_shape = self.create_single_shape(cx, cy, insert_shape, target_w_px, target_h_px, target_r_px)
                    self.edge_contours.append(new_shape)

    def _calc_fiducials(self):
        self.fiducial_points = []
        active_list = self.get_active_list()

        if active_list:
            all_pts = np.concatenate(active_list)
            x, y, w, h = cv2.boundingRect(np.round(all_pts).astype(np.int32))
            padding = 50
            self.fiducial_points = [
                (x - padding, y - padding),
                (x + w + padding, y - padding),
                (x + w + padding, y + h + padding),
                (x - padding, y + h + padding)
            ]

    # --- KRESLENÍ A EXPORT ---
    def draw_overlay_layer(self):
        if self.cv_img_bgr is None: return
        w, h = self.img_width_px, self.img_height_px
        overlay = np.zeros((h, w, 4), dtype=np.uint8)
        line_width = max(2, int(0.3 / 25.4 * self.dpi))

        active_list = self.get_active_list()

        if active_list:
            render = [np.round(c).astype(np.int32) for c in active_list]
            cv2.drawContours(overlay, render, -1, (0, 0, 255, 255), line_width)

        if self.fiducial_points:
            display_rad_px = int(2.0 / 25.4 * self.dpi)
            for pt in self.fiducial_points:
                cv2.circle(overlay, pt, display_rad_px, (255, 255, 0, 255), -1)

        bytes_per_line = 4 * w
        qimg_overlay = QImage(overlay.data, w, h, bytes_per_line, QImage.Format.Format_ARGB32)
        self.cut_item.setPixmap(QPixmap.fromImage(qimg_overlay))

    def update_layer_opacity(self, *args):
        if not self._ui_loaded: return
        self.img_item.setOpacity(self.sld_alpha_img.value() / 100.0)
        self.cut_item.setOpacity(self.sld_alpha_cut.value() / 100.0)

    def update_layer_visibility(self, *args):
        if not self._ui_loaded: return
        self.img_item.setVisible(self.chk_show_img.isChecked())
        self.cut_item.setVisible(self.chk_show_cut.isChecked())

    def fit_view(self):
        if self.cv_img_bgr is not None:
            rect = self.scene.itemsBoundingRect()
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def save_dxf(self):
        active_list = self.get_active_list()
        if not active_list:
            QMessageBox.warning(self, "Prázdné", "Nejsou žádné křivky k uložení.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Uložit DXF", "", "DXF soubory (*.dxf)")
        if not save_path: return

        try:
            self.setCursor(Qt.CursorShape.WaitCursor)
            doc = ezdxf.new('R2010')
            h_img = self.img_height_px

            if self.chk_force_a4.isChecked():
                if self.img_width_px > self.img_height_px:
                    scale_x = 297.0 / self.img_width_px
                    scale_y = 210.0 / self.img_height_px
                else:
                    scale_x = 210.0 / self.img_width_px
                    scale_y = 297.0 / self.img_height_px
            else:
                scale_x = 25.4 / self.dpi
                scale_y = 25.4 / self.dpi

            lyr_cuts = doc.layers.new(name='CUT_STICKERS')
            lyr_cuts.color = 1
            msp = doc.modelspace()

            for cnt in active_list:
                points = [(pt[0][0] * scale_x, (h_img - pt[0][1]) * scale_y) for pt in cnt]
                msp.add_lwpolyline(points, close=True, dxfattribs={'layer': 'CUT_STICKERS'})

            if self.fiducial_points:
                lyr_fidu = doc.layers.new(name='FIDUCIALS')
                lyr_fidu.color = 4
                for pt in self.fiducial_points:
                    center_x = pt[0] * scale_x
                    center_y = (h_img - pt[1]) * scale_y
                    msp.add_circle((center_x, center_y), radius=self.fiducial_radius_mm,
                                   dxfattribs={'layer': 'FIDUCIALS'})

            doc.saveas(save_path)
            QMessageBox.information(self, "Hotovo", f"Exportováno v přesných milimetrech!\nUloženo do:\n{save_path}")

        except Exception as e:
            QMessageBox.critical(self, "Chyba", f"Nepodařilo se uložit DXF:\n{str(e)}")
        finally:
            self.setCursor(Qt.CursorShape.ArrowCursor)


if __name__ == "__main__":
    import os

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ModernLaserGUI()
    window.show()
    sys.exit(app.exec())