import sys
import cv2
import numpy as np
import fitz  # PyMuPDF
import ezdxf
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QSlider, QCheckBox,
                             QGroupBox, QFileDialog, QMessageBox, QGraphicsView,
                             QGraphicsScene, QGraphicsPixmapItem, QFrame)
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
        self.delete_mode = False

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
        if self.delete_mode and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            self.clicked_scene.emit(scene_pos.x(), scene_pos.y())
            return
        super().mousePressEvent(event)


class ModernLaserGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Generátor DXF - Rozpoznávání Tvarů & Profi Filtry")
        self.resize(1400, 950)

        self.dpi = 300
        self.fiducial_radius_mm = 0.2

        self.cv_img_bgr = None
        self.smoothed_contours = []
        self.fiducial_points = []
        self.img_height_px = 0
        self.img_width_px = 0

        self.calc_timer = QTimer()
        self.calc_timer.setSingleShot(True)
        self.calc_timer.timeout.connect(self.update_contours_and_fiducials)

        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # ==========================================
        # LEVÝ PANEL (Ovládání)
        # ==========================================
        left_panel = QWidget()
        left_panel.setFixedWidth(360)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 1. Vstupní data
        grp_load = QGroupBox("1. Vstupní data")
        lyt_load = QVBoxLayout()
        self.btn_load = QPushButton("Načíst PDF")
        self.btn_load.setFixedHeight(40)
        self.btn_load.clicked.connect(self.load_pdf)
        self.chk_force_a4 = QCheckBox("Vynutit formát A4 (210x297 mm)")
        self.chk_force_a4.setChecked(True)
        lyt_load.addWidget(self.btn_load)
        lyt_load.addWidget(self.chk_force_a4)
        grp_load.setLayout(lyt_load)
        left_layout.addWidget(grp_load)

        # 2. Nastavení křivek
        grp_calc = QGroupBox("2. Detekce a Tvar Křivek")
        lyt_calc = QVBoxLayout()

        self.lbl_thresh = QLabel("Práh kontrastu: 240")
        self.sld_thresh = self._create_slider(100, 254, 240, self.lbl_thresh, "Práh kontrastu: {}")
        lyt_calc.addWidget(self.lbl_thresh)
        lyt_calc.addWidget(self.sld_thresh)

        self.lbl_noise = QLabel("Odstranit tenké čáry a šum: 0 px")
        self.sld_noise = self._create_slider(0, 20, 0, self.lbl_noise, "Odstranit tenké čáry a šum: {} px")
        lyt_calc.addWidget(self.lbl_noise)
        lyt_calc.addWidget(self.sld_noise)

        self.lbl_close = QLabel("Zacelení děr (spojování): 5 px")
        self.sld_close = self._create_slider(0, 50, 5, self.lbl_close, "Zacelení děr (spojování): {} px")
        lyt_calc.addWidget(self.lbl_close)
        lyt_calc.addWidget(self.sld_close)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        lyt_calc.addWidget(line)

        self.lbl_offset = QLabel("Ofset (- ven, + dovnitř): 5 px")
        self.sld_offset = self._create_slider(-30, 30, 5, self.lbl_offset, "Ofset (- ven, + dovnitř): {} px")
        lyt_calc.addWidget(self.lbl_offset)
        lyt_calc.addWidget(self.sld_offset)

        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        lyt_calc.addWidget(line2)

        # --- NOVÉ: ROZPOZNÁVÁNÍ TVARŮ ---
        self.chk_geom = QCheckBox("✨ Vynutit dokonalé tvary (Kruhy, Obdélníky)")
        self.chk_geom.setChecked(False)
        self.chk_geom.setStyleSheet("font-weight: bold; color: #1976D2;")
        self.chk_geom.toggled.connect(self.queue_calc)
        lyt_calc.addWidget(self.chk_geom)

        self.chk_smooth = QCheckBox("Zapnout matematické vyhlazení křivek")
        self.chk_smooth.setChecked(False)
        self.chk_smooth.toggled.connect(self.toggle_smooth_slider)
        self.chk_smooth.toggled.connect(self.queue_calc)
        lyt_calc.addWidget(self.chk_smooth)

        self.lbl_smooth = QLabel("Intenzita vyhlazení: 3")
        self.sld_smooth = self._create_slider(1, 20, 3, self.lbl_smooth, "Intenzita vyhlazení: {}")
        self.sld_smooth.setEnabled(False)
        lyt_calc.addWidget(self.lbl_smooth)
        lyt_calc.addWidget(self.sld_smooth)

        line3 = QFrame()
        line3.setFrameShape(QFrame.Shape.HLine)
        line3.setFrameShadow(QFrame.Shadow.Sunken)
        lyt_calc.addWidget(line3)

        self.lbl_area = QLabel("Min. plocha objektu: 500 px")
        self.sld_area = self._create_slider(50, 2000, 500, self.lbl_area, "Min. plocha objektu: {} px", step=50)
        lyt_calc.addWidget(self.lbl_area)
        lyt_calc.addWidget(self.sld_area)

        grp_calc.setLayout(lyt_calc)
        left_layout.addWidget(grp_calc)

        # 3. Zobrazení a Nástroje
        grp_view = QGroupBox("3. Nástroje a Náhled")
        lyt_view = QVBoxLayout()

        self.btn_delete = QPushButton("🪄 Režim ručního mazání: VYPNUTO")
        self.btn_delete.setCheckable(True)
        self.btn_delete.setFixedHeight(35)
        self.btn_delete.setStyleSheet("background-color: #444; color: white;")
        self.btn_delete.toggled.connect(self.toggle_delete_mode)
        lyt_view.addWidget(self.btn_delete)

        self.btn_fit = QPushButton("Přizpůsobit plátno oknu")
        self.btn_fit.clicked.connect(self.fit_view)
        lyt_view.addWidget(self.btn_fit)

        self.chk_show_img = QCheckBox("Ukázat Tisk")
        self.chk_show_img.setChecked(True)
        self.chk_show_img.toggled.connect(self.update_layer_visibility)
        self.lbl_alpha_img = QLabel("Průhlednost tisku: 60%")
        self.sld_alpha_img = self._create_slider(0, 100, 60, self.lbl_alpha_img, "Průhlednost tisku: {}%")
        self.sld_alpha_img.valueChanged.connect(self.update_layer_opacity)
        lyt_view.addWidget(self.chk_show_img)
        lyt_view.addWidget(self.sld_alpha_img)

        self.chk_show_cut = QCheckBox("Ukázat Křivky a Značky")
        self.chk_show_cut.setChecked(True)
        self.chk_show_cut.toggled.connect(self.update_layer_visibility)
        self.lbl_alpha_cut = QLabel("Průhlednost křivek: 100%")
        self.sld_alpha_cut = self._create_slider(0, 100, 100, self.lbl_alpha_cut, "Průhlednost křivek: {}%")
        self.sld_alpha_cut.valueChanged.connect(self.update_layer_opacity)
        lyt_view.addWidget(self.chk_show_cut)
        lyt_view.addWidget(self.sld_alpha_cut)

        grp_view.setLayout(lyt_view)
        left_layout.addWidget(grp_view)

        left_layout.addStretch()

        # 4. Export
        grp_export = QGroupBox("4. Výstup")
        lyt_export = QVBoxLayout()
        self.btn_save = QPushButton("Uložit DXF pro Laser")
        self.btn_save.setFixedHeight(50)
        self.btn_save.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #2e7d32; color: white;")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_dxf)
        lyt_export.addWidget(self.btn_save)
        grp_export.setLayout(lyt_export)
        left_layout.addWidget(grp_export)

        main_layout.addWidget(left_panel)

        # ==========================================
        # PRAVÝ PANEL (Plátno)
        # ==========================================
        self.scene = QGraphicsScene()
        self.view = GraphicsViewZoom(self.scene)
        self.view.setStyleSheet("background-color: #1e1e1e;")

        self.view.clicked_scene.connect(self.handle_delete_click)

        main_layout.addWidget(self.view)

        self.img_item = QGraphicsPixmapItem()
        self.cut_item = QGraphicsPixmapItem()
        self.scene.addItem(self.img_item)
        self.scene.addItem(self.cut_item)

    def _create_slider(self, v_min, v_max, v_default, label_widget, text_format, step=1):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(v_min)
        slider.setMaximum(v_max)
        slider.setValue(v_default)
        slider.setSingleStep(step)

        def update_label(val):
            if "Ofset" in text_format and val > 0:
                label_widget.setText(text_format.replace("{}", "+{}").format(val))
            else:
                label_widget.setText(text_format.format(val))

        update_label(v_default)
        slider.valueChanged.connect(update_label)
        slider.valueChanged.connect(self.queue_calc)
        return slider

    def toggle_smooth_slider(self, checked):
        self.sld_smooth.setEnabled(checked)

    def toggle_delete_mode(self, checked):
        self.view.delete_mode = checked
        if checked:
            self.btn_delete.setText("🛑 Režim ručního mazání: ZAPNUTO")
            self.btn_delete.setStyleSheet("background-color: #c62828; color: white; font-weight: bold;")
            self.view.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.btn_delete.setText("🪄 Režim ručního mazání: VYPNUTO")
            self.btn_delete.setStyleSheet("background-color: #444; color: white;")
            self.view.setCursor(Qt.CursorShape.ArrowCursor)

    def handle_delete_click(self, x, y):
        for i, cnt in enumerate(self.smoothed_contours):
            cnt_cv = np.round(cnt).astype(np.int32)
            if cv2.pointPolygonTest(cnt_cv, (x, y), False) >= 0:
                self.smoothed_contours.pop(i)
                self.draw_overlay_layer()
                break

    def queue_calc(self):
        if self.cv_img_bgr is not None:
            self.calc_timer.start(250)

    def load_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Vybrat PDF k tisku", "", "PDF Files (*.pdf)")
        if not file_path: return

        try:
            self.setCursor(Qt.CursorShape.WaitCursor)

            doc = fitz.open(file_path)
            page = doc.load_page(0)

            mat = fitz.Matrix(self.dpi / 72.0, self.dpi / 72.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            if pix.n == 3:
                self.cv_img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            else:
                self.cv_img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            self.img_height_px, self.img_width_px = self.cv_img_bgr.shape[:2]

            rgb_img = cv2.cvtColor(self.cv_img_bgr, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_img.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

            self.img_item.setPixmap(QPixmap.fromImage(qimg))

            self.btn_save.setEnabled(True)
            self.update_contours_and_fiducials()
            self.fit_view()
            self.update_layer_opacity()

        except Exception as e:
            QMessageBox.critical(self, "Chyba", f"Nepodařilo se načíst PDF:\n{str(e)}")
        finally:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def smooth_contour_math(self, contour, iterations, window_size=5):
        pts = contour.reshape(-1, 2).astype(float)
        if len(pts) < window_size: return contour

        pad_size = window_size // 2
        for _ in range(iterations):
            padded = np.pad(pts, ((pad_size, pad_size), (0, 0)), mode='wrap')
            window = np.ones(window_size) / window_size
            smooth_x = np.convolve(padded[:, 0], window, mode='valid')
            smooth_y = np.convolve(padded[:, 1], window, mode='valid')
            pts = np.vstack((smooth_x, smooth_y)).T

        return pts.reshape(-1, 1, 2)

    def update_contours_and_fiducials(self):
        if self.cv_img_bgr is None: return

        threshold_val = self.sld_thresh.value()
        noise_val = self.sld_noise.value()
        close_val = self.sld_close.value()
        offset = self.sld_offset.value()
        min_area = self.sld_area.value()

        use_geom = self.chk_geom.isChecked()
        use_smooth = self.chk_smooth.isChecked()
        smooth_iterations = self.sld_smooth.value()

        gray = cv2.cvtColor(self.cv_img_bgr, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, threshold_val, 255, cv2.THRESH_BINARY_INV)

        orig_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_orig_contours = [cnt for cnt in orig_contours if cv2.contourArea(cnt) > min_area]

        self.fiducial_points = []
        if valid_orig_contours:
            all_pts = np.concatenate(valid_orig_contours)
            x, y, w, h = cv2.boundingRect(all_pts)
            self.fiducial_points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]

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

        raw_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        self.smoothed_contours = []
        for cnt in raw_contours:
            area = cv2.contourArea(cnt)
            if area > min_area:
                processed_cnt = cnt.astype(float)
                shape_found = False

                # --- MAGIE ROZPOZNÁVÁNÍ TVARŮ ---
                if use_geom:
                    # Test na Kruh
                    (cx, cy), radius = cv2.minEnclosingCircle(cnt)
                    circle_area = np.pi * (radius ** 2)
                    if circle_area > 0 and (area / circle_area) > 0.85:  # Pokud je z 85 % podobný kruhu
                        # Vygenerujeme naprosto dokonalý kruh o 100 bodech (laser pojede krásně plynule)
                        angles = np.linspace(0, 2 * np.pi, 100, endpoint=False)
                        processed_cnt = np.empty((100, 1, 2), dtype=float)
                        processed_cnt[:, 0, 0] = cx + radius * np.cos(angles)
                        processed_cnt[:, 0, 1] = cy + radius * np.sin(angles)
                        shape_found = True
                    else:
                        # Test na Obdélník/Čtverec
                        rect = cv2.minAreaRect(cnt)
                        box = cv2.boxPoints(rect)
                        box_area = rect[1][0] * rect[1][1]
                        if box_area > 0 and (area / box_area) > 0.85:  # Pokud je z 85 % podobný obdélníku
                            processed_cnt = box.reshape(4, 1, 2).astype(float)
                            shape_found = True

                # Pokud to nebyl ani kruh ani čtverec, aplikujeme standardní vyhlazení křivky
                if not shape_found and use_smooth and smooth_iterations > 0:
                    processed_cnt = self.smooth_contour_math(processed_cnt, iterations=smooth_iterations)

                self.smoothed_contours.append(processed_cnt)

        self.draw_overlay_layer()

    def draw_overlay_layer(self):
        w, h = self.img_width_px, self.img_height_px
        overlay = np.zeros((h, w, 4), dtype=np.uint8)

        line_width = max(2, int(0.3 / 25.4 * self.dpi))
        color_cut = (0, 0, 255, 255)

        render_contours = [np.round(c).astype(np.int32) for c in self.smoothed_contours]
        cv2.drawContours(overlay, render_contours, -1, color_cut, line_width)

        if self.fiducial_points:
            color_fidu = (255, 255, 0, 255)
            display_rad_px = int(2.0 / 25.4 * self.dpi)
            for pt in self.fiducial_points:
                cv2.circle(overlay, pt, display_rad_px, color_fidu, -1)

        bytes_per_line = 4 * w
        qimg_overlay = QImage(overlay.data, w, h, bytes_per_line, QImage.Format.Format_ARGB32)
        self.cut_item.setPixmap(QPixmap.fromImage(qimg_overlay))

    def update_layer_opacity(self):
        self.img_item.setOpacity(self.sld_alpha_img.value() / 100.0)
        self.cut_item.setOpacity(self.sld_alpha_cut.value() / 100.0)

    def update_layer_visibility(self):
        self.img_item.setVisible(self.chk_show_img.isChecked())
        self.cut_item.setVisible(self.chk_show_cut.isChecked())

    def fit_view(self):
        if self.cv_img_bgr is not None:
            rect = self.scene.itemsBoundingRect()
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def save_dxf(self):
        if not self.smoothed_contours:
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

            for cnt in self.smoothed_contours:
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
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ModernLaserGUI()
    window.show()
    sys.exit(app.exec())