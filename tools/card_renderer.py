import os
import textwrap
from PIL import Image, ImageDraw, ImageFont

# Původní rozlišení, na kterém funguje tvůj design (NEMĚNIT)
BASE_W = 500
BASE_H = 700

STYLY_KARET = {
    "pozadi": (255, 255, 255),
    "zbozi": {
        "zelena": (34, 139, 34),
        "zluta": (204, 153, 0),
        "hneda": (139, 69, 19),
        "cervena": (178, 34, 34)
    },
    "lode": {
        "hlavicka_normal": (70, 130, 180),
        "hlavicka_past": (178, 34, 34),
        "text_pasazer": (50, 150, 50),
        "text_past": (200, 0, 0)
    },
    "trh": {
        "hlavicka_pasivni": (70, 130, 180),
        "hlavicka_jednoraz": (178, 34, 34),
        "hlavicka_prestiz": (218, 165, 32),
        "text_cena": (200, 100, 0),
        "text_body": (0, 150, 0)
    }
}


def get_safe_filename(prefix, name):
    safe_name = str(name).lower().replace(" ", "_").replace("'", "").replace("(", "").replace(")", "").replace("/", "_")
    safe_name = safe_name.replace("á", "a").replace("č", "c").replace("é", "e").replace("í", "i")
    safe_name = safe_name.replace("ň", "n").replace("ó", "o").replace("ř", "r").replace("š", "s")
    safe_name = safe_name.replace("ť", "t").replace("ú", "u").replace("ů", "u").replace("ý", "y").replace("ž", "z")
    return f"{prefix}_{safe_name}.png"


def zalom_text(text, sirka_znaku=25):
    if not text: return ""
    return textwrap.fill(str(text), width=sirka_znaku)


class CardRenderer:
    def __init__(self):
        try:
            self.font_big = ImageFont.truetype("arialbd.ttf", 150)
            self.font_mid = ImageFont.truetype("arialbd.ttf", 50)
            self.font_small = ImageFont.truetype("arial.ttf", 25)
            self.font_title = ImageFont.truetype("arialbd.ttf", 35)
        except IOError:
            self.font_big = self.font_mid = self.font_small = self.font_title = ImageFont.load_default()

    def nakresli_ramecek(self, draw, tloustka=3, barva=(0, 0, 0)):
        draw.rectangle([0, 0, BASE_W - 1, BASE_H - 1], outline=barva, width=tloustka)

    def vycentruj_text(self, draw, text, font, y_pos, barva=(0, 0, 0)):
        try:
            bbox = draw.textbbox((0, 0), str(text), font=font)
            sirka_textu = bbox[2] - bbox[0]
        except AttributeError:
            sirka_textu, _ = draw.textsize(str(text), font=font)
        x_pos = (BASE_W - sirka_textu) / 2
        draw.text((x_pos, y_pos), str(text), font=font, fill=barva)

    def vycentruj_text_v_boxu(self, draw, text, font, box_x1, box_x2, y_pos, barva=(0, 0, 0)):
        try:
            bbox = draw.textbbox((0, 0), str(text), font=font)
            sirka_textu = bbox[2] - bbox[0]
        except AttributeError:
            sirka_textu, _ = draw.textsize(str(text), font=font)
        stred_boxu = box_x1 + (box_x2 - box_x1) / 2
        x_pos = stred_boxu - (sirka_textu / 2)
        draw.text((x_pos, y_pos), str(text), font=font, fill=barva)

    def render(self, card_data, target_w_px, target_h_px):
        """Vykreslí kartu na 500x700 a pak ji zvětší/zmenší na požadovaný rozměr"""
        img = Image.new('RGB', (BASE_W, BASE_H), STYLY_KARET["pozadi"])
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

    def _kresli_zbozi(self, draw, c):
        cislo = c.get("cislo", 0)
        nazev = c.get("nazev", "")

        if cislo <= 15:
            barva = STYLY_KARET["zbozi"]["zelena"]
        elif cislo <= 30:
            barva = STYLY_KARET["zbozi"]["zluta"]
        elif cislo <= 45:
            barva = STYLY_KARET["zbozi"]["hneda"]
        else:
            barva = STYLY_KARET["zbozi"]["cervena"]

        self.nakresli_ramecek(draw, tloustka=5, barva=barva)
        draw.rectangle([15, 15, BASE_W - 15, BASE_H - 15], outline=barva, width=2)
        draw.text((40, 40), str(cislo), font=self.font_mid, fill=barva)
        draw.text((BASE_W - 100, BASE_H - 90), str(cislo), font=self.font_mid, fill=barva)
        self.vycentruj_text(draw, str(cislo), self.font_big, BASE_H / 2 - 90, barva=barva)
        self.vycentruj_text(draw, str(nazev).upper(), self.font_title, BASE_H - 150, barva=(0, 0, 0))
        self.vycentruj_text(draw, "ZBOŽÍ", self.font_small, BASE_H - 100, barva=(100, 100, 100))

    def _kresli_lod(self, draw, c):
        self.nakresli_ramecek(draw)
        je_past = c.get("je_past", False)
        kapacita = max(1, c.get("kapacita", 1))

        barva_hlavicky = STYLY_KARET["lode"]["hlavicka_past"] if je_past else STYLY_KARET["lode"]["hlavicka_normal"]
        
        # 1. HLAVIČKA
        draw.rectangle([10, 10, BASE_W - 10, 110], outline=barva_hlavicky, width=4)

        # Odznak VB v pravém rohu
        right_bound = BASE_W - 10
        body_val = c.get("body", None)
        if body_val is not None and str(body_val).strip() != "":
            body_int = int(body_val)
            right_bound = BASE_W - 110
            barva_vb = (200, 0, 0) if body_int < 0 else (0, 150, 0)
            draw.rectangle([BASE_W - 110, 10, BASE_W - 10, 110], outline=barva_hlavicky, width=4,
                           fill=(255, 240, 240) if body_int < 0 else (240, 255, 240))
            znaminko = "+" if body_int > 0 else ""
            self.vycentruj_text_v_boxu(draw, f"{znaminko}{body_int}", self.font_mid, BASE_W - 110, BASE_W - 10, 25,
                                       barva=barva_vb)
            self.vycentruj_text_v_boxu(draw, "VB", self.font_small, BASE_W - 110, BASE_W - 10, 75, barva=barva_vb)

        # Texty hlavičky
        self.vycentruj_text_v_boxu(draw, c.get("nazev", ""), self.font_title, 10, right_bound, 25, barva=barva_hlavicky)
        podtitul = "PAST" if je_past else "LOĎ"
        self.vycentruj_text_v_boxu(draw, f"▼ {podtitul} ▼", self.font_small, 10, right_bound, 70, barva=barva_hlavicky)

        # 2. TĚLO - Kapacita
        start_y = 150
        mezera = 65
        self.vycentruj_text(draw, f"KAPACITA: {kapacita}", self.font_small, start_y - 35)

        for i in range(kapacita):
            y = start_y + (i * mezera)
            draw.rectangle([80, y, BASE_W - 80, y + 50], outline=(0, 0, 0), width=2)
            ikona = "[ Poslední zboží ]" if i == kapacita - 1 else "[ zboží ]"
            self.vycentruj_text(draw, ikona, self.font_small, y + 10, barva=(100, 100, 100))

        # 3. ODMĚNA PRO PASAŽÉRY
        y_odmeny = start_y + (kapacita * mezera) + 30
        draw.rectangle([30, y_odmeny, BASE_W - 30, BASE_H - 30], outline=(0, 0, 0), width=3)
        self.vycentruj_text(draw, "Odměna za vložené zboží:", self.font_small, y_odmeny + 15)

        display_body = int(body_val) if body_val is not None and str(body_val).strip() != "" else 0
        txt_majitel = f"Poslední karta: {display_body} VB"

        mince_val = c.get('mince', 0)
        display_mince = int(mince_val) if mince_val is not None and str(mince_val).strip() != "" else 0
        abs_m = abs(display_mince)
        if abs_m == 1:
            txt_pasazer = f"Odměna: {display_mince} Mušle"
        elif 2 <= abs_m <= 4:
            txt_pasazer = f"Odměna: {display_mince} Mušle"
        else:
            txt_pasazer = f"Odměna: {display_mince} Mušlí"

        barva_pasazer = STYLY_KARET["lode"]["text_past"] if je_past else STYLY_KARET["lode"]["text_pasazer"]

        self.vycentruj_text(draw, txt_majitel, self.font_title, y_odmeny + 55, barva=(0, 0, 0))
        self.vycentruj_text(draw, txt_pasazer, self.font_title, y_odmeny + 95, barva=barva_pasazer)

        efekt = c.get("efekt", "")
        if efekt and str(efekt).strip() != "-":
            zalomene = zalom_text(efekt, 35)
            draw.multiline_text((50, y_odmeny + 145), zalomene, font=self.font_small, fill=(200, 0, 0), align="center", spacing=5)

    def _kresli_trh(self, draw, c):
        self.nakresli_ramecek(draw)
        podtyp = str(c.get("podtyp", "")).lower()

        if "pasiv" in podtyp:
            barva_hlavicky = STYLY_KARET["trh"]["hlavicka_pasivni"]
        elif "jednor" in podtyp or "trik" in podtyp:
            barva_hlavicky = STYLY_KARET["trh"]["hlavicka_jednoraz"]
        else:
            barva_hlavicky = STYLY_KARET["trh"]["hlavicka_prestiz"]

        # 1. HLAVIČKA - Dvojitý tenký rámeček
        draw.rectangle([10, 10, BASE_W - 10, 110], outline=barva_hlavicky, width=2)
        draw.rectangle([16, 16, BASE_W - 16, 104], outline=barva_hlavicky, width=1)

        left_bound = 10
        right_bound = BASE_W - 10

        cena_val = c.get("cena", None)
        if cena_val is not None and str(cena_val).strip() != "":
            left_bound = 110
            draw.rectangle([10, 10, 110, 110], outline=barva_hlavicky, width=4, fill=(255, 250, 200))
            self.vycentruj_text_v_boxu(draw, str(cena_val), self.font_mid, 10, 110, 25, barva=STYLY_KARET["trh"]["text_cena"])
            self.vycentruj_text_v_boxu(draw, "Mušlí", self.font_small, 10, 110, 75, barva=STYLY_KARET["trh"]["text_cena"])

        body_val = c.get("body", None)
        if body_val is not None and str(body_val).strip() != "":
            right_bound = BASE_W - 110
            draw.rectangle([BASE_W - 110, 10, BASE_W - 10, 110], outline=barva_hlavicky, width=4,
                           fill=(240, 255, 240))
            znaminko = "+" if int(body_val) > 0 else ""
            self.vycentruj_text_v_boxu(draw, f"{znaminko}{body_val}", self.font_mid, BASE_W - 110, BASE_W - 10, 25,
                                       barva=STYLY_KARET["trh"]["text_body"])
            self.vycentruj_text_v_boxu(draw, "VB", self.font_small, BASE_W - 110, BASE_W - 10, 75,
                                       barva=STYLY_KARET["trh"]["text_body"])

        # Názvy uprostřed hlavičky
        self.vycentruj_text_v_boxu(draw, c.get("nazev", ""), self.font_title, left_bound, right_bound, 25, barva=barva_hlavicky)
        self.vycentruj_text_v_boxu(draw, f"♦ {str(c.get('podtyp', '')).upper()} ♦", self.font_small, left_bound, right_bound, 70,
                                   barva=barva_hlavicky)

        # 2. TĚLO - Volný prostor pro efekty
        y_efekt = 140
        efekt = c.get("efekt", "")
        if efekt and str(efekt).strip() != "-":
            draw.rectangle([30, y_efekt, BASE_W - 30, BASE_H - 40], outline=(100, 100, 100), width=2)
            self.vycentruj_text(draw, "EFEKT KARTY:", self.font_small, y_efekt + 20)
            zalomene = zalom_text(efekt, 32)
            draw.multiline_text((50, y_efekt + 70), zalomene, font=self.font_small, fill=(0, 0, 0), align="center", spacing=10)

    def _kresli_ostatni(self, draw, c):
        self.nakresli_ramecek(draw)
        barva_hlavicky = (100, 100, 100)
        draw.rectangle([10, 10, BASE_W - 10, 110], outline=barva_hlavicky, width=4)
        self.vycentruj_text(draw, str(c.get("nazev", "")).upper(), self.font_title, 35, barva=barva_hlavicky)

        efekt = c.get("efekt", "")
        if efekt and str(efekt).strip() != "-":
            zalomene = zalom_text(efekt, 35)
            draw.multiline_text((40, 150), zalomene, font=self.font_small, fill=(0, 0, 0), align="left", spacing=8)