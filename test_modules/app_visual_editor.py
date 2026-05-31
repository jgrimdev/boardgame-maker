import sys
import os
import json
import csv
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QListWidget, 
                             QGroupBox, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
                             QGraphicsTextItem, QLineEdit, QFileDialog, QMessageBox, QComboBox)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QBrush, QColor, QPen, QFont, QPixmap

DPI = 300
MM_TO_PX = DPI / 25.4

class VisualEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vizuální Editor Layoutu (BETA) + CSV Data")
        self.resize(1300, 850)
        
        self.csv_data = []
        self.headers = []
        self.items_map = {} # header -> QGraphicsItem
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        
        # --- LEVÝ PANEL (Nástroje a Data) ---
        left_panel = QWidget()
        left_panel.setFixedWidth(280)
        left_layout = QVBoxLayout(left_panel)
        
        grp_canvas = QGroupBox("Nastavení plátna (mm)")
        lyt_canvas = QVBoxLayout()
        row_w = QHBoxLayout()
        row_w.addWidget(QLabel("Šířka:"))
        self.inp_w = QLineEdit("63")
        row_w.addWidget(self.inp_w)
        lyt_canvas.addLayout(row_w)
        
        row_h = QHBoxLayout()
        row_h.addWidget(QLabel("Výška:"))
        self.inp_h = QLineEdit("88")
        row_h.addWidget(self.inp_h)
        lyt_canvas.addLayout(row_h)
        
        btn_apply_canvas = QPushButton("Aplikovat rozměr")
        btn_apply_canvas.clicked.connect(self.update_canvas_size)
        lyt_canvas.addWidget(btn_apply_canvas)
        grp_canvas.setLayout(lyt_canvas)
        left_layout.addWidget(grp_canvas)
        
        grp_data = QGroupBox("Datový zdroj (CSV)")
        lyt_data = QVBoxLayout()
        self.btn_load_csv = QPushButton("📁 Načíst CSV tabulku")
        self.btn_load_csv.setStyleSheet("background-color: #b5e4ff; font-weight: bold; padding: 5px;")
        self.btn_load_csv.clicked.connect(self.load_csv)
        lyt_data.addWidget(self.btn_load_csv)
        
        lyt_data.addWidget(QLabel("Náhled řádku:"))
        self.combo_rows = QComboBox()
        self.combo_rows.currentIndexChanged.connect(self.preview_row)
        lyt_data.addWidget(self.combo_rows)
        grp_data.setLayout(lyt_data)
        left_layout.addWidget(grp_data)
        
        grp_tools = QGroupBox("Přidat prvky")
        lyt_tools = QVBoxLayout()
        self.btn_add_text = QPushButton("+ Volný Text")
        self.btn_add_img = QPushButton("+ Volný Obrázek")
        lyt_tools.addWidget(self.btn_add_text)
        lyt_tools.addWidget(self.btn_add_img)
        grp_tools.setLayout(lyt_tools)
        left_layout.addWidget(grp_tools)
        
        left_layout.addStretch()
        
        # --- STŘED (Plátno karty) ---
        self.scene = QGraphicsScene()
        
        self.bg_card = QGraphicsRectItem()
        self.bg_card.setBrush(QBrush(QColor(255, 255, 255)))
        self.bg_card.setPen(QPen(QColor(0, 0, 0)))
        self.scene.addItem(self.bg_card)
        
        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet("background-color: #2b2b2b;")
        self.view.setRenderHint(self.view.renderHints() | self.view.renderHints().Antialiasing)
        
        layout.addWidget(left_panel)
        layout.addWidget(self.view)
        
        # --- PRAVÝ PANEL (Vlastnosti) ---
        right_panel = QWidget()
        right_panel.setFixedWidth(250)
        right_layout = QVBoxLayout(right_panel)
        
        grp_props = QGroupBox("Vlastnosti vybraného prvku")
        self.lyt_props = QVBoxLayout()
        self.lbl_prop_info = QLabel("Vyberte prvek na plátně...")
        self.lyt_props.addWidget(self.lbl_prop_info)
        self.lyt_props.addStretch()
        grp_props.setLayout(self.lyt_props)
        
        right_layout.addWidget(grp_props)
        
        self.btn_save = QPushButton("💾 Uložit Layout (JSON)")
        self.btn_save.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 10px;")
        self.btn_save.clicked.connect(self.save_layout)
        right_layout.addWidget(self.btn_save)
        
        layout.addWidget(right_panel)
        
        self.scene.selectionChanged.connect(self.on_selection_changed)
        
        self.update_canvas_size()

    def update_canvas_size(self):
        try:
            w_mm = float(self.inp_w.text().replace(',', '.'))
            h_mm = float(self.inp_h.text().replace(',', '.'))
            w_px = w_mm * MM_TO_PX
            h_px = h_mm * MM_TO_PX
            
            self.scene.setSceneRect(0, 0, w_px, h_px)
            self.bg_card.setRect(0, 0, w_px, h_px)
            
            # Vycentrování pohledu
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        except:
            pass

    def load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Načíst CSV", "", "CSV soubory (*.csv)")
        if not path: return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=';') # Předpoklad středníku (Excel CZ)
                rows = list(reader)
                
            if len(rows) < 2:
                # Zkusíme čárku
                with open(path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f, delimiter=',')
                    rows = list(reader)
                    
            if not rows: return
            
            self.headers = rows[0]
            self.csv_data = [dict(zip(self.headers, row)) for row in rows[1:]]
            
            self.combo_rows.clear()
            for i, row_data in enumerate(self.csv_data):
                # Zkusíme najít název pro combo box
                name = row_data.get(self.headers[0], f"Řádek {i+1}")
                self.combo_rows.addItem(f"{i+1}: {name}", i)
                
            self.generate_items_from_headers()
            
        except Exception as e:
            QMessageBox.critical(self, "Chyba", f"Nepodařilo se načíst CSV:\n{e}")

    def generate_items_from_headers(self):
        # Smazat staré automatické prvky
        for item in self.items_map.values():
            if item in self.scene.items():
                self.scene.removeItem(item)
        self.items_map.clear()
        
        y_offset = 50
        for header in self.headers:
            txt = QGraphicsTextItem(f"[{header}]")
            txt.setFont(QFont("Arial", 40, QFont.Weight.Bold))
            txt.setPos(50, y_offset)
            txt.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable)
            txt.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)
            txt.setData(0, header) # Data role 0 = Jméno sloupce z CSV
            self.scene.addItem(txt)
            self.items_map[header] = txt
            y_offset += 100
            
        self.preview_row(0)

    def preview_row(self, index):
        if index < 0 or index >= len(self.csv_data): return
        row_data = self.csv_data[index]
        
        for header, item in self.items_map.items():
            if isinstance(item, QGraphicsTextItem):
                val = row_data.get(header, "")
                item.setPlainText(str(val))

    def on_selection_changed(self):
        selected = self.scene.selectedItems()
        if not selected:
            self.lbl_prop_info.setText("Nic není vybráno.")
            return
            
        item = selected[0]
        pos = item.pos()
        
        info = f"Typ: {type(item).__name__}\n"
        if isinstance(item, QGraphicsTextItem):
            header = item.data(0)
            if header:
                info += f"Zdroj: Sloupec '{header}'\n"
            info += f"Text: {item.toPlainText()[:15]}...\n"
            
        info += f"\nX: {pos.x():.1f} px\nY: {pos.y():.1f} px"
        self.lbl_prop_info.setText(info)

    def save_layout(self):
        layout_data = {
            "canvas_w_mm": float(self.inp_w.text().replace(',', '.')),
            "canvas_h_mm": float(self.inp_h.text().replace(',', '.')),
            "items": []
        }
        
        for item in self.scene.items():
            if item == self.bg_card: continue
            
            if isinstance(item, QGraphicsTextItem):
                data = {
                    "type": "text",
                    "x": item.pos().x(),
                    "y": item.pos().y(),
                    "csv_column": item.data(0) or ""
                }
                layout_data["items"].append(data)
                
        path, _ = QFileDialog.getSaveFileName(self, "Uložit Layout", "layout.json", "JSON (*.json)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(layout_data, f, indent=4)
                QMessageBox.information(self, "Hotovo", "Layout úspěšně uložen.")
            except Exception as e:
                QMessageBox.critical(self, "Chyba", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = VisualEditorApp()
    window.show()
    sys.exit(app.exec())
