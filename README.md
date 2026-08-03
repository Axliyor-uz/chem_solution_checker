# Kimyo yechimlari tekshirgichi

Kimyoviy tenglamani o'quvchi qanday yozsa, shundayligicha o'qiydigan, undagi
xatoni aniq aytadigan, muvozanatlaydigan va yechim yo'lini ko'rsatadigan
Streamlit dasturi.

U hech qachon shunchaki "tenglama noto'g'ri" demaydi. Har bir xulosa elementni
nomlaydi, ikkala tomondagi sonlarni keltiradi va qaysi koeffitsiyentni
o'zgartirish kerakligini aytadi.

```
H2 + O2 -> H2O

  ✕  O muvozanatlanmagan
     O: chapda 2, o'ngda 1
     Yechim — H₂O oldidagi koeffitsiyent 2 bo'lishi kerak.
```

## Ishga tushirish

```bash
pip install -r requirements.txt
streamlit run app.py
```

Python 3.12 yoki undan yangi versiya. API kalit ham, internet ham talab
qilinmaydi; faqat ixtiyoriy sun'iy intellekt ustozi shularga muhtoj.

## Nima qila oladi

| Sahifa | Nima uchun |
| --- | --- |
| **Tenglama tekshirgich** | Tekshirish, muvozanatlash, atomlar hisobi, yechim qadamlari, reaksiya turi, eksport |
| **Stexiometriya** | Cheklovchi reagent, nazariy unum, ortiqcha modda, gaz hajmi, foizli unum |
| **Molyar massa** | Elementlar ulushi, foizli tarkib, massa↔mol o'girish |
| **Davriy jadval** | 118 ta element, bosiladigan kataklar, konfiguratsiya va oksidlanish darajalari |
| **Birikma haqida** | Xossalar, ishlatilishi va xavflari; ro'yxatda yo'q formulalar qoidalar bo'yicha nomlanadi |
| **Tarix** | Shu sessiyada tekshirilganlarning hammasi, qidiruv va eksport bilan |

### Kimyoviy klaviatura

Elementlar, raqamlar, pastki indekslar, yuqori indeksdagi zaryadlar, qavslar,
amallar, holatlar, grek harflari va katalizatorlar — har biri tenglama
maydoniga yozadi. Oddiy usulda yozish ham xuddi shunday ishlaydi: `H2O` va
`H₂O` bir xil natija beradi, ikkalasi ham `H2O` bo'lib saqlanadi.

Katalizator tugmalari tenglamaga emas, alohida sharoitlar maydoniga yozadi,
chunki katalizator strelka ustida turadi, formula ichida emas.

### Muvozanat tarozisi

Dasturning asosiy ko'rinishi. Har bir element markaziy tayanch atrofida o'zi
bilan taroziga qo'yiladi, ustunlar markazdan tashqariga qarab o'sadi — shuning
uchun muvozanatsizlik birorta raqamni o'qishdan oldin ko'zga tashlanadi. Ionlar
bo'lsa, zaryad uchun alohida qator chiqadi.

## Qanday ishlaydi

Muvozanatlash — qidiruv emas, chiziqli algebra masalasi. Har bir element bitta
saqlanish tenglamasini beradi, zaryad esa yana bittasini; reagentlarni musbat,
mahsulotlarni manfiy yozish "muvozanatlangan" shartini o'sha matritsaning "nol
fazosida yotadi" shartiga aylantiradi. SymPy uni ratsional sonlar ustida
yechadi, maxrajlar yo'qotiladi va natija eng katta umumiy bo'luvchiga bo'linadi.

Shu sababli bitta kod yo'li oddiy tenglamalarni ham, ionli va oksidlanish-
qaytarilish tenglamalarini ham qamrab oladi:

```
MnO4- + Fe2+ + H+  →  MnO4⁻ + 5Fe²⁺ + 8H⁺ → Mn²⁺ + 5Fe³⁺ + 4H₂O
```

O'sha matritsa tenglama muvaffaqiyatsiz bo'lishining to'rt xil sababini ajratadi
— bu muhim, chunki ular turli xatolar va turli maslahat talab qiladi:

| Natija | Ma'nosi |
| --- | --- |
| `balanced` | Koeffitsiyentlar topildi |
| `missing_species` | Element faqat bir tomonda — buni koeffitsiyent to'g'rilay olmaydi |
| `impossible` | Nol fazo bo'sh yoki manfiy koeffitsiyent kerak |
| `underdetermined` | Bitta qatorga yozilgan ikkita reaksiya, javob yagona emas |

## O'quvchi yozuvini o'qish

Ustki belgisiz yozilgan `n+` chinakam ikkima'noli: `Cu2+` dagi 2 — zaryad,
`NH4+` dagi 4 — pastki indeks. Parser buni quyidagi tartibdagi qoidalar bilan
hal qiladi, yon paneldagi yozuv qo'llanmasi esa o'quvchiga shuni tushuntiradi:

1. `^` zaryadni aniq belgilaydi va doim ustun turadi — `SO4^2-`
2. Avval ishora kelsa, bu doim zaryad — `Fe+3`
3. Yolg'iz element belgisidan keyingi `n+` — zaryad — `Cu2+` → Cu²⁺
4. Ikki va undan ortiq raqam bo'linadi: oxirgisi zaryad — `SO42-` → SO₄²⁻
5. Aks holda bitta raqam pastki indeks bo'lib qoladi — `NH4+` → NH₄⁺

Katta-kichik harf xatosi rad etilmaydi, tuzatiladi. `FE2o3` uchun dastur
"element belgilari katta-kichik harfda noto'g'ri yozilgan — `Fe₂O₃` ni nazarda
tutdingizmi?" deb javob beradi. Qayta o'qish ikkima'noli bo'lsa (`caco3` ni
CaCO₃ ham, CaCo₃ ham deb o'qish mumkin) yengilroq elementlardan iborat variant
tanlanadi — bu deyarli har doim to'g'ri chiqadi.

## Loyiha tuzilishi

```
chem_solution_checker/
├── app.py                      navigatsiya, mavzu, yozuv qoidalari paneli
├── pages/
│   ├── Equation_Checker.py     asosiy sahifa
│   ├── Stoichiometry.py
│   ├── Molar_Mass.py
│   ├── Periodic_Table.py
│   ├── Compound_Info.py
│   └── History.py
├── components/
│   ├── parser.py               matn → Formula / Species / Equation
│   ├── validator.py            o'quvchi amal qila oladigan xulosalar
│   ├── balancer.py             saqlanish matritsasining nol fazosi orqali yechim
│   ├── atom_counter.py         sanash, baho berishdan alohida
│   ├── reaction_classifier.py  reaksiya turkumlari va dalillari
│   ├── explanation.py          qadamlar, ustoz izohlari, bosqichli maslahatlar
│   ├── stoichiometry.py        mol, cheklovchi reagent, unum
│   ├── chemical_keyboard.py    klaviatura komponenti
│   └── ui.py                   mavzu va umumiy chizish
├── data/
│   ├── elements.py             118 ta element; o'rni va konfiguratsiyasi hisoblanadi
│   └── compounds.py            ma'lumotnoma, murakkab ionlar, nomlash qoidalari
├── utils/
│   ├── formatting.py           ASCII ↔ terilgan ko'rinish
│   ├── history.py              sessiya yozuvi
│   └── export.py               PDF, CSV, JSON, PNG
└── tests/                      137 ta test
```

Kimyo mantig'i, interfeys va biznes mantiq alohida turadi: `components/` ichida
`ui.py` va `chemical_keyboard.py` dan boshqa hech bir fayl Streamlit'ni import
qilmaydi, shuning uchun butun kimyo dvigatelini interfeyssiz sinash va qayta
ishlatish mumkin.

## Testlar

```bash
pytest
```

137 ta test: o'qish (barcha zaryad va strelka yozuvlari bilan), ma'lum javoblar
bo'yicha muvozanatlash, atomlarni sanash, tekshirish xabarlari, tasniflash,
tushuntirish, nomlash va to'rtala eksport formati.

## Ixtiyoriy sun'iy intellekt ustozi

Yechim qadamlari, maslahatlar va ustoz izohlari to'liq oflayn tayyorlanadi.
Agar `.streamlit/secrets.toml` faylida yoki muhit o'zgaruvchilarida
`ANTHROPIC_API_KEY` bo'lsa, ustiga erkin savol-javob ustozi qo'shiladi; unga
kontekst sifatida tekshirilgan tahlil beriladi, shuning uchun u ramziy natijaga
zid gapira olmaydi. Mashq rejimida esa unga javobni aytmaslik topshiriladi.

## Ma'lum cheklovlar

- **Muvozanat — hali kimyo emas.** Muvozanatlangan tenglama, albatta, amalda
  boradigan reaksiya degani emas. Tekshirgich saqlanish qonunlarini tekshiradi,
  termodinamikani emas, va buni yashirmay aytadi.
- **Tasniflash — evristik.** Reaksiya turkumlari tuzilish belgilariga qarab
  aniqlanadi; har bir yorliq o'zi asoslangan kuzatuv va ishonch darajasi bilan
  beriladi, shunda o'quvchi ko'r-ko'rona ishonmay, o'zi baho bera oladi.
- **Oksidlanish-qaytarilishni aniqlash** elementning erkin va birikkan holat
  orasida ko'chishini yoki zaryad o'zgarishini qidiradi. Kovalent birikmalar
  ichidagi oksidlanish darajalarini hisoblamaydi, shuning uchun ayrim nozik
  redoks reaksiyalari belgilanmay qolishi mumkin.
- **Ma'lumotnoma** 40 ta birikmani batafsil qamraydi; qolgan hamma narsa uchun
  molyar massa hisoblanadi va nom qoidalar asosida tuziladi.
