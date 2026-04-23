import sys
import os
import cv2
import numpy as np

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QGroupBox, QLabel, QSlider, QCheckBox,
                             QPushButton, QFileDialog, QMessageBox, QScrollArea, QSizePolicy,
                             QTabWidget, QListWidget, QListWidgetItem, QFrame)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QImage, QIcon


class SlicerStudioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sprite Slicer Studio v2.2 - Sub-Cropping & Separace")
        self.resize(1300, 880)

        self.cv_img = None
        self.valid_items = []

        self.setup_ui()

    def setup_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        # ==========================================
        # LEVÝ PANEL (Ovládání se Slidery)
        # ==========================================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)

        btn_load = QPushButton("Načíst obrázek (Tilemapu)")
        btn_load.setFixedHeight(45)
        btn_load.setStyleSheet("background-color: #b5e4ff; font-weight: bold; font-size: 14px;")
        btn_load.clicked.connect(self.load_image)
        left_layout.addWidget(btn_load)

        # --- SKUPINA: PARAMETRY DETEKCE ---
        gb_detect = QGroupBox("Nastavení detekce a ořezu")
        lyt_detect = QVBoxLayout()

        self.lbl_tol = QLabel("Tolerance bílého pozadí: 20")
        self.sld_tol = self._create_slider(0, 100, 20, self.lbl_tol, "Tolerance bílého pozadí: {}")
        lyt_detect.addWidget(self.lbl_tol)
        lyt_detect.addWidget(self.sld_tol)

        self.lbl_noise = QLabel("Odstranit nepořádek z pozadí (šum): 0 px")
        self.sld_noise = self._create_slider(0, 20, 0, self.lbl_noise, "Odstranit nepořádek z pozadí (šum): {} px")
        lyt_detect.addWidget(self.lbl_noise)
        lyt_detect.addWidget(self.sld_noise)

        self.lbl_min = QLabel("Min. rozměr objektu: 50 px")
        self.sld_min = self._create_slider(10, 1000, 50, self.lbl_min, "Min. rozměr objektu: {} px", step=10)
        lyt_detect.addWidget(self.lbl_min)
        lyt_detect.addWidget(self.sld_min)

        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        lyt_detect.addWidget(line1)

        # Logika rámečků
        self.chk_frames = QCheckBox("Automaticky extrahovat postavy z rámečků")
        self.chk_frames.setChecked(True)
        self.chk_frames.setStyleSheet("color: #1976D2; font-weight: bold;")
        self.chk_frames.stateChanged.connect(self.toggle_frame_slider)
        lyt_detect.addWidget(self.chk_frames)

        self.lbl_frame_cut = QLabel("Tloušťka rámečku k odříznutí (řez skrz): 5 px")
        self.sld_frame_cut = self._create_slider(1, 30, 5, self.lbl_frame_cut,
                                                 "Tloušťka rámečku k odříznutí (řez skrz): {} px")
        self.sld_frame_cut.setStyleSheet("QSlider::handle:horizontal { background: #1976D2; }")
        lyt_detect.addWidget(self.lbl_frame_cut)
        lyt_detect.addWidget(self.sld_frame_cut)

        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        lyt_detect.addWidget(line2)

        # --- SKUPINA: ÚPRAVA VÝSLEDNÝCH OKRAJŮ ---
        lyt_detect.addWidget(QLabel("<b>Úprava výsledných okrajů postavy:</b>"))

        self.lbl_inset = QLabel("Oříznout hrany Bounding Boxu (Inset): 0 px")
        self.sld_inset = self._create_slider(0, 50, 0, self.lbl_inset, "Oříznout hrany Bounding Boxu (Inset): {} px")
        lyt_detect.addWidget(self.lbl_inset)
        lyt_detect.addWidget(self.sld_inset)

        self.lbl_halo = QLabel("Sežrat bílý obrys postavy (Eroze masky): 1 px")
        self.sld_halo = self._create_slider(0, 10, 1, self.lbl_halo, "Sežrat bílý obrys postavy (Eroze masky): {} px")
        lyt_detect.addWidget(self.lbl_halo)
        lyt_detect.addWidget(self.sld_halo)

        gb_detect.setLayout(lyt_detect)
        left_layout.addWidget(gb_detect)

        # Tlačítko uložení
        left_layout.addStretch()
        self.btn_save = QPushButton("Uložit vyříznuté objekty (PNG)")
        self.btn_save.setFixedHeight(50)
        self.btn_save.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; font-size: 14px;")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_images)
        left_layout.addWidget(self.btn_save)

        splitter.addWidget(left_panel)

        # ==========================================
        # PRAVÝ PANEL (Záložky s náhledy)
        # ==========================================
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { padding: 10px; font-weight: bold; }")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.preview_label = QLabel(
            "Nahrajte obrázek pro zobrazení náhledu.\n\nZelená = Nalezena postava\nModrá = Ignorovaný rámeček")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #2b2b2b; color: #888;")
        scroll_area.setWidget(self.preview_label)
        self.tabs.addTab(scroll_area, "Celkový náhled na arch")

        self.list_results = QListWidget()
        self.list_results.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_results.setIconSize(QSize(150, 150))
        self.list_results.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_results.setSpacing(10)
        self.list_results.setStyleSheet("background-color: #3c3f41; padding: 10px;")
        self.tabs.addTab(self.list_results, "Náhled vyříznutých obrázků")

        splitter.addWidget(self.tabs)
        splitter.setSizes([450, 850])

    def _create_slider(self, v_min, v_max, v_default, label_widget, text_format, step=1):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(v_min)
        slider.setMaximum(v_max)
        slider.setValue(v_default)
        slider.setSingleStep(step)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)

        def update_label(val):
            label_widget.setText(text_format.format(val))

        update_label(v_default)
        slider.valueChanged.connect(update_label)
        slider.valueChanged.connect(self.process_image)
        return slider

    def toggle_frame_slider(self):
        is_checked = self.chk_frames.isChecked()
        self.lbl_frame_cut.setEnabled(is_checked)
        self.sld_frame_cut.setEnabled(is_checked)
        self.process_image()

    def load_image(self):
        f, _ = QFileDialog.getOpenFileName(self, "Vyberte obrázek", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if not f: return

        stream = open(f, "rb")
        bytes_arr = bytearray(stream.read())
        numpyarray = np.asarray(bytes_arr, dtype=np.uint8)
        self.cv_img = cv2.imdecode(numpyarray, cv2.IMREAD_COLOR)

        if self.cv_img is None:
            QMessageBox.critical(self, "Chyba", "Obrázek se nepodařilo načíst.")
            return

        self.btn_save.setEnabled(True)
        self.process_image()

    def process_image(self):
        if self.cv_img is None: return

        tol = self.sld_tol.value()
        noise_val = self.sld_noise.value()
        min_size = self.sld_min.value()
        ignore_frames = self.chk_frames.isChecked()
        frame_cut = self.sld_frame_cut.value()
        inset = self.sld_inset.value()
        halo_px = self.sld_halo.value()

        # 1. Maska pozadí
        lower_white = np.array([255 - tol, 255 - tol, 255 - tol])
        upper_white = np.array([255, 255, 255])
        white_mask = cv2.inRange(self.cv_img, lower_white, upper_white)
        inv_mask = cv2.bitwise_not(white_mask)

        if noise_val > 0:
            kernel_noise = np.ones((noise_val, noise_val), np.uint8)
            inv_mask = cv2.morphologyEx(inv_mask, cv2.MORPH_OPEN, kernel_noise)

        # 2. Hledáme POUZE vnější tvary (díky RETR_EXTERNAL ignorujeme díry a bordel uvnitř)
        contours, _ = cv2.findContours(inv_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        self.valid_items = []
        preview_img = self.cv_img.copy()

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)

            if w < min_size or h < min_size:
                continue

            area = cv2.contourArea(cnt)
            bbox_area = w * h
            extent = area / float(bbox_area) if bbox_area > 0 else 0

            # 3. JE TO RÁMEČEK? (Tvar vyplňuje většinu svého obdélníku - např. přes 75 %)
            if ignore_frames and extent > 0.75:
                # Zmenšíme oblast detekce, čímž tvrdě odřízneme plameny přilepené k rámečku!
                roi_x = x + frame_cut
                roi_y = y + frame_cut
                roi_w = w - (2 * frame_cut)
                roi_h = h - (2 * frame_cut)

                if roi_w > min_size and roi_h > min_size:
                    cv2.rectangle(preview_img, (x, y), (x + w, y + h), (255, 0, 0), 2)  # Modrá = detekován rámeček

                    # Vezmeme masku jen z vnitřku tohoto zmenšeného rámečku
                    roi_mask = inv_mask[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]

                    # Najdeme tvary UVNITŘ (tentokrát to najde čistou postavu, protože dotek je pryč)
                    inner_contours, _ = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                    for inner_cnt in inner_contours:
                        ix, iy, iw, ih = cv2.boundingRect(inner_cnt)
                        if iw < min_size or ih < min_size:
                            continue

                        # Posuneme lokální souřadnice z vnitřku rámečku zpět do globálních souřadnic obrázku
                        inner_cnt_shifted = inner_cnt + np.array([roi_x, roi_y])

                        final_x = roi_x + ix + inset
                        final_y = roi_y + iy + inset
                        final_w = iw - (2 * inset)
                        final_h = ih - (2 * inset)

                        if final_w > 0 and final_h > 0:
                            self.valid_items.append((final_x, final_y, final_w, final_h, inner_cnt_shifted))
                            cv2.rectangle(preview_img, (final_x, final_y), (final_x + final_w, final_y + final_h),
                                          (0, 255, 0), 3)

            else:
                # NENÍ TO RÁMEČEK (např. červ, který leží volně na papíře)
                final_x = x + inset
                final_y = y + inset
                final_w = w - (2 * inset)
                final_h = h - (2 * inset)

                if final_w > 0 and final_h > 0:
                    self.valid_items.append((final_x, final_y, final_w, final_h, cnt))
                    cv2.rectangle(preview_img, (final_x, final_y), (final_x + final_w, final_y + final_h), (0, 255, 0),
                                  3)

        # --- AKTUALIZACE ZÁLOŽKY 1: Celkový náhled ---
        rgb_img = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)
        h_img, w_img, ch_img = rgb_img.shape
        q_img = QImage(rgb_img.data, w_img, h_img, ch_img * w_img, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)

        scaled_pixmap = pixmap.scaled(self.preview_label.width() - 20,
                                      self.preview_label.height() - 20,
                                      Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
        self.preview_label.setPixmap(scaled_pixmap)

        # --- AKTUALIZACE ZÁLOŽKY 2: Jednotlivé výsledky ---
        self.list_results.clear()
        img_bgra = cv2.cvtColor(self.cv_img, cv2.COLOR_BGR2BGRA)

        for idx, (x, y, w, h, cnt) in enumerate(self.valid_items):
            cropped_img = img_bgra[y:y + h, x:x + w].copy()

            mask_full = np.zeros(self.cv_img.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask_full, [cnt], -1, 255, thickness=cv2.FILLED)
            cropped_mask = mask_full[y:y + h, x:x + w]

            if halo_px > 0:
                kernel = np.ones((3, 3), np.uint8)
                cropped_mask = cv2.erode(cropped_mask, kernel, iterations=halo_px)

            cropped_img[cropped_mask == 0, 3] = 0

            rgba_img = cv2.cvtColor(cropped_img, cv2.COLOR_BGRA2RGBA)
            q_res_img = QImage(rgba_img.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
            icon = QIcon(QPixmap.fromImage(q_res_img))

            item = QListWidgetItem(icon, f"Obrázek {idx + 1}\n({w}x{h} px)")
            self.list_results.addItem(item)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.process_image()

    def save_images(self):
        if not self.valid_items:
            QMessageBox.warning(self, "Chyba", "Nebyly detekovány žádné objekty k uložení.")
            return

        out_dir = QFileDialog.getExistingDirectory(self, "Vyberte složku pro uložení výsledků")
        if not out_dir: return

        img_bgra = cv2.cvtColor(self.cv_img, cv2.COLOR_BGR2BGRA)
        halo_px = self.sld_halo.value()
        saved_count = 0

        for x, y, w, h, cnt in self.valid_items:
            cropped_img = img_bgra[y:y + h, x:x + w].copy()

            mask_full = np.zeros(self.cv_img.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask_full, [cnt], -1, 255, thickness=cv2.FILLED)
            cropped_mask = mask_full[y:y + h, x:x + w]

            if halo_px > 0:
                kernel = np.ones((3, 3), np.uint8)
                cropped_mask = cv2.erode(cropped_mask, kernel, iterations=halo_px)

            cropped_img[cropped_mask == 0, 3] = 0

            out_path = os.path.join(out_dir, f"sprite_{saved_count + 1}.png")
            is_success, im_buf_arr = cv2.imencode(".png", cropped_img)
            if is_success:
                im_buf_arr.tofile(out_path)
                saved_count += 1

        QMessageBox.information(self, "Hotovo", f"Úspěšně uloženo {saved_count} obrázků do vybrané složky.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = SlicerStudioApp()
    window.show()
    sys.exit(app.exec())