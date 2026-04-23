# Dokumentace projektu: Multitool Studio

Tento projekt se skládá z několika nezávislých aplikací, které lze spouštět samostatně, nebo hromadně přes sjednocující rozhraní (`main.py`).

## Přehled skriptů

### `main.py` (Master GUI)
- **Účel:** Sjednocující "mateřská" aplikace.
- **Funkce:** Načítá všechny ostatní skripty (A, B, C, D) a zobrazuje je jako záložky (taby) v jednom moderním okně.

### 1. `main_A_pyqt.py` (Card Imposer Studio)
- **Účel:** Sazba již hotových obrázků karet na tiskový arch (např. A4/A3).
- **Funkce:** Načte složku obrázků nebo Excel s počty kusů. Naskládá karty úsporně na papír, přidá spadávku (bleed), vygeneruje tiskové křížky (ořezové značky) a exportuje tiskové PDF. Zároveň vytvoří výřezové DXF (vše v jedné vrstvě, se 4 zaměřovacími body pro funkci "Frame" na laseru).

### 2. `main_B_pyqt.py` (Generátor DXF pro Laser)
- **Účel:** Detekce a extrakce křivek z PDF dokumentů.
- **Funkce:** Pomocí OpenCV najde obrysy/tvary v nahraném PDF. Nabízí posuvníky pro práh kontrastu, matematické vyhlazování křivek, offset (vnitřní/vnější okraj) a zacelování děr. Výsledkem je čisté DXF s přesnými křivkami pro laser.

### 3. `main_C_pyqt.py` (Generátor Karet: Data ➔ Obrázky)
- **Účel:** Hromadná tvorba finálních obrázků karet na základě dat z tabulky.
- **Funkce:** Přečte `karty_data.xlsx` (názvy, parametry, efekty). Využívá `card_renderer.py` k vykreslení PNG obrázků. Obsahuje interaktivní náhled s možností filtrování kategorií. Nakonec vytvoří nový "tiskový" Excel připravený pro sazbu v aplikaci `main_A`.

### 4. `main_D_pyqt.py` (Sticker Imposer)
- **Účel:** Speciální sazba pro žetony a samolepky (řádkové skládání).
- **Funkce:** Na rozdíl od aplikace A, která skládá natvrdo do mřížky, aplikace D skládá obrázky po řádcích a inteligentně odřádkuje, pokud se změní typ žetonu (zabraňuje míchání druhů na jednom řádku). Hlídá si bezpečné okraje papíru a opět exportuje PDF a DXF.

---

## 🛠 Grafické jádro

### `card_renderer.py`
- **Účel:** Čistá vykreslovací logika pro aplikaci `main_C`.
- **Funkce:** Neobsahuje žádné uživatelské rozhraní (GUI). Definuje barvy, písma a funkce (`Pillow / ImageDraw`) pro kreslení jednotlivých typů karet (Zboží, Lodě, Trh atd.).
- **Výhoda:** Tím, že je grafika oddělená, lze při tvorbě nové hry tento soubor snadno nahradit novým grafickým kódem (např. vygenerovaným AI z mockupu), aniž by se muselo sahat do kódu aplikace samotné.