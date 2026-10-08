# Kontrola mini-shopu

Datum: 3. 10. 2026. Autor: openai1. Podkladem jsou aktuální pravidla v `AGENTS.md`, nikoli starší rozhodnutí popsaná v komentářích kódu.

Prošel jsem osm souborů `api/miniweb*.py`, stránky, JavaScript, nastavení a související překlady v `webapp/miniweb/`. Pro ověření návazností jsem četl konkrétní části `api/orders.py`, `api/car_storefronts.py` a `api/app.py`. Zdrojový kód jsem neměnil. Aplikaci, databázi, objednávky, odesílání zpráv ani cizí služby jsem nespouštěl.

Níže je 16 nálezů, od nejzávažnějších. „Vidím v kódu“ znamená doloženou implementaci; dopady závislé na datech a provozu uvádím podmíněně. Bez databáze neověřuji, které domény jsou živé, jaká mají nastavení ani jaké produkty skutečně obsahují.

## 1. Vysoká — Jiná objednávka se stejnou cenou je zaměněna za opakování

- **Soubor a řádky:** `api/miniweb_objednavky.py:389–395`.
- **Vidím v kódu:** hledání opakované objednávky porovnává obchod, e-mail, IČO, částku a časové okno. Neporovnává položky, konfigurace, adresy ani způsob dopravy. Odpověď kombinuje číslo původní objednávky s právě vypočtenými údaji nového požadavku.
- **Proč je to špatně:** dvě rozdílné objednávky se stejnou částkou během pěti minut mohou skončit jako jedna; zákazník dostane potvrzení druhé, která nebyla uložena. Souběžné stejné požadavky navíc nemají v této větvi společný zámek ani jedinečný identifikátor.
- **Návrh opravy:** použít jedinečný identifikátor požadavku vázaný na obchod a otisk celého normalizovaného obsahu. Při opakování vracet uloženou původní odpověď. Jedinečnost zajistit i při souběhu.

## 2. Vysoká — Objednávka z aliasu domény ztratí přiřazení k obchodu

- **Soubor a řádky:** `api/miniweb_objednavky.py:386–408`, `435–437`; návaznost `api/orders.py:1450–1451`, `1465–1472`, `api/car_storefronts.py:139–158`. Rozpoznání aliasů mini-shopem: `api/miniweb.py:138–144`.
- **Vidím v kódu:** mini-shop přijímá hlavní doménu i aliasy. Jádro ukládající objednávku hledá pouze hlavní doménu; mini-shop následně nedoplní `storefront_id` podle vlastního již ověřeného kontextu.
- **Proč je to špatně:** na aliasu odlišném od hlavní domény může být objednávka uložena bez obchodu. Přehledy, hledání opakování a denní omezení používají `storefront_id`, takže takovou objednávku neuvidí. Pouhé `www.` tento problém nevyvolá, protože ho společná funkce odstraňuje.
- **Návrh opravy:** předat ověřené ID obchodu do ukládání objednávky nebo ho doplnit ve stejné transakci. Sjednotit rozpoznávání hlavních domén a aliasů.

## 3. Vysoká — Kód nadále umožňuje skrývat ceny

- **Soubor a řádky:** `api/miniweb_shops_admin.py:21`, `89–96`; `api/miniweb.py:317–329`; `api/miniweb_cena.py:57–72`; `webapp/miniweb/miniweb-pages.js:22–25`, `179–187`, `257–284`. Ukázkové nastavení: `webapp/miniweb/config.sk.json:17`, `config.cs.json:5`.
- **Vidím v kódu:** nastavení dovoluje skryté ceny a jiné měny než EUR. Katalog nevydá cenu při jiném režimu než `shown`, u produktu bez konfigurátoru nebo při chybě marže, kurzu či výpočtu. Stránky tyto stavy nahrazují textem bez ceny; poptávkový košík nezobrazuje ceny položek. Ukázkové slovenské nastavení má skryté ceny, české používá CZK.
- **Proč je to špatně:** přímý rozpor s pravidlem „EUR bez DPH, ceny se nikdy neskrývají“. Neověřil jsem nastavení živých obchodů.
- **Návrh opravy:** pro mini-shopy vynutit EUR a zobrazené ceny. Zajistit ověřený zdroj cen i pro produkty bez konfigurátoru a poptávkový košík. Při chybě ceny ukázat jasnou chybu dostupnosti, nevymýšlet částku ani tiše přejít na skryté ceny. Stejná pravidla použít v náhledu.

## 4. Vysoká — Údaje prodejce nemají požadovaný jediný zdroj a filtr má výjimku pro značku

- **Soubor a řádky:** `api/miniweb.py:228–236`, `383–410`, `524–526`; zobrazení `webapp/miniweb/miniweb-pages.js:34–37`, `405–409`, `439–441`.
- **Vidím v kódu:** kontakt s `use_company` čerpá z `company_info`, ale právní údaje prodejce z `documents.SUPPLIER`. Filtr právních dokumentů výslovně povoluje název tohoto dodavatele a u kontaktu z firemních údajů se filtr značky nepoužije. Stránky název prodejce zobrazují.
- **Proč je to špatně:** údaje na kontaktu a v právních informacích se mohou lišit; pravidla požadují údaje z `company_info`. Výjimka dovoluje zveřejnit zakázanou značku, pokud ji tento zdroj obsahuje. Obsah `documents.SUPPLIER` ani firemního nastavení jsem kvůli tomuto nálezu nevyhledával.
- **Návrh opravy:** všechny údaje prodejce čerpat z `company_info`. Kontrolovat soulad se zákazem značky i u právních dokumentů a údajů prodejce; nesoulad oznámit před zveřejněním místo použití starého zdroje či výjimky.

## 5. Střední — Zákazník může podvrhnout poznámku o přepočtu měny na dokladu

- **Soubor a řádky:** `api/miniweb_objednavky.py:310`, `429–434`; `api/miniweb_objednavky_admin.py:27–41`, `115–117`.
- **Vidím v kódu:** systémový snímek ceny se ukládá do stejného textu jako zákazníkem zadaný název firmy. Při tvorbě poznámky dokladu se bere první značka `EUR-SNAPSHOT` v tomto textu. Název firmy může takovou značku s vlastním JSON obsahovat ještě před skutečným snímkem.
- **Proč je to špatně:** poznámka na dokladu může uvádět zákazníkem podvržený přepočet. Čisté ověření to potvrdilo. Tímto netvrdím, že lze stejným způsobem změnit skutečné částky dokladu.
- **Návrh opravy:** ukládat snímek do samostatného strukturovaného pole, odděleného od zákaznických textů. Validovat jeho částky a kurz při čtení.

## 6. Střední — Firmy bez DIČ formulář odmítne, server je přijímá

- **Soubor a řádky:** `webapp/miniweb/miniweb-pages.js:335–341`, `371–378`; server `api/miniweb.py:592–599`, `api/miniweb_objednavky.py:222–223`.
- **Vidím v kódu:** košík a poptávka vyžadují DIČ pro každou zemi mimo ČR. Server přitom dovoluje DIČ neuvést a má pro tuto situaci vlastní cenovou větev.
- **Proč je to špatně:** například slovenská firma bez DIČ nemůže přes formulář pokračovat, přestože splňuje požadavek firmy a IČO. Pravidlo pro mini-shopy neomezuje prodej jen na firmy s DIČ.
- **Návrh opravy:** sjednotit formuláře se serverem: firma, IČO a firemní potvrzení povinné, DIČ nepovinné; jeho vyplnění ovlivní až ověření a výpočet.

## 7. Střední — Při výpadku cen zůstávají některé příplatky v původní měně

- **Soubor a řádky:** `api/miniweb_cena.py:90–107`.
- **Vidím v kódu:** bez nastavení se odstraní hlavní cena a příplatek pouze z volby `on`. Příplatky v dalších volbách zůstávají beze změny, zatímco větev s platným nastavením převádí všechny volby.
- **Proč je to špatně:** odpověď může míchat chybějící cenu s příplatky v Kč. Pokud je klient zobrazí pomocí formátování mini-shopu, označí je jako EUR. Čisté ověření potvrdilo ponechání původního příplatku.
- **Návrh opravy:** při chybě nastavení vracet jednoznačnou chybu výpočtu; žádná číselná cena ani příplatek nesmí projít nepřevedený. Při převodu kontrolovat všechny volby shodně.

## 8. Střední — Nastavení může rozbít již zapnuté objednávky

- **Soubor a řádky:** `api/miniweb_shops_admin.py:179–185`; návaznost `api/miniweb_objednavky.py:110–114`.
- **Vidím v kódu:** kontrola ceny se provede pouze tehdy, když požadavek výslovně zapíná `orders_enabled`. U již zapnutého obchodu lze samostatně změnit měnu, skrýt cenu nebo vymazat marži bez této kontroly.
- **Proč je to špatně:** konfigurace může dál hlásit objednávkový režim, ale kalkulace a objednávky začnou vracet chybu nedostupné ceny.
- **Návrh opravy:** kontrolovat výsledné nastavení po každé změně, pokud `after.orders_enabled` zůstává zapnuté. Současně vynutit pravidla cen z nálezu 3.

## 9. Střední — Osobní odběr obchází krok schválení potřebný pro tuto větev dokladů

- **Soubor a řádky:** `api/miniweb_objednavky.py:380–382`, `398–408`, `435–442`; `api/miniweb_objednavky_admin.py:86–95`, `112–118`.
- **Vidím v kódu:** osobní odběr nastaví `shipping_review` na nulu a při založení se nepředává platební metoda. Zdejší následná větev vystavení zálohové faktury přijme jen objednávky se zapnutým `shipping_review`; tam také probíhá potvrzení neověřeného DIČ.
- **Proč je to špatně:** osobní odběr neprojde touto větví vystavení dokladu ani její kontrolou DIČ. Domnívám se, že běžný postup zaměstnance bude pro tyto objednávky neúplný; existenci jiného ručního postupu jsem neověřoval.
- **Návrh opravy:** oddělit schválení dopravy od připravenosti k vystavení dokladu. U osobního odběru zajistit samostatný navazující krok včetně případné kontroly DIČ.

## 10. Střední — Katalog a hezké adresy přestanou fungovat za první stovkou produktů

- **Soubor a řádky:** `api/miniweb.py:47`, `466`, `491–492`; `api/miniweb_seo.py:152–161`, `333–335`; `webapp/miniweb/miniweb-pages.js:100–101`, `136–141`, `172–174`.
- **Vidím v kódu:** výchozí odpověď katalogu obsahuje nejvýše 100 produktů. Server hledá produkt pro hezkou adresu jen v této první odpovědi a stejně sestavuje mapu stránek. Úvod a kategorie nepokračují další stránkou, náhled detailu hledá nejvýše v prvních 200 produktech.
- **Proč je to špatně:** u většího katalogu mohou platné hezké adresy vracet 404 a další produkty chybějí v nabídce i mapě stránek. Skutečnou velikost katalogu jsem neověřil.
- **Návrh opravy:** detail dohledávat přímo podle slugu se stejnými pravidly viditelnosti. Pro seznamy a mapu stránek zpracovat všechny stránky nebo zavést viditelné stránkování.

## 11. Střední — Vnitřní čtení stránky sdílí omezení požadavků mezi návštěvníky

- **Soubor a řádky:** `api/miniweb_seo.py:60–72`, `140`, `152–153`; `api/miniweb.py:184–187`; návaznost `api/app.py:652–663`.
- **Vidím v kódu:** stránka volá API přes nový testovací klient a předává pouze doménu. Nepředává původní IP. Omezení mini-shopu přitom používá IP, která v takto vytvořeném požadavku patří testovacímu klientovi, nikoli návštěvníkovi.
- **Proč je to špatně:** vnitřní požadavky sdílejí společný limit i mezi doménami. Po jeho vyčerpání může chyba API vést k prázdným seznamům nebo falešnému 404. Cache dopad tlumí, ale chybové odpovědi se necachují.
- **Návrh opravy:** sdílet čtecí logiku přímo bez vytváření dalšího HTTP požadavku a návštěvníka omezovat na vstupu stránky. Případné interní předávání IP musí vycházet z ověřené adresy, nikoli libovolné hlavičky klienta.

## 12. Střední — Objednávkový náhled ztrácí obchod a může vyprázdnit košík bez uložení

- **Soubor a řádky:** `webapp/miniweb/miniweb-pages.js:30`, `235`, `351–354`, `381–383`; `api/miniweb_objednavky.py:384–385`; kontext `api/miniweb.py:154–171`.
- **Vidím v kódu:** poptávka přidává parametry vybraného obchodu a jazyka, kalkulace a objednávka nikoli. Objednávková odpověď s `preview: true` se zároveň zpracuje jako skutečné úspěšné odeslání a košík se vymaže. Poptávka náhled výslovně rozlišuje.
- **Proč je to špatně:** na společné doméně náhled objednávkového košíku nenajde vybraný obchod. Na vlastní doméně konceptu může po pouhé validaci smazat košík a hlásit odeslání.
- **Návrh opravy:** používat společnou tvorbu adres API i pro kalkulaci a objednávky. Při `preview: true` zachovat košík a zobrazit potvrzení náhledu.

## 13. Střední — Kontaktní formulář nefunguje pro obchod s více zeměmi

- **Soubor a řádky:** `webapp/miniweb/miniweb-pages.js:411–428`; `api/miniweb.py:654`, `675–680`.
- **Vidím v kódu:** formulář neposílá zemi a nenabízí její výběr. Server zemi doplní pouze u obchodu s jedinou zemí; jinak vrátí `country_required`.
- **Proč je to špatně:** správně vyplněný kontakt se u vícenárodního obchodu neodešle a návštěvník nemá pole, kterým chybu opraví.
- **Návrh opravy:** přidat výběr země ze seznamu obchodu a posílat ho spolu s ostatními údaji.

## 14. Střední — Poptávka přijímá zemi mimo povolený seznam obchodu

- **Soubor a řádky:** `api/miniweb.py:660–661`, `675–682`; srovnání `api/miniweb_objednavky.py:94–103`.
- **Vidím v kódu:** u poptávky se kontroluje tvar kódu země a případná výchozí hodnota, nikoli členství v seznamu povolených zemí. Objednávka toto členství kontroluje.
- **Proč je to špatně:** přímý požadavek může obejít omezení formuláře a vložit poptávku ze země, kterou obchod nenabízí. Tento dopad závisí na tom, zda seznam vymezuje přípustné země i pro poptávky; objednávková větev s ním tak zachází.
- **Návrh opravy:** sjednotit kontrolu zemí pro kontakt, poptávku a objednávku. Pokud je širší příjem poptávek záměrný, výslovně ho oddělit od seznamu zemí dodání.

## 15. Střední — Poškozený uložený košík může zablokovat celý obchod

- **Soubor a řádky:** `webapp/miniweb/miniweb.js:119–127`, `160`, `215`; `webapp/miniweb/miniweb-pages.js:206–209`, `226`, `277–288`.
- **Vidím v kódu:** čtení košíku zachytí neplatný JSON, ale nekontroluje, zda výsledkem je seznam platných položek. Následně se bez kontroly volají `reduce`, `filter`, `map` a přistupuje se k položkám. Odznak košíku se vytváří při startu každé stránky.
- **Proč je to špatně:** syntakticky platná uložená hodnota jako `null`, objekt nebo seznam obsahující `null` může vyvolat chybu již při startu. Není to samo o sobě průnik útočníka, ale chyba obnovy po poškození či změně formátu uložených dat.
- **Návrh opravy:** ověřit seznam, tvar každé položky, množství a konfiguraci; neplatné položky bezpečně vyřadit a umožnit obnovu košíku.

## 16. Nízká — Textová pole přijímají i objekty a jiné nečekané typy

- **Soubor a řádky:** `api/miniweb.py:107–122`, `650–655`; `api/miniweb_objednavky.py:292–310`.
- **Vidím v kódu:** čisticí funkce převádí libovolný vstup na text. JSON objekt zadaný jako jméno, firma či část adresy tak může projít kontrolou neprázdnosti. Čisté ověření přijetí objektu potvrdilo. IČO se kontroluje jen formálně; projde i osm nul.
- **Proč je to špatně:** do evidence se dostanou nesmyslné kontaktní údaje; formální vyplnění není ověřením skutečné firmy. Poslední bod uvádím jako omezení ochrany, nikoli jako důkaz prodeje spotřebiteli.
- **Návrh opravy:** před čištěním vyžadovat textový typ, rozumné délky a odmítat strukturované hodnoty. Oddělit syntaktickou kontrolu IČO od ověření firmy; v této kopii žádné registry nevolat.

## Co jsem ověřil a co zůstává neověřené

Čistý skript `vystupy/overeni_minishop.py` úspěšně reprodukoval přijetí nesprávného typu textu, ponechaný nepřevedený příplatek a podvržení poznámky snímku ceny. Dále ověřil, že objednávková funkce odmítá zemi mimo seznam. Načítá pouze vybrané funkce ze zdrojů; neimportuje aplikaci a nevolá síť ani databázi. Příkaz: `python3 -B vystupy/overeni_minishop.py`. Jde o reprodukce současného chybného chování, nikoli o potvrzení opravy.

V kódu jsou také užitečné ochrany: veřejnost nedostává koncepty, dotazy používají parametrizované hodnoty, veřejné texty se vkládají přes `textContent` nebo escapování, veřejné zápisové požadavky mají limit velikosti a objednávková cena se počítá na serveru. To nevylučuje jiné chyby mimo rozsah kontroly.

Neověřoval jsem provozní nastavení, skutečná data, oprávnění konkrétních účtů, dostupnost cizích služeb ani původ všech technických tvrzení v překladech. U jejich pravdivosti proto nevyslovuji závěr. Nejde o právní či daňové posouzení. Nálezy v objednávkách a administraci jsou pouze návrhy pro příslušné boty, žádný zásah do jejich práce.

Zbývá předat nálezy bot3, opravit je v příslušných oblastech a po opravách ověřit chování na oddělených testovacích datech.
