# 🎲 Multitool Studio

Komplexní sada nástrojů (nejen) pro tvůrce deskových her. Projekt sdružuje několik nezávislých utilit pro generování karet, sazbu na tiskové archy, tvorbu ořezových cest pro laser, řezání sprite sheetů, generování krabiček a sazbu hexagonálních žetonů. Každý modul lze spouštět **samostatně**, nebo pohodlně přes jedno sjednocující rozhraní (`main.py`).

---

## 🚀 Jak začít

### 1. Instalace závislostí

```bash
pip install -r requirements.txt
```

Projekt využívá: `PyQt6`, `Pillow`, `ezdxf`, `opencv-python`, `openpyxl`

### 2. Spuštění hlavní aplikace

```bash
python main.py
```

### 3. Spuštění libovolného modulu samostatně

```bash
python tools/app_hex_imposer.py
python tools/app_box_generator.py
# ... atd.
```

---

## ⚙️ Hlavní okno (`main.py`)

Sjednocující „mateřská" aplikace s **lazy loadingem** – moduly se inicializují až po prvním kliknutí na záložku, takže start aplikace je okamžitý.

### Klíčové vlastnosti
- **Záložkové rozhraní** – všechny nástroje na jednom místě
- **Správa modulů** – přes menu `Zobrazení → ⚙️ Nastavení zobrazených modulů` lze libovolné záložky skrýt. Nastavení se ukládá do `config.json`.
- **Lazy loading** – při startu se načítá pouze samotné okno, moduly se importují až na vyžádání
- **Windows taskbar** – aplikace se zobrazí s vlastní ikonou v liště (`iconA.ico`)

---

## 📦 Přehled modulů

### 📄 A: Sazba Karet a DXF (`app_card_imposer.py`)
Sazba hotových obrázků karet na tiskový arch.

- Načte složku obrázků nebo tabulku s počty kusů
- Poskládá karty úsporně na papír (A3/A4/A5) se zadanou spadávkou
- Přidá tiskové křížky / ořezové značky
- Export tiskového **PDF** a výřezového **DXF** (vrstvy `REZANI`, `OREZY`)

---

### 🎯 B: Laser – Detekce Křivek (`app_laser_dxf.py`)
Extrakce řezacích křivek z naskenovaných podkladů nebo PDF.

- Detekce obrysů pomocí OpenCV (nastavitelný práh, Canny)
- Matematické vyhlazování křivek, offset (inset/outset), zacelování děr
- Export čistého **DXF** pro laserový výřez

---

### 🖼️ C: Generátor Karet z Dat (`app_card_generator.py`)
Hromadná tvorba finálních obrázků karet z datové tabulky.

- Načte Excel (`karty_data.xlsx`) s parametry jednotlivých karet
- Využívá `card_renderer.py` pro vykreslování přes Pillow
- Interaktivní náhled s filtrováním kategorií
- Vytvoří tiskový Excel připravený pro sazbu v modulu A

> **Pozn.:** Tento modul závisí na `tools/card_renderer.py`, kde jsou definovány grafické styly karet. Vlastní vizuál lze snadno vytvořit nahrazením tohoto souboru.

---

### 🏷️ D: Sazba Žetonů / Samolepek (`app_sticker_imposer.py`)
Specializovaná sazba pro žetony, samolepky a menší formáty.

- Skládá obrázky po řádcích, inteligentně odřádkuje při změně druhu žetonu
- Nastavení: spadávka, mezera, poloměr rohů, bezpečný okraj
- Tabulka se spinboxy pro počet kusů, přidání testovacích (dummy) dat, **mazání řádků** (❌)
- Zachování poměru stran při ruční editaci rozměrů
- Export **PDF** + **DXF** s ořezovými křivkami (zaoblené rohy ve vrstvě `REZANI`)

---

### ✂️ E: Sprite Slicer Studio (`app_sprite_slicer.py`)
Rozřezání naskenovaných archů nebo tilemaps na jednotlivé sprity.

- Automatická detekce objektů pomocí OpenCV
- Nastavení inset/halo okraje, ořez rámečků
- Hromadný export rozřezaných PNG souborů

---

### 📦 F: Generátor Krabiček (`app_box_generator.py`)
Tvorba papírových i dřevěných (laserových) krabiček na míru.

#### Papírové typy:
| Typ | Popis |
|-----|-------|
| Tuck Box | Klasická krabička na karty z jednoho kusu |
| Dno a Víko | Dvoudílná krabička (2 kusy papíru) |

#### Dřevěné typy (Laser / Finger Joints):
| Typ | Popis |
|-----|-------|
| Otevřený Box / Šuplík | 5 desek bez víka, zuby na všech hranách |
| Dno a Víko | 10 desek – dno se nasune do víka (+tolerance) |
| Zasouvací víko | 5 desek + 1 plochá deska (víko se zasune shora) |

- Nastavení tloušťky dřeva a velikosti zubu
- Matematicky přesné **Finger Joints** – uzavřené polygony bez přetažení v rozích
- Export **DXF** s vrstvami `REZANI` a `RÝHOVÁNÍ`

---

### ⬡ G: Sazba Hexagonů (`app_hex_imposer.py`)
Speciální sazba pro hexagonální žetony v „plástvovém" (honeycomb) rozložení.

- Automatický výpočet honeycomb layoutu (každý sudý řádek je horizontálně posunutý)
- Nastavení: šířka hexagonu, mezera, spadávka (default 0), bezpečný okraj
- Tlačítka pro přidání 1× testovacího hexagonu nebo **vyplnění celé stránky** (automatický výpočet počtu)
- Tabulka s počtem kusů od každého hexagonu + **mazání řádků** (❌)
- Ořezové značky v rozích Bounding Boxu (L-křížky v každém rohu)
- Export **PDF** + **DXF** (vrstvy `REZANI` a `ZNACKY`)

---

### 🖌️ H: Vizuální Editor (BETA) (`app_visual_editor.py`)
Experimentální drag & drop editor layoutu karet s propojením na CSV data.

- Nastavení rozměrů plátna (šířka × výška v mm)
- Import CSV tabulky – automatické vytvoření textových polí pro každý sloupec
- Přepínání řádků CSV s live náhledem hodnot na plátně
- Uložení layoutu do **JSON** pro pozdější použití při generování karet

---

## 🛠 Grafické jádro

### `tools/card_renderer.py`
Čistá vykreslovací logika pro modul C (Generátor Karet).

- **Žádné GUI** – pouze funkce pro kreslení karet přes `Pillow / ImageDraw`
- Definuje barvy, písma a strukturu karet pro konkrétní hru
- Plně oddělená od GUI – vlastní vizuál = nový soubor bez zásahu do GUI kódu

---

## 📁 Struktura projektu

```
nandeck_alternative/
├── main.py                    # Master GUI (lazy loading, správa modulů)
├── config.json                # Nastavení viditelnosti modulů (auto-generované)
├── iconA.ico                  # Ikona aplikace
├── requirements.txt
├── README.md
└── tools/
    ├── app_card_imposer.py    # A: Sazba karet
    ├── app_laser_dxf.py       # B: Detekce DXF křivek
    ├── app_card_generator.py  # C: Generátor karet z dat
    ├── app_sticker_imposer.py # D: Sazba žetonů
    ├── app_sprite_slicer.py   # E: Sprite Slicer
    ├── app_box_generator.py   # F: Generátor krabiček
    ├── app_hex_imposer.py     # G: Sazba hexagonů
    ├── app_visual_editor.py   # H: Vizuální editor (BETA)
    └── card_renderer.py       # Grafické jádro pro modul C
```

---

## 🔧 Závislosti

| Balíček | Použití |
|---------|---------|
| `PyQt6` | GUI framework pro všechny moduly |
| `Pillow` | Renderování, skládání a export obrázků (PDF) |
| `ezdxf` | Tvorba DXF souborů pro laser/plotter |
| `opencv-python` | Detekce křivek v modulech B a E |
| `openpyxl` | Čtení a zápis Excel souborů v modulu C |

```bash
pip install PyQt6 Pillow ezdxf opencv-python openpyxl
```