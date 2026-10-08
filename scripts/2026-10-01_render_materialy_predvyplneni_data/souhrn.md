# Návrh renderovacích materiálů pro katalog scény (2026-10-01)

Zdroj: dotaz jako `fetch_katalog_parts` (cfg_dily + shop_products visible_in_scene=1 AND glb_file IS NOT NULL), bez karoserií. Jen čtení DB, nic nezapsáno. Detail po řádcích: `navrh.csv`.

- Řádků v návrhu: **181** (cfg 43, product 138)
- Navíc **287** neaktivních dílů SSE (`sse_part_*`) — podle Roberta nechány být, v CSV nejsou.

## Počty podle stavu

- OK: 115
- ROZHODNE ROBERT: 51
- VYNECHANO: 15

## Počty podle klíče a stavu

| klíč | OK | ROZHODNE ROBERT | VYNECHANO |
|---|---|---|---|
| (žádný) | 0 | 1 | 15 |
| alumi2 | 25 | 1 | 0 |
| bila | 1 | 1 | 0 |
| black | 35 | 17 | 0 |
| brown | 1 | 0 | 0 |
| chrome | 1 | 0 | 0 |
| cub_seda | 2 | 2 | 0 |
| grey | 48 | 29 | 0 |
| multibox | 2 | 0 | 0 |

Pozn.: aktivní (`aktivni=1`) = viditelné ve scéně / aktivní karta. Z 25× alumi2 OK u cfg je viditelných jen 10 profilů, zbytek jsou `_PENDING_` profily a výplně drážek (neviditelné, návrh pro budoucnost).

## ROZHODNE ROBERT — skupiny s návrhem

- **Plotny (kat. 153/155/163/218), 16 ks:** **grey** (podle barvy ve scéně #4d4d4d, jako ostatní zinkové spojky). Pozor: popis karet tvrdí „vysokopevnostní plast (HRP)“ (u 3357 „ocel“) – pokud jsou opravdu plastové, pak **black**. Rozhodnout podle fotky/dodavatele.
- **MDF deska Steel Grey 8 mm (3939):** **grey** (tmavě šedá #494b50); alternativa cub_seda, kdyby měla vypadat jako laminodesky.
- **Plastová deska 8 mm (3950):** **cub_seda** (plastová výplň jako CUB, světlejší než MDF). Je to placeholder se sdíleným GLB s MDF.
- **Ocelové šuplíky 2 ks (4930):** **bila** (lakovaný ocelový plech); alternativa grey. Korpus i čela jsou v jednom meshi, rozdělit nejde bez úpravy modelu.
- **LED 1,2 m (4929):** **alumi2** (hliníkové těleso); mléčný difuzor by chtěl bila, ale je ve stejném meshi.
- **Držák PET lahve (4928):** **black** (lakovaný drát); alternativa chrome.
- **Pojezdové kolo s brzdou 75 mm (4916):** **black**; vidlice by byla chrome, ale je to jeden mesh. Karta nemá kategorii.
- **SSE stůl vzor (4606):** celá sestava stolu v jednom meshi – návrh **nepřiřazovat** (rendrovat po dílech), případně alumi2.
- **Elektrožlab – výstupky (4932):** tělo **bila** (OK). Pro modré výstupky navrhuji **klt1**: výstupky jsou plastové zásuvkové moduly, klt1 je matný modrý plast z KLT boxů – odpovídá. blue_ceramic je lesklá, vypadá jako glazura/keramika, na plast nesedí. **Ale:** GLB je jeden mesh s jedním primitivem a bez materiálů – výstupky dnes nejdou obarvit zvlášť, je potřeba model rozdělit (nový FBX s oddělenými tělesy, nebo výběr ploch).
- **cfg pomocné díly:** doraz_dvirek → black (červená je jen značka dorazu); placka_slot_dira → grey; kvadr_plny → grey; kvadr_zaobleny → black; dvirka_40_20_test → cub_seda nebo vynechat. Všechny jsou neviditelné ve scéně.
- **Vícetělesové díly (23 aktivních):** celý díl dostane klíč podle barvy (níže), návrh po částech v tabulce níže.

## Vícetělesové díly (aktivní, víc meshů Solid_N)

Rozměry z GLB (mm, bbox). Návrh po částech je odhad podle velikosti/tvaru, jen jako podklad.

### 3381 Upevňovací kus patky (varianta 2.2.002.00.00) — Konektory pro patky (#4d4d4d), 2 těles
Výchozí: **grey** (deska grey)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 92.2 x 152.3 x 45.0 | grey | hlavní/ostatní |
| Solid_1 | 87.2 x 147.2 x 4.0 | black | tenká 4mm podložka - pryž |

### 3413 Upínač patky k podlaze 45x45 — Konektory pro patky (#4d4d4d), 4 těles
Výchozí: **grey** (svařenec ze 4 plechů, vše grey (de facto OK))

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 135.0 x 4.0 x 89.0 | grey | hlavní/ostatní |
| Solid_1 | 135.0 x 80.0 x 4.0 | grey | hlavní/ostatní |
| Solid_2 | 4.0 x 80.0 x 89.0 | grey | hlavní/ostatní |
| Solid_3 | 4.0 x 80.0 x 89.0 | grey | hlavní/ostatní |

### 3420 Upínač patky k podlaze 45x90 — Konektory pro patky (#4d4d4d), 4 těles
Výchozí: **grey** (svařenec ze 4 plechů, vše grey (de facto OK))

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 180.0 x 4.0 x 89.0 | grey | hlavní/ostatní |
| Solid_1 | 180.0 x 80.0 x 4.0 | grey | hlavní/ostatní |
| Solid_2 | 4.0 x 80.0 x 89.0 | grey | hlavní/ostatní |
| Solid_3 | 4.0 x 80.0 x 89.0 | grey | hlavní/ostatní |

### 3206 Rohová spojka trojcestná radius 20 x 20 — Rožky trojcestné oblé (#4d4d4d), 2 těles
Výchozí: **grey** (tělo grey)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 0.8 x 0.8 x 1.5 | grey | drobný kolík 1 mm, neviditelný |
| Solid_1 | 20.0 x 20.0 x 20.0 | grey | hlavní/ostatní |

### 3237 Rohová spojka trojcestná radius 30 x 30 — Rožky trojcestné oblé (#4d4d4d), 2 těles
Výchozí: **grey** (tělo grey)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 1.0 x 1.3 x 8.0 | grey | drobný kolík, neviditelný |
| Solid_1 | 30.1 x 30.1 x 30.1 | grey | hlavní/ostatní |

### 3165 Závěsná sada 20x25 — Závěsné karabiny (#4d4d4d), 2 těles
Výchozí: **grey** (T-kostka i hák zinek)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 35.0 x 23.5 x 10.0 | grey | hlavní/ostatní |
| Solid_1 | 5.0 x 50.0 x 25.0 | grey | hlavní/ostatní |

### 3348 Plastová kuličková pojistka 30x45 — Zámky (#242424), 2 těles
Výchozí: **black** (obě tělesa plast black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 37.0 x 23.0 x 74.0 | black | hlavní/ostatní |
| Solid_1 | 60.0 x 22.0 x 74.0 | black | hlavní/ostatní |

### 3423 Bezpečnostní zámek (malý) — Zámky (#242424), 17 těles
Výchozí: **black** (tělo, kryt, páčka a plastové díly black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 80.0 x 30.8 x 50.0 | black | hlavní/ostatní |
| Solid_1 | 82.8 x 30.9 x 56.1 | black | hlavní/ostatní |
| Solid_2 | 15.6 x 11.7 x 23.3 | black | hlavní/ostatní |
| Solid_3 | 15.6 x 11.7 x 23.3 | black | hlavní/ostatní |
| Solid_4 | 80.0 x 24.5 x 40.0 | black | hlavní/ostatní |
| Solid_5 | 11.9 x 12.9 x 22.4 | black | hlavní/ostatní |
| Solid_6 | 19.6 x 5.9 x 16.2 | black | hlavní/ostatní |
| Solid_7 | 42.7 x 10.6 x 32.3 | black | hlavní/ostatní |
| Solid_8 | 8.3 x 8.0 x 28.3 | chrome | pružina |
| Solid_9 | 8.3 x 8.0 x 28.3 | chrome | pružina |
| Solid_10 | 16.8 x 28.8 x 16.9 | black | hlavní/ostatní |
| Solid_11 | 20.2 x 13.0 x 17.6 | black | hlavní/ostatní |
| Solid_12 | 10.5 x 7.9 x 10.5 | chrome | drobný kovový díl 10 mm |
| Solid_13 | 22.0 x 5.1 x 5.1 | chrome | kolík 22x5 |
| Solid_14 | 11.9 x 12.9 x 22.4 | black | hlavní/ostatní |
| Solid_15 | 22.0 x 5.1 x 5.1 | chrome | kolík 22x5 |
| Solid_16 | 19.6 x 5.9 x 16.2 | black | hlavní/ostatní |

### 3219 Plastový pant 3030 — Panty plastové (#202224), 3 těles
Výchozí: **black** (obě křídla black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 32.5 x 15.5 x 50.0 | black | hlavní/ostatní |
| Solid_1 | 32.5 x 15.5 x 50.0 | black | hlavní/ostatní |
| Solid_2 | 6.2 x 6.2 x 47.0 | chrome | čep Ø6x47 (ocel) |

### 3395 Pohyblivý kloub (tuzemský) 30x30 — Spojovací klouby s páčkou (#4d4d4d), 6 těles
Výchozí: **grey** (dvě poloviny kloubu grey)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 30.0 x 37.8 x 30.0 | grey | hlavní/ostatní |
| Solid_1 | 30.0 x 38.7 x 30.4 | grey | hlavní/ostatní |
| Solid_2 | 4.5 x 17.5 x 17.5 | chrome | podložka Ø17 |
| Solid_3 | 5.1 x 17.5 x 17.5 | chrome | podložka Ø17 |
| Solid_4 | 10.0 x 12.0 x 12.0 | chrome | matice/šroub |
| Solid_5 | 43.5 x 34.5 x 42.0 | black | páčka |

### 3411 Kloub s aretací 40 x 40 — Spojovací klouby s páčkou (#4d4d4d), 16 těles
Výchozí: **grey** (dvě poloviny kloubu grey)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 40.0 x 49.5 x 40.0 | grey | hlavní/ostatní |
| Solid_1 | 40.0 x 50.1 x 40.4 | grey | hlavní/ostatní |
| Solid_2 | 5.6 x 23.8 x 23.8 | chrome | podložka Ø24 |
| Solid_3 | 5.4 x 23.8 x 23.8 | chrome | podložka Ø24 |
| Solid_4 | 16.0 x 16.0 x 16.0 | chrome | matice 16 mm |
| Solid_5 | 15.8 x 8.4 x 4.8 | grey | drobná T-matice 16x8x5 - zinek |
| Solid_6 | 16.2 x 7.8 x 16.2 | grey | drobná T-matice 16x8x5 - zinek |
| Solid_7 | 16.2 x 8.2 x 16.3 | grey | drobná T-matice 16x8x5 - zinek |
| Solid_8 | 4.8 x 8.4 x 15.8 | grey | drobná T-matice 16x8x5 - zinek |
| Solid_9 | 15.8 x 8.4 x 4.8 | grey | drobná T-matice 16x8x5 - zinek |
| Solid_10 | 4.8 x 8.4 x 15.8 | grey | drobná T-matice 16x8x5 - zinek |
| Solid_11 | 15.8 x 8.5 x 5.0 | grey | drobná T-matice 16x8x5 - zinek |
| Solid_12 | 4.8 x 8.7 x 15.9 | grey | drobná T-matice 16x8x5 - zinek |
| Solid_13 | 15.8 x 8.5 x 5.0 | grey | drobná T-matice 16x8x5 - zinek |
| Solid_14 | 4.8 x 8.7 x 15.9 | grey | drobná T-matice 16x8x5 - zinek |
| Solid_15 | 62.0 x 50.4 x 60.3 | black | páčka |

### 3386 Posuvné kolečko - drážka 8 — Vodící kolečka (#242424), 4 těles
Výchozí: **black** (kolečko black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 19.3 x 47.0 x 47.0 | black | hlavní/ostatní |
| Solid_1 | 5.3 x 13.0 x 13.0 | chrome | osa/šroub |
| Solid_2 | 7.0 x 22.0 x 22.0 | chrome | ložisko |
| Solid_3 | 7.0 x 22.0 x 22.0 | chrome | ložisko |

### 3404 Posuvné kolečko - drážka 10 — Vodící kolečka (#242424), 4 těles
Výchozí: **black** (kolečko black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 29.0 x 68.5 x 68.5 | black | hlavní/ostatní |
| Solid_1 | 13.0 x 16.0 x 16.0 | chrome | osa/šroub |
| Solid_2 | 8.0 x 24.0 x 24.0 | chrome | ložisko |
| Solid_3 | 8.0 x 24.0 x 24.0 | chrome | ložisko |

### 3425 Sada kluzáků do drážky - drážka 8 30x30 — Vodící kolečka (#242424), 7 těles
Výchozí: **black** (těleso + kolečko black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 30.0 x 32.5 x 32.5 | black | hlavní/ostatní |
| Solid_1 | 19.6 x 26.8 x 26.8 | black | hlavní/ostatní |
| Solid_2 | 5.0 x 13.0 x 13.0 | chrome | ložisko |
| Solid_3 | 30.0 x 12.0 x 12.0 | chrome | osa 30x12 |
| Solid_4 | 5.0 x 13.0 x 13.0 | chrome | ložisko |
| Solid_5 | 16.0 x 16.0 x 20.0 | grey | spojovací kus 16x20 - zinek |
| Solid_6 | 16.0 x 20.0 x 16.0 | grey | spojovací kus 16x20 - zinek |

### 3430 Sada kluzáků do drážky 40x40 - drážka 10 — Vodící kolečka (#242424), 5 těles
Výchozí: **black** (těleso + kolečko black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 40.0 x 40.0 x 40.0 | black | hlavní/ostatní |
| Solid_1 | 40.0 x 16.0 x 16.0 | chrome | osa 40x16 |
| Solid_2 | 27.0 x 34.0 x 34.0 | black | hlavní/ostatní |
| Solid_3 | 4.0 x 16.0 x 16.0 | chrome | ložisko |
| Solid_4 | 4.0 x 16.0 x 16.0 | chrome | ložisko |

### 3436 Sada kluzáků do drážky 45x45 — Vodící kolečka (#242424), 7 těles
Výchozí: **black** (těleso, kolečko, kostky black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 45.0 x 16.0 x 16.0 | chrome | osa 45x16 |
| Solid_1 | 20.0 x 20.0 x 25.0 | black | hlavní/ostatní |
| Solid_2 | 20.0 x 25.0 x 20.0 | black | hlavní/ostatní |
| Solid_3 | 30.0 x 42.0 x 42.0 | black | hlavní/ostatní |
| Solid_4 | 4.0 x 16.0 x 16.0 | chrome | ložisko |
| Solid_5 | 4.0 x 16.0 x 16.0 | chrome | ložisko |
| Solid_6 | 45.0 x 45.0 x 45.0 | black | hlavní/ostatní |

### 3288 Čep k drážce 8 mm — Drážkové čepy (#242424), 3 těles
Výchozí: **black** (tělo + podložka black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 15.0 x 21.5 x 15.0 | black | hlavní/ostatní |
| Solid_1 | 5.2 x 10.0 x 5.2 | chrome | šroub Ø5x10 |
| Solid_2 | 15.2 x 8.6 x 15.2 | black | hlavní/ostatní |

### 3315 Čep k drážce 10 mm — Drážkové čepy (#242424), 2 těles
Výchozí: **black** (obě tělesa plast black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 18.0 x 18.0 x 24.0 | black | hlavní/ostatní |
| Solid_1 | 18.0 x 18.0 x 11.0 | black | hlavní/ostatní |

### 3372 Plynová vzpěra (zdvih 105 mm) F150N — Plynové vzpěry (#242424), 3 těles
Výchozí: **black** (válec black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 18.0 x 210.5 x 18.1 | black | hlavní/ostatní |
| Solid_1 | 8.0 x 158.5 x 8.0 | chrome | pístnice Ø8x158 |
| Solid_2 | 12.1 x 30.9 x 15.4 | black | koncovka (kulový čep) |

### 3367 Kovová patka M6x45 — Stavitelné patky (#4d4d4d), 2 těles
Výchozí: **grey** (základna grey)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 10.4 x 53.0 x 12.0 | chrome | závitová tyč M6, 53 mm |
| Solid_1 | 40.0 x 20.0 x 40.0 | grey | hlavní/ostatní |

### 3368 Kovová patka M8x50 — Stavitelné patky (#4d4d4d), 2 těles
Výchozí: **grey** (základna grey)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 10.4 x 68.5 x 12.0 | chrome | závitová tyč M8, 68 mm |
| Solid_1 | 50.0 x 21.0 x 50.0 | grey | hlavní/ostatní |

### 3327 Sada magnetů - drážka 10 — Magnety (#242424), 6 těles
Výchozí: **black** (pouzdro black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 45.0 x 48.0 x 35.0 | black | hlavní/ostatní |
| Solid_1 | 6.3 x 2.0 x 1.5 | chrome | magnet/plíšek |
| Solid_2 | 6.3 x 2.0 x 1.5 | chrome | magnet/plíšek |
| Solid_3 | 10.3 x 2.0 x 1.5 | chrome | magnet/plíšek |
| Solid_4 | 10.3 x 2.0 x 1.5 | chrome | magnet/plíšek |
| Solid_5 | 40.0 x 20.0 x 28.4 | grey | vložka/T-kus 40x20 - zinek |

### 3116 Držák plexiskla s maticí S10 — Držáky plexiskla (#242424), 4 těles
Výchozí: **black** (tělo + pásky black)

| těleso | rozměr | návrh | proč |
|---|---|---|---|
| Solid_0 | 24.9 x 36.7 x 18.1 | black | hlavní/ostatní |
| Solid_1 | 3.0 x 22.9 x 1.5 | black | hlavní/ostatní |
| Solid_2 | 3.0 x 22.9 x 1.5 | black | hlavní/ostatní |
| Solid_3 | 5.0 x 9.5 x 9.5 | chrome | matice 5x9,5 mm |

## Vynecháno (15)

- cfg kontrolni-doblo-zjednoduseny-test Doblo FI22-B zjednodušený (test 15.9.) – kontrolni pomucka - bez materialu
- cfg deska_mdf_seda_8 MDF deska Steel Grey 8mm – duplikat - v katalogu ho zastupuje shop_products 3939 (fetch_katalog_parts ho preskoci)
- cfg kontrolni-oblozeni-bok-levy Obložení K-075 - bok levý (kontrola) – kontrolni pomucka - bez materialu
- cfg kontrolni-oblozeni-bok-pravy Obložení K-075 - bok pravý (kontrola) – kontrolni pomucka - bez materialu
- cfg kontrolni-oblozeni-podlaha-predni Obložení K-075 - podlaha přední (kontrola) – kontrolni pomucka - bez materialu
- cfg kontrolni-oblozeni-podlaha-zadni Obložení K-075 - podlaha zadní (kontrola) – kontrolni pomucka - bez materialu
- cfg deska_plast_8 Plastová deska 8mm – duplikat - v katalogu ho zastupuje shop_products 3950 (fetch_katalog_parts ho preskoci)
- cfg sipka_posuvne_celo Šipka posuvné čelo (obousměrná značka) – znacka/sipka - bez materialu
- cfg deska_lam_seda_25 Laminovaná deska šedá 25mm – duplikat - v katalogu ho zastupuje shop_products 3671 (fetch_katalog_parts ho preskoci); POZOR layer=alu u nehlinikoveho dilu
- cfg logo_logiman_cz Logo LOGIMAN.CZ – logo - bez materialu
- cfg pr10 PR10 – duplikat - v katalogu ho zastupuje shop_products 3539 (fetch_katalog_parts ho preskoci); POZOR layer=alu u nehlinikoveho dilu
- product 4899 TEST: Renault Trafic L2H1 (rekonstrukce v3, noha/komponenta vcelku) – neaktivni Vandr testovaci/exportni sestava, nese vlastni Vandr materialy (ALU, blue KLT, preklizka...) - ponechat nativni
- product 4900 TEST: VW Transporter T6 L1 (rekonstrukce v3, cista) – neaktivni Vandr testovaci/exportni sestava, nese vlastni Vandr materialy (ALU, blue KLT, preklizka...) - ponechat nativni
- product 4901 TEST: Fiat Ducato L1H1 (rekonstrukce v3, 2 chybejici FBX v katalogu) – neaktivni Vandr testovaci/exportni sestava, nese vlastni Vandr materialy (ALU, blue KLT, preklizka...) - ponechat nativni
- product 4902 EXPORT (realny FBX z appky): Renault Trafic L2H1 - leva police – neaktivni Vandr testovaci/exportni sestava, nese vlastni Vandr materialy (ALU, blue KLT, preklizka...) - ponechat nativni
