import math
import textwrap
from PIL import Image, ImageDraw, ImageFont

# Původní rozlišení, na kterém funguje tvůj design (NEMĚNIT)
BASE_W = 500
BASE_H = 700

BARVY = {
    "pozadi": (255, 255, 255),
    "ram_karty": (35, 35, 35),
    "text_tmavy": (25, 25, 25),
    "text_sedy": (115, 115, 115),
    "linka_jemna": (215, 215, 215),

    "zbozi": {
        "zelena": (34, 139, 34),
        "zluta": (204, 140, 0),
        "hneda": (139, 69, 19),
        "cervena": (185, 35, 35)
    },
    "lode": {
        "normal": (35, 100, 160),      # Námořnická modrá
        "past": (180, 35, 35),         # Rudá pro pasti
        "slot_ram": (135, 155, 175),
        "slot_posledni": (204, 135, 0) # Zlatavá pro poslední slot
    },
    "trh": {
        "pasivni": (40, 115, 165),     # Modrá
        "jednoraz": (175, 50, 45),     # Červená
        "prestiz": (190, 135, 20),     # Zlatá
        "ram_vnitrni": (155, 140, 120)
    },
    "odznaky": {
        "musle": (195, 115, 10),
        "vb_plus": (35, 135, 50),
        "vb_minus": (185, 35, 35),
        "vb_nula": (120, 120, 120)
    }
}


def get_safe_filename(prefix, name):
    safe_name = str(name).lower().replace(" ", "_").replace("'", "").replace("(", "").replace(")", "").replace("/", "_")
    safe_name = safe_name.replace("á", "a").replace("č", "c").replace("é", "e").replace("í", "i")
    safe_name = safe_name.replace("ň", "n").replace("ó", "o").replace("ř", "r").replace("š", "s")
    safe_name = safe_name.replace("ť", "t").replace("ú", "u").replace("ů", "u").replace("ý", "y").replace("ž", "z")
    return f"{prefix}_{safe_name}.png"


def zalom_text(text, sirka_znaku=28):
    if not text:
        return ""
    return textwrap.fill(str(text), width=sirka_znaku)


def sklonuj_musle(pocet):
    abs_m = abs(int(pocet))
    if 1 <= abs_m <= 4:
        return "Mušle"
    return "Mušlí"


class CardRenderer:
    def __init__(self):
        self.font_big = self._load_font(["arialbd.ttf", "DejaVuSans-Bold.ttf", "segoeuib.ttf"], 145)
        self.font_badge_num = self._load_font(["arialbd.ttf", "DejaVuSans-Bold.ttf", "segoeuib.ttf"], 42)
        self.font_title = self._load_font(["arialbd.ttf", "DejaVuSans-Bold.ttf", "segoeuib.ttf"], 29)
        self.font_subtitle = self._load_font(["arialbd.ttf", "DejaVuSans-Bold.ttf", "segoeuib.ttf"], 21)
        self.font_body_bold = self._load_font(["arialbd.ttf", "DejaVuSans-Bold.ttf", "segoeuib.ttf"], 24)
        self.font_small = self._load_font(["arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"], 21)
        self.font_tiny = self._load_font(["arialbd.ttf", "DejaVuSans-Bold.ttf", "segoeuib.ttf"], 15)

    def _load_font(self, font_names, size):
        for name in font_names:
            try:
                return ImageFont.truetype(name, size)
            except IOError:
                continue
        return ImageFont.load_default()

    # ==========================================
    # 🛠️ POMOCNÉ FUNKCE PRO TEXT A TVARY
    # ==========================================
    def _get_text_size(self, draw, text, font):
        try:
            bbox = draw.textbbox((0, 0), str(text), font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            return draw.textsize(str(text), font=font)

    def vycentruj_text(self, draw, text, font, y_pos, barva=(0, 0, 0)):
        w, _ = self._get_text_size(draw, text, font)
        x_pos = (BASE_W - w) / 2
        draw.text((x_pos, y_pos), str(text), font=font, fill=barva)

    def vycentruj_text_v_boxu(self, draw, text, font, box_x1, box_x2, y_pos, barva=(0, 0, 0)):
        w, _ = self._get_text_size(draw, text, font)
        stred_boxu = box_x1 + (box_x2 - box_x1) / 2
        x_pos = stred_boxu - (w / 2)
        draw.text((x_pos, y_pos), str(text), font=font, fill=barva)

    def vycentruj_multiline(self, draw, text, font, y_pos, barva=(0, 0, 0), sirka_znaku=28, spacing=8):
        zalomene = zalom_text(text, sirka_znaku)
        try:
            bbox = draw.multiline_textbbox((0, 0), zalomene, font=font, align="center", spacing=spacing)
            w = bbox[2] - bbox[0]
        except AttributeError:
            w, _ = self._get_text_size(draw, zalomene.split('\n')[0], font)
        x_pos = (BASE_W - w) / 2
        draw.multiline_text((x_pos, y_pos), zalomene, font=font, fill=barva, align="center", spacing=spacing)

    def kresli_hvezdu(self, draw, cx, cy, r_outer, barva):
        r_inner = r_outer * 0.42
        body = []
        for i in range(10):
            angle = math.radians(i * 36 - 90)
            r = r_outer if i % 2 == 0 else r_inner
            body.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(body, fill=barva)

    def kresli_lodku(self, draw, cx, cy, barva):
        draw.polygon([(cx - 14, cy + 2), (cx + 14, cy + 2), (cx + 9, cy + 9), (cx - 9, cy + 9)], fill=barva)
        draw.polygon([(cx - 2, cy - 10), (cx - 2, cy - 1), (cx + 10, cy - 1)], fill=barva)
        draw.line([(cx - 2, cy - 10), (cx - 2, cy + 2)], fill=barva, width=2)

    def kresli_varovani(self, draw, cx, cy, barva):
        draw.polygon([(cx, cy - 10), (cx - 11, cy + 9), (cx + 11, cy + 9)], outline=barva, width=2)
        draw.line([(cx, cy - 3), (cx, cy + 3)], fill=barva, width=2)
        draw.ellipse([cx - 1, cy + 5, cx + 1, cy + 7], fill=barva)

    def kresli_velky_odznak_musle(self, draw, x1, y1, x2, y2, mince_int, dolni_text):
        """Velký geometrický osmiúhelník (drahokam) s místem na přepsání čísla propiskou."""
        barva = BARVY["odznaky"]["vb_minus"] if mince_int < 0 else BARVY["odznaky"]["musle"]
        c = 16  # Zkosení rohů
        tvar = [
            (x1 + c, y1), (x2 - c, y1),
            (x2, y1 + c), (x2, y2 - c),
            (x2 - c, y2), (x1 + c, y2),
            (x1, y2 - c), (x1, y1 + c)
        ]
        draw.polygon(tvar, fill=(255, 255, 255), outline=barva, width=3)

        # Číslo bez znaménka plus (záporné číslo si mínus nese v sobě)
        self.vycentruj_text_v_boxu(draw, str(mince_int), self.font_badge_num, x1, x2, y1 + 14, barva=barva)
        self.vycentruj_text_v_boxu(draw, dolni_text, self.font_tiny, x1, x2, y2 - 24, barva=barva)

    def kresli_velky_odznak_vb(self, draw, x1, y1, x2, y2, body_int):
        """Velký erb/štít pro VB s místem na přepsání čísla propiskou."""
        if body_int > 0:
            barva = BARVY["odznaky"]["vb_plus"]
        elif body_int < 0:
            barva = BARVY["odznaky"]["vb_minus"]
        else:
            barva = BARVY["odznaky"]["vb_nula"]

        cx = (x1 + x2) // 2
        stit = [
            (x1, y1),
            (x2, y1),
            (x2, y2 - 24),
            (cx, y2),
            (x1, y2 - 24)
        ]
        draw.polygon(stit, fill=(255, 255, 255), outline=barva, width=3)

        # Číslo bez znaménka plus (záporné číslo si mínus nese v sobě)
        self.vycentruj_text_v_boxu(draw, str(body_int), self.font_badge_num, x1, x2, y1 + 14, barva=barva)
        self.vycentruj_text_v_boxu(draw, "VB", self.font_tiny, x1, x2, y2 - 28, barva=barva)

    def render(self, card_data, target_w_px, target_h_px):
        img = Image.new('RGB', (BASE_W, BASE_H), BARVY["pozadi"])
        draw = ImageDraw.Draw(img)

        kat = card_data.get("kategorie", "")

        if kat in ["ZBOŽÍ", "ZBOZI"]:
            self._kresli_zbozi(draw, card_data)
        elif kat in ["LOĎ", "LOD"]:
            self._kresli_lod(draw, card_data)
        elif kat == "TRH":
            self._kresli_trh(draw, card_data)
        else:
            self._kresli_ostatni(draw, card_data)

        if target_w_px != BASE_W or target_h_px != BASE_H:
            img = img.resize((int(target_w_px), int(target_h_px)), Image.Resampling.LANCZOS)

        return img

    # ==========================================
    # 📦 1. KARTY ZBOŽÍ
    # ==========================================
    def _kresli_zbozi(self, draw, c):
        cislo = c.get("cislo", 0)
        nazev = c.get("nazev", "")

        if cislo <= 15:
            barva = BARVY["zbozi"]["zelena"]
        elif cislo <= 30:
            barva = BARVY["zbozi"]["zluta"]
        elif cislo <= 45:
            barva = BARVY["zbozi"]["hneda"]
        else:
            barva = BARVY["zbozi"]["cervena"]

        draw.rectangle([0, 0, BASE_W - 1, BASE_H - 1], outline=BARVY["ram_karty"], width=3)
        draw.rounded_rectangle([18, 18, BASE_W - 18, BASE_H - 18], radius=16, outline=barva, width=4)

        draw.text((40, 35), str(cislo), font=self.font_badge_num, fill=barva)
        w_num, _ = self._get_text_size(draw, str(cislo), self.font_badge_num)
        draw.text((BASE_W - 40 - w_num, BASE_H - 85), str(cislo), font=self.font_badge_num, fill=barva)

        self.vycentruj_text(draw, str(cislo), self.font_big, 220, barva=barva)

        draw.line([100, BASE_H - 170, BASE_W - 100, BASE_H - 170], fill=barva, width=2)
        self.vycentruj_text(draw, str(nazev).upper(), self.font_title, BASE_H - 150, barva=BARVY["text_tmavy"])
        self.vycentruj_text(draw, "ZBOŽÍ", self.font_tiny, BASE_H - 105, barva=BARVY["text_sedy"])

    # ==========================================
    # ⛵ 2. KARTY LODÍ
    # ==========================================
    def _kresli_lod(self, draw, c):
        je_past = c.get("je_past", False)
        kapacita = max(1, int(c.get("kapacita", 1)))
        barva_hlavni = BARVY["lode"]["past"] if je_past else BARVY["lode"]["normal"]

        # Horní barevný proužek + vnější rám
        draw.rectangle([0, 0, BASE_W, 12], fill=barva_hlavni)
        draw.rectangle([0, 0, BASE_W - 1, BASE_H - 1], outline=BARVY["ram_karty"], width=3)

        mince_val = c.get("mince", 0)
        mince_int = int(mince_val) if mince_val is not None and str(mince_val).strip() != "" else 0

        body_val = c.get("body", 0)
        body_int = int(body_val) if body_val is not None and str(body_val).strip() != "" else 0

        # 1. HLAVIČKA: Jediné místo, kde jsou čísla Mušlí a VB (snadná úprava propiskou)
        self.kresli_velky_odznak_musle(
            draw, x1=16, y1=22, x2=116, y2=127,
            mince_int=mince_int,
            dolni_text=sklonuj_musle(mince_int).upper()
        )
        self.kresli_velky_odznak_vb(
            draw, x1=BASE_W - 116, y1=22, x2=BASE_W - 16, y2=127,
            body_int=body_int
        )

        # Název lodi uprostřed
        nazev = str(c.get("nazev", ""))
        if len(nazev) > 14:
            self.vycentruj_multiline(draw, nazev, self.font_body_bold, 28, barva=BARVY["text_tmavy"], sirka_znaku=14, spacing=2)
        else:
            self.vycentruj_text_v_boxu(draw, nazev, self.font_title, 122, BASE_W - 122, 36, barva=BARVY["text_tmavy"])

        podtitul = f"PAST • KAPACITA {kapacita}" if je_past else f"LOĎ • KAPACITA {kapacita}"
        self.vycentruj_text_v_boxu(draw, podtitul, self.font_tiny, 122, BASE_W - 122, 92, barva=barva_hlavni)
        if je_past:
            self.kresli_varovani(draw, BASE_W // 2, 118, barva_hlavni)
        else:
            self.kresli_lodku(draw, BASE_W // 2, 118, barva_hlavni)

        draw.line([25, 142, BASE_W - 25, 142], fill=barva_hlavni, width=2)

        # 2. STŘED KARTY: Vizuální nákladní sloty (bez duplicitních čísel)
        slot_area_top = 162
        slot_area_bottom = 525
        available_h = slot_area_bottom - slot_area_top

        slot_h = min(64, int((available_h - (kapacita - 1) * 20) / max(1, kapacita)))
        gap = min(26, int((available_h - kapacita * slot_h) / max(1, kapacita)))
        total_slots_h = kapacita * slot_h + (kapacita - 1) * gap
        start_y = slot_area_top + (available_h - total_slots_h) // 2

        for i in range(kapacita):
            y = start_y + i * (slot_h + gap)
            je_posledni = (i == kapacita - 1)

            if i > 0:
                mid_x = BASE_W // 2
                y_arrow_top = y - gap + 4
                y_arrow_bot = y - 4
                draw.line([(mid_x, y_arrow_top), (mid_x, y_arrow_bot)], fill=BARVY["lode"]["slot_ram"], width=2)
                draw.polygon([(mid_x - 5, y_arrow_bot - 5), (mid_x + 5, y_arrow_bot - 5), (mid_x, y_arrow_bot)],
                             fill=BARVY["lode"]["slot_ram"])

            if je_posledni:
                barva_slotu = BARVY["lode"]["past"] if body_int < 0 else BARVY["lode"]["slot_posledni"]
                tloustka = 3
            else:
                barva_slotu = BARVY["lode"]["slot_ram"]
                tloustka = 2

            draw.rounded_rectangle([55, y, BASE_W - 55, y + slot_h], radius=10, fill=(255, 255, 255), outline=barva_slotu, width=tloustka)

            cy_slot = y + slot_h // 2
            r_num = min(18, slot_h // 2 - 6)
            cx_num = 85
            if je_posledni:
                draw.ellipse([cx_num - r_num, cy_slot - r_num, cx_num + r_num, cy_slot + r_num], fill=barva_slotu)
                self.vycentruj_text_v_boxu(draw, str(i + 1), self.font_subtitle, cx_num - r_num, cx_num + r_num, cy_slot - 12, barva=(255, 255, 255))
            else:
                draw.ellipse([cx_num - r_num, cy_slot - r_num, cx_num + r_num, cy_slot + r_num], outline=barva_slotu, width=2)
                self.vycentruj_text_v_boxu(draw, str(i + 1), self.font_subtitle, cx_num - r_num, cx_num + r_num, cy_slot - 12, barva=BARVY["text_sedy"])

            # Čistý popis slotu bez číselných hodnot
            if je_posledni:
                self.vycentruj_text_v_boxu(draw, "Poslední zboží", self.font_subtitle, 115, BASE_W - 85, cy_slot - 12, barva=barva_slotu)
                self.kresli_hvezdu(draw, BASE_W - 78, cy_slot, 9, barva_slotu)
            else:
                self.vycentruj_text_v_boxu(draw, "Zboží", self.font_small, 115, BASE_W - 100, cy_slot - 12, barva=BARVY["text_sedy"])

        # 3. SPODNÍ ČÁST: Prostor pro speciální efekt nebo ruční poznámky
        draw.line([40, 545, BASE_W - 40, 545], fill=BARVY["linka_jemna"], width=2)

        efekt = c.get("efekt", "")
        if efekt and str(efekt).strip() not in ["", "-", "None"]:
            self.vycentruj_multiline(draw, efekt, self.font_body_bold, 560, barva=BARVY["lode"]["past"], sirka_znaku=32, spacing=4)

        self.vycentruj_text(draw, "LOĎ", self.font_tiny, 655, barva=BARVY["text_sedy"])

    # ==========================================
    # ⚖️ 3. KARTY TRHU
    # ==========================================
    def _kresli_trh(self, draw, c):
        podtyp = str(c.get("podtyp", "")).lower()

        if "pasiv" in podtyp:
            barva_kat = BARVY["trh"]["pasivni"]
        elif "jednor" in podtyp or "trik" in podtyp:
            barva_kat = BARVY["trh"]["jednoraz"]
        else:
            barva_kat = BARVY["trh"]["prestiz"]

        draw.rectangle([0, 0, BASE_W - 1, BASE_H - 1], outline=BARVY["ram_karty"], width=3)

        # Vnitřní rám se zkosenými rohy
        m = 10
        zkos = 20
        body_ramu = [
            (m + zkos, m), (BASE_W - m - zkos, m),
            (BASE_W - m, m + zkos), (BASE_W - m, BASE_H - m - zkos),
            (BASE_W - m - zkos, BASE_H - m), (m + zkos, BASE_H - m),
            (m, BASE_H - m - zkos), (m, m + zkos)
        ]
        draw.polygon(body_ramu, outline=BARVY["trh"]["ram_vnitrni"], width=2)

        # 1. HLAVIČKA: Velký šestiúhelník vlevo (Mušle), Velký štít vpravo (VB)
        cena_val = c.get("cena", 0)
        cena_int = int(cena_val) if cena_val is not None and str(cena_val).strip() != "" else 0

        body_val = c.get("body", 0)
        body_int = int(body_val) if body_val is not None and str(body_val).strip() != "" else 0

        self.kresli_velky_odznak_musle(
            draw, x1=20, y1=22, x2=120, y2=127,
            mince_int=cena_int,
            dolni_text=sklonuj_musle(cena_int).upper()
        )
        self.kresli_velky_odznak_vb(
            draw, x1=BASE_W - 120, y1=22, x2=BASE_W - 20, y2=127,
            body_int=body_int
        )

        # Název karty uprostřed
        nazev = str(c.get("nazev", ""))
        if len(nazev) > 14:
            self.vycentruj_multiline(draw, nazev, self.font_body_bold, 28, barva=BARVY["text_tmavy"], sirka_znaku=14, spacing=2)
        else:
            self.vycentruj_text_v_boxu(draw, nazev, self.font_title, 124, BASE_W - 124, 36, barva=BARVY["text_tmavy"])

        # Štítek podtypu
        draw.rounded_rectangle([145, 92, BASE_W - 145, 122], radius=8, fill=(255, 255, 255), outline=barva_kat, width=2)
        podtyp_txt = str(c.get("podtyp", "TRH")).upper()
        self.vycentruj_text_v_boxu(draw, podtyp_txt, self.font_tiny, 145, BASE_W - 145, 98, barva=barva_kat)

        # Oddělovací linka s kosočtvercem hned pod hlavičkou
        y_orn_top = 152
        cx = BASE_W // 2
        draw.line([40, y_orn_top, cx - 16, y_orn_top], fill=barva_kat, width=2)
        draw.line([cx + 16, y_orn_top, BASE_W - 40, y_orn_top], fill=barva_kat, width=2)
        draw.polygon([(cx, y_orn_top - 6), (cx + 6, y_orn_top), (cx, y_orn_top + 6), (cx - 6, y_orn_top)], fill=barva_kat)

        # 2. TEXT EFEKTU NAHOŘE (začíná hned na Y=180, pod ním zůstává volný prostor)
        efekt = c.get("efekt", "")
        if efekt and str(efekt).strip() not in ["", "-", "None"]:
            self.vycentruj_multiline(draw, efekt, self.font_body_bold, 180, barva=BARVY["text_tmavy"], sirka_znaku=28, spacing=8)

        # Jemná uzavírací linka dole a patička
        draw.line([140, BASE_H - 65, BASE_W - 140, BASE_H - 65], fill=BARVY["linka_jemna"], width=1)
        self.vycentruj_text(draw, "TRH", self.font_tiny, BASE_H - 48, barva=BARVY["text_sedy"])

    # ==========================================
    # 📄 4. OSTATNÍ KARTY
    # ==========================================
    def _kresli_ostatni(self, draw, c):
        draw.rectangle([0, 0, BASE_W - 1, BASE_H - 1], outline=BARVY["ram_karty"], width=3)
        self.vycentruj_text(draw, str(c.get("nazev", "")).upper(), self.font_title, 45, barva=BARVY["text_tmavy"])
        draw.line([40, 105, BASE_W - 40, 105], fill=BARVY["text_sedy"], width=2)

        efekt = c.get("efekt", "")
        if efekt and str(efekt).strip() != "-":
            self.vycentruj_multiline(draw, efekt, self.font_small, 140, barva=BARVY["text_tmavy"], sirka_znaku=32, spacing=8)