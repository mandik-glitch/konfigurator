"""Pouziti: python3 patch_dealers_storefront.py <dealers.py> - atribuce objednavky podle prirazeni mini-shopu (storefront_dealers), dealer_source, knihovna prirazeni (bot5, 2026-10-02)."""
import sys

p = sys.argv[1]
t = open(p, encoding="utf-8").read()


def zamen(a, b):
    global t
    assert t.count(a) == 1, (t.count(a), a[:90])
    t = t.replace(a, b)


# 1) pomocnik "vlastni nakup" a pouziti v klikove atribuci (chovani beze zmeny)
zamen('''def attribution_for_new_order(cur, click_token, user, customer_email, is_test=False, billing_ico=None):''', '''def _own_purchase(dealer, user, customer_email, billing_ico):
    """Nakup dealera sam sobe (jeho ucet, jeho e-mail kontaktu, jeho ICO) se dealerovi nepripisuje."""
    if user and dealer["user_id"] and user.get("id") == dealer["user_id"]:
        return True
    if customer_email and dealer["contact_email"] and customer_email.strip().lower() == dealer["contact_email"].strip().lower():
        return True
    if billing_ico and dealer["ico"] and re.sub(r"\\s", "", billing_ico) == re.sub(r"\\s", "", dealer["ico"]):
        return True
    return False


def attribution_for_new_order(cur, click_token, user, customer_email, is_test=False, billing_ico=None):''')
zamen('''    if user and dealer["user_id"] and user.get("id") == dealer["user_id"]:
        return None
    if customer_email and dealer["contact_email"] and customer_email.strip().lower() == dealer["contact_email"].strip().lower():
        return None
    if billing_ico and dealer["ico"] and re.sub(r"\\s", "", billing_ico) == re.sub(r"\\s", "", dealer["ico"]):
        return None
    return {"dealer_id": dealer["id"], "click_id": click["id"], "order_path": "our"}
''', '''    if _own_purchase(dealer, user, customer_email, billing_ico):
        return None
    return {"dealer_id": dealer["id"], "click_id": click["id"], "order_path": "our"}
''')

# 2) nova atribuce: prirazeni mini-shopu + attach_attribution
start = t.index("def attach_attribution(cur, order_id, user, click_token=None):")
end = t.index("# ---------------------------------------------------------------------------------------------------------------- administrace (admin)", start)
assert "dealer_source" not in t[start:end]
novy = '''def storefront_assignment(cur, storefront_id, at=None):
    """Prirazeni mini-shopu dealerovi PLATNE v danem okamziku (vychozi: ted) = radek storefront_dealers nebo None. Volat jen pri vzniku objednavky - zpetne se nic nepocita."""
    at = at or _now()
    cur.execute("SELECT * FROM storefront_dealers WHERE storefront_id=%s AND valid_from <= %s AND (valid_to IS NULL OR valid_to > %s) "
                "ORDER BY valid_from DESC, id DESC LIMIT 1", (storefront_id, at, at))
    return cur.fetchone()


def storefront_attribution(cur, storefront_id, user, customer_email, is_test=False, billing_ico=None):
    """-> (rozhodl, attr). rozhodl=False: mini-shop nema ted platne prirazeni dealerovi, rozhoduje dal klik z cookie. rozhodl=True: mini-shop prirazeni MA a rozhoduje on, i kdyz je tu klik
    jineho dealera (cena a atribuce musi souhlasit). attr = {'dealer_id', 'click_id': None, 'order_path': 'our', 'source': 'storefront'} nebo None = dealera nelze pripsat (neni aktivni,
    ma cestu 'dealer', testovaci objednavka, vlastni nakup) a objednavka zustava NASE, zadny navrat ke kliku."""
    a = storefront_assignment(cur, storefront_id)
    if not a:
        return False, None
    if is_test:
        return True, None
    dealer = _load_dealer(cur, a["dealer_id"])
    if not _dealer_usable(dealer) or dealer["order_path"] != "our" or _own_purchase(dealer, user, customer_email, billing_ico):
        return True, None
    return True, {"dealer_id": dealer["id"], "click_id": None, "order_path": "our", "source": "storefront"}


def attach_attribution(cur, order_id, user, click_token=None):
    """Volano z orders_create PO vytvoreni objednavky, PRED commitem: pripise objednavku dealerovi. Poradi (Robert/bot3 2026-10-02): 1) mini-shop (storefront_id objednavky) s prirazenim
    dealera platnym V TU CHVILI rozhoduje vzdy, i kdyz je tu cookie z prokliku jineho dealera, 2) jinak cookie dlr (30 dni, last-click). Bez dealera zustava dealer_id prazdne a objednavka je
    nase. dealer_source = 'storefront' nebo 'click'. NIKDY nevyhodi vyjimku (objednavka se nesmi kvuli dealerovi rozbit) - selhani jen zaloguje a vrati False. True = pripsano dealerovi."""
    try:
        cur.execute("SELECT customer_email, billing_ico, is_test, dealer_id, storefront_id FROM shop_orders WHERE id=%s", (order_id,))
        o = cur.fetchone()
        if not o or o["dealer_id"] is not None:
            return False
        rozhodl, attr = False, None
        if o["storefront_id"]:
            rozhodl, attr = storefront_attribution(cur, o["storefront_id"], user, o["customer_email"], bool(o["is_test"]), o["billing_ico"])
        if not rozhodl:
            if click_token is None:
                click_token = request.cookies.get(CLICK_COOKIE)
            if not click_token:
                return False
            attr = attribution_for_new_order(cur, click_token, user, o["customer_email"], bool(o["is_test"]), o["billing_ico"])
            if attr:
                attr["source"] = "click"
        if not attr:
            return False
        cur.execute("UPDATE shop_orders SET dealer_id=%s, dealer_click_id=%s, order_path=%s, dealer_source=%s WHERE id=%s AND dealer_id IS NULL",
                    (attr["dealer_id"], attr["click_id"], attr["order_path"], attr["source"], order_id))
        return cur.rowcount == 1
    except Exception:
        app.logger.exception("attach_attribution: pripsani objednavky %s dealerovi selhalo", order_id)
        return False


def assign_storefront(cur, storefront_id, dealer_id, valid_from=None, note=None, created_by=None):
    """Prirazeni mini-shopu dealerovi OD TED (nebo od budouciho okamziku): dosud platne prirazeni bez konce se zavre (valid_to = valid_from), zalozi se nove. NIKDY zpetne: valid_from v minulosti
    se odmitne - objednavky pred prirazenim zustavaji nase (zpetna provize je samostatna akce na pokyn Roberta). Dealer musi byt aktivni a mit cestu 'our'. -> id noveho radku, ValueError s cesky textem."""
    now = _now()
    valid_from = valid_from or now
    if valid_from < now - datetime.timedelta(seconds=60):
        raise ValueError("Přiřazení nejde nastavit zpětně (objednávky před přiřazením zůstávají naše). Zpětná provize je samostatná akce na pokyn Roberta.")
    cur.execute("SELECT id FROM car_storefronts WHERE id=%s FOR UPDATE", (storefront_id,))
    if not cur.fetchone():
        raise ValueError("Mini-shop neexistuje.")
    dealer = _load_dealer(cur, dealer_id)
    if not dealer:
        raise ValueError("Dealer neexistuje.")
    if not _dealer_usable(dealer):
        raise ValueError("Dealer musí být aktivní.")
    if dealer["order_path"] != "our":
        raise ValueError("Dealer musí mít cestu objednávky „dokončí se u nás“.")
    cur.execute("SELECT * FROM storefront_dealers WHERE storefront_id=%s AND valid_to IS NULL ORDER BY id DESC LIMIT 1 FOR UPDATE", (storefront_id,))
    current = cur.fetchone()
    if current:
        if current["dealer_id"] == dealer["id"]:
            raise ValueError("Tento dealer už je mini-shopu přiřazen.")
        if current["valid_from"] >= valid_from:
            raise ValueError("Naplánované přiřazení už existuje, nejdřív ho ukončete.")
        cur.execute("UPDATE storefront_dealers SET valid_to=%s WHERE id=%s", (valid_from, current["id"]))
    cur.execute("INSERT INTO storefront_dealers (storefront_id, dealer_id, valid_from, note, created_by) VALUES (%s,%s,%s,%s,%s)",
                (storefront_id, dealer["id"], valid_from, _clean(note, 255), created_by))
    return cur.lastrowid


def end_assignment(cur, storefront_id, valid_to=None):
    """Ukonci prirazeni mini-shopu bez konce (od ted, nebo od budouciho okamziku). Nikdy zpetne. Je-li posledni prirazeni bez konce NEZACATE (naplanovane na budoucnost), jde o ZRUSENI:
    nikdy nic nepripise a predchozi prirazeni, ktere koncilo v jeho zacatku, se znovu otevre (zrusena naplanovana zmena dealera = puvodni dealer pokracuje). -> True, kdyz nejake bylo,
    False kdyz ne. Objednavky, ktere dealer uz ma, se nemeni."""
    now = _now()
    valid_to = valid_to or now
    if valid_to < now - datetime.timedelta(seconds=60):
        raise ValueError("Ukončení nejde nastavit zpětně.")
    cur.execute("SELECT id, valid_from FROM storefront_dealers WHERE storefront_id=%s AND valid_to IS NULL ORDER BY id DESC LIMIT 1 FOR UPDATE", (storefront_id,))
    row = cur.fetchone()
    if not row:
        return False
    if row["valid_from"] > now:
        cur.execute("UPDATE storefront_dealers SET valid_to=valid_from WHERE id=%s", (row["id"],))
        cur.execute("UPDATE storefront_dealers SET valid_to=NULL WHERE storefront_id=%s AND valid_to=%s AND id<>%s ORDER BY id DESC LIMIT 1", (storefront_id, row["valid_from"], row["id"]))
        return True
    cur.execute("UPDATE storefront_dealers SET valid_to=%s WHERE id=%s", (max(valid_to, row["valid_from"]), row["id"]))
    return True


'''
t = t[:start] + novy + t[end:]
open(p, "w", encoding="utf-8").write(t)
