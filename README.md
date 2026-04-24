# 🎲 Multitool Studio (Boardgame Maker)

Komplexní sada nástrojů (nejen) pro tvůrce deskových her. Tento projekt sdružuje několik nezávislých utilit pro generování karet, sazbu na tiskové archy, tvorbu ořezových cest pro laser, řezání sprite sheetů a generování krabiček. Vše lze spouštět samostatně, nebo pohodlně přes jedno sjednocující rozhraní.

---

## 🚀 Jak začít

1. **Instalace závislostí:**
   Aplikace využívá knihovny jako `PyQt6`, `OpenCV` (cv2), `Pillow` a `ezdxf`.
   ```bash
   pip install -r requirements.txt
   ```

2. **Spuštění hlavní aplikace:**
   ```bash
   python main.py
   ```

---

## 📦 Přehled aplikací (Modulů)

### 🖥️ `main.py` (Master GUI)
- **Účel:** Sjednocující "mateřská" aplikace.
- **Funkce:** Načítá všechny ostatní skripty (A, B, C, D, E) a zobrazuje je jako záložky (taby) v jednom moderním okně.

### 📄 1. `main_A_pyqt.py` (Card Imposer Studio)
- **Účel:** Sazba hotových obrázků karet na tiskový arch (např. A4/A3).
- **Funkce:** Načte složku obrázků nebo Excel s počty kusů. Poskládá karty úsporně na papír, přidá spadávku (bleed), vygeneruje tiskové křížky (ořezové značky) a exportuje tiskové PDF. Zároveň vytvoří výřezové DXF (vše v jedné vrstvě, se 4 zaměřovacími body pro funkci "Frame" na laseru).

### 🎯 2. `main_B_pyqt.py` (Generátor DXF pro Laser)
- **Účel:** Detekce a extrakce křivek z PDF dokumentů.
- **Funkce:** Pomocí OpenCV najde obrysy/tvary v nahraném PDF. Nabízí posuvníky pro práh kontrastu, matematické vyhlazování křivek, offset (vnitřní/vnější okraj) a zacelování děr. Výsledkem je čisté DXF s přesnými křivkami pro laserový výřez.

### 🖼️ 3. `main_C_pyqt.py` (Generátor Karet: Data ➔ Obrázky)
- **Účel:** Hromadná tvorba finálních obrázků karet na základě dat z tabulky.
- **Funkce:** Přečte datový Excel (`karty_data.xlsx` apod.). Využívá `card_renderer.py` k vykreslení PNG obrázků. Obsahuje interaktivní náhled s možností filtrování kategorií. Vytvoří nový "tiskový" Excel připravený pro sazbu v modulu A.

### 🏷️ 4. `main_D_pyqt.py` (Sticker Imposer)
- **Účel:** Speciální sazba pro žetony a samolepky (řádkové skládání).
- **Funkce:** Skládá obrázky po řádcích a inteligentně odřádkuje, pokud se změní typ žetonu (zabraňuje míchání druhů na jednom řádku). Hlídá bezpečné okraje papíru a exportuje PDF i DXF.

### ✂️ 5. `main_E_pyqt.py` (Sprite Slicer Studio)
- **Účel:** Extrakce a řezání obrázků (Tilemap extruder / Sub-Cropping).
- **Funkce:** Slouží pro automatické rozřezání naskenovaného archu nebo tilemapy. Pomocí počítačového vidění (OpenCV) detekuje objekty, umí odříznout rámečky, vytvořit "inset/halo" okraje a vyexportovat rozřezané sprity jako samostatné PNG soubory.

### 📦 6. `box_generator.py` (Box Generator) *[Zatím samostatný skript]*
- **Účel:** Generování krabiček na míru.
- **Funkce:** Vypočítá a vygeneruje 2D plány pro řez a ohyb krabiček (Tuck Box nebo Dno a Víko) na základě zadání vnitřních rozměrů. Kreslí čáry řezu i ohybu a exportuje je do DXF.

---

## 🛠 Grafické jádro

### `card_renderer.py`
- **Účel:** Čistá vykreslovací logika pro aplikaci `main_C_pyqt.py`.
- **Funkce:** Neobsahuje žádné uživatelské rozhraní (GUI). Definuje barvy, písma a funkce (`Pillow` / `ImageDraw`) pro kreslení jednotlivých typů karet.
- **Výhoda:** Grafika je plně oddělená. Lze snadno tvořit nové vizuály her prostým nahrazením tohoto souboru bez nutnosti sahat do kódu GUI.