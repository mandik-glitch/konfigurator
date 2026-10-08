"""Kanonicky generator `kod_sestavy` - JEDINE misto, kde se sklada retezec.

Nahrazuje inline `sestav_kod()` z `2026-09-11_kod_sestavy_format.py`
(ten skript uz jednou probehl, nechavame ho jako historicky zaznam
nezmeneny) - format se od te doby dvakrat zmenil (bot9, 2026-09-13,
Robert primo v chatu, digit-po-digitu revize):

  1. Pribyl segment UMISTENI (`regal_umisteni.kod`, napr. RL/RP/RK) hned
     za karoserii, pred typologii - drive se vubec nezapisoval.
  2. Horni blok je dvojcislo (`horni_blok_varianty.kod` je dnes CHAR(2),
     "dej mu dvojcifernost, varianty pribudou"), ne jednociferny znak.
  3. Zadny segment kolizni rezervy (byval "-1030" navic na konci) -
     "10/30 budou vsechny regaly, tato informace v SKU je k nicemu".

VZOR (8 segmentu, pomlckami): K-075-RL-EB-30-C-0063-03-0
  karoserie - umisteni - typologie - profil - verze - varianta_typologie
  - horni_blok - dodatek

Pouziti (vsechny hodnoty uz VYPOCITANE/nactene ze sloupcu, tahle funkce
jen sklada retezec - "pravdou jsou pole, kod je jen zapis"):

    from _kod_sestavy import sestavit_kod_sestavy
    kod = sestavit_kod_sestavy(
        karoserie_kod="K-075", umisteni_kod="RL", typologie_kod="EB",
        profil_mm=30, verze="C", varianta_kod="0063", horni_blok_kod="03",
        dodatek=0,
    )
"""


def sestavit_kod_sestavy(*, karoserie_kod, umisteni_kod, typologie_kod, profil_mm,
                          verze, varianta_kod, horni_blok_kod, dodatek=0):
    if not karoserie_kod or not umisteni_kod or not typologie_kod or not profil_mm:
        return None
    if not verze or not varianta_kod or horni_blok_kod is None:
        return None
    horni_blok_kod = str(horni_blok_kod).zfill(2)
    return (f"{karoserie_kod}-{umisteni_kod}-{typologie_kod}-{profil_mm}-"
            f"{verze}-{varianta_kod}-{horni_blok_kod}-{dodatek}")
