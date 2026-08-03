"""Birikmalar bo'yicha ma'lumotnoma va zaxira nomlagich.

Jadval o'quv dasturida haqiqatan uchraydigan birikmalarni qamrab oladi.
Undan tashqaridagi hamma narsa :func:`name_from_formula` ga tushadi va
hech narsa qaytarmaslik o'rniga oddiy nomlash qoidalari qo'llaniladi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from data.elements import ELEMENTS

_METALS: Final[frozenset[str]] = frozenset(
    symbol
    for symbol, element in ELEMENTS.items()
    if element.category
    in {"ishqoriy metall", "ishqoriy-yer metall", "o'tish metali",
        "o'tishdan keyingi metall", "lantanoid", "aktinoid"}
)

#: Reaksiyada butun holda saqlanadigan, bitta birlik sifatida tenglashtiriladigan ionlar.
POLYATOMIC_IONS: Final[dict[str, tuple[str, int]]] = {
    "OH": ("gidroksid", -1), "NO3": ("nitrat", -1), "NO2": ("nitrit", -1),
    "SO4": ("sulfat", -2), "SO3": ("sulfit", -2), "CO3": ("karbonat", -2),
    "HCO3": ("gidrokarbonat", -1), "PO4": ("fosfat", -3),
    "NH4": ("ammoniy", 1), "ClO3": ("xlorat", -1), "ClO4": ("perxlorat", -1),
    "ClO": ("gipoxlorit", -1), "MnO4": ("permanganat", -1),
    "Cr2O7": ("dixromat", -2), "CrO4": ("xromat", -2), "CN": ("sianid", -1),
    "SCN": ("tiosianat", -1), "C2H3O2": ("asetat", -1), "HSO4": ("gidrosulfat", -1),
}

_ANION_STEMS: Final[dict[str, str]] = {
    "O": "oks", "S": "sulf", "N": "nitr", "P": "fosf", "C": "karb", "H": "gidr",
    "F": "ftor", "Cl": "xlor", "Br": "brom", "I": "yod", "Se": "selen",
    "Te": "tellur", "As": "arsen", "Si": "silits", "B": "bor",
}
_PREFIXES: Final[tuple[str, ...]] = (
    "", "mono", "di", "tri", "tetra", "penta", "geksa", "gepta", "okta", "nona", "deka",
)
_ROMAN: Final[dict[int, str]] = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII",
}


@dataclass(frozen=True, slots=True)
class Compound:
    """Bitta birikma haqidagi ma'lumotnoma yozuvi."""

    formula: str
    name: str
    common_name: str = ""
    state: str = ""
    density: str = ""
    melting_point: str = ""
    uses: str = ""
    hazards: str = ""


#: Tanlangan ma'lumotnoma. Zichliklar, boshqacha ko'rsatilmagan bo'lsa, xona haroratida.
COMPOUNDS: Final[dict[str, Compound]] = {
    c.formula: c
    for c in (
        Compound("H2O", "Suv", "", "suyuq", "1.00 g/sm³", "0 °C",
                 "Erituvchi, sovutgich, reaksiya muhiti.", "Oddiy sharoitda xavfsiz."),
        Compound("H2SO4", "Sulfat kislota", "kuporos moyi", "suyuq", "1.84 g/sm³", "10 °C",
                 "O'g'it, akkumulyatorlar, neftni tozalash.",
                 "Og'ir kuyish; terini kuydiradi. Doim kislotani suvga quying, aksincha emas."),
        Compound("HCl", "Vodorod xlorid", "eritmada — xlorid kislota", "gaz", "1.49 g/L", "-114 °C",
                 "Po'latni tozalash, pH nazorati, hazm qilish.",
                 "Korroziy; bug'i nafas yo'llarini kuydiradi."),
        Compound("HNO3", "Nitrat kislota", "aqua fortis", "suyuq", "1.51 g/sm³", "-42 °C",
                 "O'g'it, portlovchi moddalar, o'yish.",
                 "Kuchli oksidlovchi; teridan sariq dog' qoldiradi."),
        Compound("NaOH", "Natriy gidroksid", "kaustik soda", "qattiq", "2.13 g/sm³", "318 °C",
                 "Sovun, qog'oz, quvur tozalagich.",
                 "Og'ir kuyish; suvda eriganda issiqlik chiqaradi."),
        Compound("KOH", "Kaliy gidroksid", "kaustik potash", "qattiq", "2.04 g/sm³", "406 °C",
                 "Yumshoq sovun, batareyalar, biodizel.", "Og'ir kuyish."),
        Compound("NaCl", "Natriy xlorid", "osh tuzi", "qattiq", "2.17 g/sm³", "801 °C",
                 "Oziq-ovqat, xlor-ishqor xomashyosi, muzni eritish.", "Oddiy sharoitda xavfsiz."),
        Compound("CaCO3", "Kalsiy karbonat", "ohaktosh, bo'r", "qattiq", "2.71 g/sm³",
                 "825 °C da parchalanadi",
                 "Sement, antatsidlar, to'ldirgich.", "Changi o'pkani ta'sirlaydi."),
        Compound("CaO", "Kalsiy oksid", "so'ndirilmagan ohak", "qattiq", "3.34 g/sm³", "2613 °C",
                 "Sement, po'lat eritish, tuproqni ishlash.",
                 "Suv bilan issiqlik chiqarib reaksiyaga kirishadi."),
        Compound("Ca(OH)2", "Kalsiy gidroksid", "so'ndirilgan ohak", "qattiq", "2.21 g/sm³",
                 "580 °C da parchalanadi",
                 "Qorishma, suvni tozalash, ohakli suv sinovi.", "Teri va ko'zni ta'sirlaydi."),
        Compound("CO2", "Uglerod dioksid", "karbonat angidrid", "gaz", "1.98 g/L",
                 "-78 °C da sublimatsiyalanadi",
                 "Gazlangan ichimliklar, o't o'chirgichlar, fotosintez.",
                 "Yopiq joyda bo'g'uvchi."),
        Compound("CO", "Uglerod monoksid", "is gazi", "gaz", "1.14 g/L", "-205 °C",
                 "Metallurgiyada qaytaruvchi, sintez-gaz.",
                 "Hidsiz va o'ldiruvchi; gemoglobin bilan bog'lanadi."),
        Compound("NH3", "Ammiak", "", "gaz", "0.73 g/L", "-78 °C",
                 "O'g'it, sovutgich, tozalash vositalari.",
                 "O'tkir hidli, nafas yo'llari uchun korroziy."),
        Compound("CH4", "Metan", "tabiiy gaz", "gaz", "0.66 g/L", "-182 °C",
                 "Yoqilg'i, vodorod ishlab chiqarish.",
                 "Oson yonuvchi; kuchli issiqxona gazi."),
        Compound("C2H5OH", "Etanol", "spirt", "suyuq", "0.789 g/sm³", "-114 °C",
                 "Erituvchi, yoqilg'i, dezinfeksiya vositasi.",
                 "Oson yonuvchi; ko'p miqdorda zaharli."),
        Compound("C6H12O6", "Glyukoza", "dekstroza, uzum shakari", "qattiq", "1.54 g/sm³", "146 °C",
                 "Hujayra yoqilg'isi, achitish xomashyosi.", "Oddiy sharoitda xavfsiz."),
        Compound("H2O2", "Vodorod peroksid", "", "suyuq", "1.45 g/sm³", "-0.4 °C",
                 "Oqartirish, dezinfeksiya, raketa yoqilg'isi.",
                 "Kuchli oksidlovchi; konsentrlangan eritmasi kuydiradi."),
        Compound("O2", "Kislorod", "", "gaz", "1.43 g/L", "-219 °C",
                 "Nafas olish, po'lat eritish, payvandlash.", "Yonishni keskin kuchaytiradi."),
        Compound("H2", "Vodorod", "", "gaz", "0.09 g/L", "-259 °C",
                 "Ammiak sintezi, yoqilg'i elementlari.",
                 "Havo bilan keng oraliqda portlovchi aralashma hosil qiladi."),
        Compound("N2", "Azot", "", "gaz", "1.25 g/L", "-210 °C",
                 "Inert muhit, kriogenika.", "Yopiq joyda bo'g'uvchi."),
        Compound("Fe2O3", "Temir(III) oksid", "zang, gematit", "qattiq", "5.24 g/sm³", "1565 °C",
                 "Temir rudasi, pigment, termit.", "Changi o'pkani ta'sirlaydi."),
        Compound("FeO", "Temir(II) oksid", "vyustit", "qattiq", "5.75 g/sm³", "1377 °C",
                 "Pigment, keramika sirlari.", "Changi ta'sirlaydi."),
        Compound("Fe3O4", "Temir(II,III) oksid", "magnetit", "qattiq", "5.17 g/sm³", "1597 °C",
                 "Temir rudasi, magnit yozuv, pigment.", "Changi ta'sirlaydi."),
        Compound("CuSO4", "Mis(II) sulfat", "mis kuporosi (pentagidrat)", "qattiq",
                 "3.60 g/sm³", "650 °C da parchalanadi",
                 "Fungitsid, galvanoplastika, Feling sinovi.",
                 "Yutilsa zararli; baliqlar uchun zaharli."),
        Compound("AgNO3", "Kumush nitrat", "jahannam toshi", "qattiq", "4.35 g/sm³", "212 °C",
                 "Galogenid sinovlari, fotografiya, kuydirish.",
                 "Korroziy; teridan qora dog' qoldiradi."),
        Compound("AgCl", "Kumush xlorid", "", "qattiq", "5.56 g/sm³", "455 °C",
                 "Foto emulsiyalar, taqqoslash elektrodlari.",
                 "Yorug'likda qorayadi; kam zaharli."),
        Compound("KMnO4", "Kaliy permanganat", "marganesovka", "qattiq", "2.70 g/sm³",
                 "240 °C da parchalanadi",
                 "Titrlash, suvni tozalash, dezinfeksiya.",
                 "Kuchli oksidlovchi; hamma narsaga binafsha-jigarrang dog' qoldiradi."),
        Compound("K2Cr2O7", "Kaliy dixromat", "xrompik", "qattiq", "2.68 g/sm³", "398 °C",
                 "Oksidlovchi titrlash, teri oshlash.", "Kanserogen; ehtiyot bo'ling."),
        Compound("NaHCO3", "Natriy gidrokarbonat", "ichimlik sodasi", "qattiq", "2.20 g/sm³",
                 "50 °C da parchalanadi", "Non yopish, antatsid, yong'inni o'chirish.",
                 "Oddiy sharoitda xavfsiz."),
        Compound("Na2CO3", "Natriy karbonat", "kir sodasi, kalsinatsiyalangan soda", "qattiq",
                 "2.54 g/sm³", "851 °C", "Shisha, yuvish vositalari, suvni yumshatish.",
                 "Ko'z va terini ta'sirlaydi."),
        Compound("SO2", "Oltingugurt dioksid", "oltingugurt gazi", "gaz", "2.63 g/L", "-72 °C",
                 "Sulfat kislota xomashyosi, konservant.",
                 "Bo'g'adi; astmani qo'zg'atadi; kislotali yomg'ir hosil qiladi."),
        Compound("SO3", "Oltingugurt trioksid", "", "suyuq", "1.92 g/sm³", "17 °C",
                 "Sulfat kislota ishlab chiqarish.",
                 "Suvni shiddat bilan tortadi; og'ir kuyish."),
        Compound("NO2", "Azot dioksid", "", "gaz", "1.88 g/L", "-11 °C",
                 "Nitrat kislota oraliq mahsuloti.",
                 "Jigarrang, zaharli; o'pka to'qimasini shikastlaydi."),
        Compound("ZnCl2", "Rux xlorid", "", "qattiq", "2.91 g/sm³", "290 °C",
                 "Kavsharlash flyusi, yog'ochni himoyalash.", "Korroziy."),
        Compound("MgO", "Magniy oksid", "magneziya", "qattiq", "3.58 g/sm³", "2852 °C",
                 "O'tga chidamli g'ishtlar, antatsidlar.", "Changi ta'sirlaydi."),
        Compound("Al2O3", "Alyuminiy oksid", "alyumina, korund", "qattiq", "3.99 g/sm³", "2072 °C",
                 "Alyuminiy olish, abrazivlar, keramika.", "Changi ta'sirlaydi."),
        Compound("CH3COOH", "Etan kislota", "sirka kislota, sirka", "suyuq", "1.05 g/sm³", "17 °C",
                 "Sirka, erituvchi, plastmassa.", "Konsentrlangan holda korroziy."),
        Compound("NH4Cl", "Ammoniy xlorid", "novshadil", "qattiq", "1.53 g/sm³",
                 "338 °C da sublimatsiyalanadi", "Quruq batareyalar, flyus, o'g'it.",
                 "Ta'sirlovchi."),
        Compound("BaSO4", "Bariy sulfat", "", "qattiq", "4.49 g/sm³", "1580 °C",
                 "Rentgen kontrasti, burg'ilash eritmasi, pigment.",
                 "Erimaydi, shuning uchun zaharsiz — eruvchan bariy tuzlari esa zaharli."),
        Compound("PbI2", "Qo'rg'oshin(II) yodid", "", "qattiq", "6.16 g/sm³", "402 °C",
                 "\"Oltin yomg'ir\" tajribasi, detektorlar.",
                 "Zaharli; qo'rg'oshin organizmda to'planadi."),
    )
}


def normalise_key(formula: str) -> str:
    """Jadvaldagi kalit bilan mos kelishi uchun zaryad va gidrat belgilarini olib tashlaydi."""
    return re.sub(r"\^.*$", "", formula.strip())


def lookup(formula: str) -> Compound | None:
    """Formula jadvalda bo'lsa, u haqidagi ma'lumotni topadi."""
    return COMPOUNDS.get(normalise_key(formula))


def search(term: str) -> list[Compound]:
    """Birikmalarni formulasi, sistematik nomi yoki oddiy nomi bo'yicha qidiradi."""
    term = term.strip().lower()
    if not term:
        return sorted(COMPOUNDS.values(), key=lambda c: c.name)
    return sorted(
        (
            compound
            for compound in COMPOUNDS.values()
            if term in compound.formula.lower()
            or term in compound.name.lower()
            or term in compound.common_name.lower()
        ),
        key=lambda c: c.name,
    )


def polyatomic_ions_in(formula: str) -> list[str]:
    """Formula ichida butun holda yozilgan murakkab ionlar, eng uzunidan boshlab."""
    found: list[str] = []
    for ion in sorted(POLYATOMIC_IONS, key=len, reverse=True):
        if ion in formula and not any(ion in seen for seen in found):
            found.append(ion)
    return found


def name_from_formula(formula: str, composition: dict[str, int], charge: int = 0) -> str | None:
    """Jadvalda yo'q formulaga oddiy nomlash qoidalarini qo'llaydi.

    Ikkilamchi ionli birikmalar (metallning bir nechta oksidlanish darajasi
    bo'lsa, rim raqami bilan) va ikkilamchi kovalent birikmalar (grek
    old qo'shimchalari bilan) qo'llab-quvvatlanadi. Hech bir qoida mos
    kelmasa ``None`` qaytaradi.
    """
    known = lookup(formula)
    if known:
        return known.name
    if charge:
        ion = POLYATOMIC_IONS.get(normalise_key(formula))
        return ion[0].capitalize() if ion else None
    if len(composition) == 1:
        symbol = next(iter(composition))
        return ELEMENTS[symbol].name if symbol in ELEMENTS else None
    if len(composition) != 2:
        return _name_with_polyatomic(formula, composition)

    (first, first_count), (second, second_count) = _ordered_pair(composition)
    stem = _ANION_STEMS.get(second)
    if stem is None:
        return None
    anion = f"{stem}id"
    if first in _METALS:
        cation = ELEMENTS[first].name
        states = ELEMENTS[first].oxidation_states
        if len(states) > 1:
            anion_charge = _anion_charge(second)
            if anion_charge:
                oxidation = abs(anion_charge) * second_count / first_count
                if oxidation == int(oxidation) and int(oxidation) in _ROMAN:
                    return f"{cation}({_ROMAN[int(oxidation)]}) {anion}"
        return f"{cation} {anion}"
    first_prefix = _PREFIXES[first_count] if first_count < len(_PREFIXES) else ""
    second_prefix = _PREFIXES[second_count] if second_count < len(_PREFIXES) else ""
    if first_prefix == "mono":
        first_prefix = ""
    head = f"{first_prefix}{ELEMENTS[first].name.lower()}"
    # "mono" + "oksid" ikkita unlini yonma-yon qo'yadi; o'zbekcha shakli "monoksid".
    tail = f"{second_prefix}{anion}".replace("monooks", "monoks")
    return f"{head} {tail}".capitalize()


def _name_with_polyatomic(formula: str, composition: dict[str, int]) -> str | None:
    """Metall va tanilgan murakkab iondan tuzilgan tuzni nomlaydi."""
    match = re.match(r"^([A-Z][a-z]?)\d*", formula)
    if not match or match.group(1) not in _METALS:
        return None
    metal = match.group(1)
    remainder = formula[match.end():].strip("()")
    for ion, (ion_name, _) in POLYATOMIC_IONS.items():
        if remainder.startswith(ion) or remainder.strip("()0123456789") == ion:
            return f"{ELEMENTS[metal].name} {ion_name}"
    return None


def _ordered_pair(composition: dict[str, int]) -> list[tuple[str, int]]:
    """Kationga o'xshash element birinchi — formulalar shunday yoziladi."""
    items = list(composition.items())
    if items[0][0] in _METALS or items[1][0] not in _METALS:
        return items
    return [items[1], items[0]]


def _anion_charge(symbol: str) -> int | None:
    element = ELEMENTS.get(symbol)
    if not element:
        return None
    negatives = [state for state in element.oxidation_states if state < 0]
    return negatives[0] if negatives else None
