import re

with open("data/compounds.py", "r") as f:
    content = f.read()

translations = {
    "water": "suv",
    "Essential to life. Universal solvent.": "Hayot uchun muhim. Universal erituvchi.",
    "carbon dioxide": "karbonat angidrid",
    "Product of respiration and combustion. Greenhouse gas.": "Nafas olish va yonish mahsuloti. Issiqxona gazi.",
    "ammonia": "ammiak",
    "Pungent gas used in fertilizer production.": "O'g'it ishlab chiqarishda ishlatiladigan o'tkir hidli gaz.",
    "Corrosive, toxic": "Korroziy, zaharli",
    "methane": "metan",
    "Primary component of natural gas.": "Tabiiy gazning asosiy tarkibiy qismi.",
    "Highly flammable": "Oson yonuvchi",
    "sulfuric acid": "sulfat kislota",
    "Industrial acid used in car batteries and fertilizer.": "Avtomobil akkumulyatorlari va o'g'itlarda ishlatiladigan sanoat kislotasi.",
    "Corrosive, reactive": "Korroziy, reaktiv",
    "hydrochloric acid": "xlorid kislota",
    "Strong acid found in the stomach.": "Oshqozonda uchraydigan kuchli kislota.",
    "sodium chloride": "natriy xlorid",
    "table salt": "osh tuzi",
    "Essential dietary mineral and food preservative.": "Muhim ozuqa minerali va oziq-ovqat konservanti.",
    "sodium hydroxide": "natriy gidroksid",
    "lye": "ishqor",
    "Strong base used in drain cleaners and soap making.": "Quvurlarni tozalash va sovun ishlab chiqarishda ishlatiladigan kuchli asos.",
    "Corrosive": "Korroziy",
    "calcium carbonate": "kalsiy karbonat",
    "limestone": "ohaktosh",
    "Major component of shells and limestone.": "Chig'anoqlar va ohaktoshning asosiy tarkibiy qismi.",
    "acetic acid": "sirka kislota",
    "Main component of vinegar.": "Sirkaning asosiy tarkibiy qismi.",
    "ethanol": "etanol",
    "drinking alcohol": "ichimlik spirti",
    "Intoxicating ingredient in alcoholic beverages.": "Alkogolli ichimliklar tarkibidagi mast qiluvchi modda.",
    "glucose": "glyukoza",
    "blood sugar": "qon shaqari",
    "Primary energy source for cells.": "Hujayralar uchun asosiy energiya manbai.",
    "sucrose": "saxaroza",
    "table sugar": "shakar",
    "Common dietary sugar extracted from cane or beet.": "Qamish yoki lavlagidan olinadigan oddiy shakar.",
    "hydrogen peroxide": "vodorod peroksid",
    "Bleaching agent and mild antiseptic.": "Oqartiruvchi vosita va yengil antiseptik.",
    "Oxidizer": "Oksidlovchi",
    "sodium bicarbonate": "natriy bikarbonat",
    "baking soda": "osh sodasi",
    "Leavening agent in baking.": "Pishiriqlarda ko'pertiruvchi modda.",
    "nitric acid": "nitrat kislota",
    "Used in the production of fertilizers and explosives.": "O'g'itlar va portlovchi moddalar ishlab chiqarishda ishlatiladi.",
    "Corrosive, strong oxidizer": "Korroziy, kuchli oksidlovchi",
    "phosphoric acid": "fosfat kislota",
    "Used in fertilizers, detergents, and food flavoring.": "O'g'itlar, yuvish vositalari va oziq-ovqat xushbo'ylashtirgichlarida ishlatiladi.",
    "Corrosive": "Korroziy"
}

for eng, uzb in translations.items():
    content = content.replace(f'"{eng}"', f'"{uzb}"')

with open("data/compounds.py", "w") as f:
    f.write(content)

