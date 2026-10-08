#!/usr/bin/env python3
"""
Testy sdileneho `net_fetch.fetch_public_url` (bot6, 2026-09-02, revize 17).

Spusteni:  ./api/venv/bin/python api/test_net_fetch.py

ZADNY skutecny sitovy pozadavek se neposila (`build_opener` i
`getaddrinfo` jsou podstrcene) a nic se nezapisuje do DB - testuje se
prave to, ze se na interni adresu VUBEC nepokusime pripojit.
"""
import io
import os
import sys
import unittest
import urllib.error
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import net_fetch  # noqa: E402


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _opener_returning(payload):
    opener = mock.Mock()
    opener.open.return_value = _FakeResponse(payload)
    return opener


def _opener_redirecting(location, code=302):
    """Simuluje `NoRedirectHandler`: misto nasledovani vyhodi HTTPError."""
    opener = mock.Mock()
    opener.open.side_effect = urllib.error.HTTPError(
        location, code, "Redirect blocked (SSRF ochrana)", {"Location": location}, None)
    return opener


def _public_dns(_host, port):
    return [(2, 1, 6, "", ("93.184.216.34", port))]


def _internal_dns(_host, port):
    return [(2, 1, 6, "", ("127.0.0.1", port))]


class FetchPublicUrlTest(unittest.TestCase):

    def test_odmitne_file_schema(self):
        """Puvodni dira (AUDIT 2026-08-18 nalez 1.4): urllib ma
        FileHandler, takze bez allowlistu by tohle precetlo .env."""
        with self.assertRaises(ValueError) as ctx:
            net_fetch.fetch_public_url("file:///opt/konfigurator/api/.env",
                                       timeout=1, max_bytes=1024)
        self.assertIn("schéma", str(ctx.exception))

    def test_odmitne_interni_adresu_bez_pripojeni(self):
        with mock.patch.object(net_fetch.socket, "getaddrinfo", _internal_dns), \
             mock.patch.object(net_fetch.urllib.request, "build_opener") as bo:
            with self.assertRaises(ValueError) as ctx:
                net_fetch.fetch_public_url("http://vnitrni.example/x",
                                           timeout=1, max_bytes=1024)
            self.assertIn("interní", str(ctx.exception))
            bo.assert_not_called()   # ani se nepokusime pripojit

    def test_stahne_verejnou_url(self):
        with mock.patch.object(net_fetch.socket, "getaddrinfo", _public_dns), \
             mock.patch.object(net_fetch.urllib.request, "build_opener",
                               return_value=_opener_returning(b"ahoj")):
            self.assertEqual(
                net_fetch.fetch_public_url("https://example.com/a", timeout=1, max_bytes=1024),
                b"ahoj")

    def test_prekroceny_limit_velikosti(self):
        """Driv bylo `resp.read()` bez argumentu - obri odpoved = RAM."""
        with mock.patch.object(net_fetch.socket, "getaddrinfo", _public_dns), \
             mock.patch.object(net_fetch.urllib.request, "build_opener",
                               return_value=_opener_returning(b"x" * 5000)):
            with self.assertRaises(ValueError) as ctx:
                net_fetch.fetch_public_url("https://example.com/a", timeout=1, max_bytes=100)
            self.assertIn("limit", str(ctx.exception))

    def test_presne_na_limitu_projde(self):
        with mock.patch.object(net_fetch.socket, "getaddrinfo", _public_dns), \
             mock.patch.object(net_fetch.urllib.request, "build_opener",
                               return_value=_opener_returning(b"x" * 100)):
            self.assertEqual(
                len(net_fetch.fetch_public_url("https://example.com/a", timeout=1, max_bytes=100)),
                100)

    def test_presmerovani_se_nasleduje_a_znovu_overi(self):
        """http->https redirect e-shopu je legitimni, musi projit."""
        openers = [_opener_redirecting("https://example.com/cil"),
                   _opener_returning(b"cena")]
        with mock.patch.object(net_fetch.socket, "getaddrinfo", _public_dns), \
             mock.patch.object(net_fetch.urllib.request, "build_opener",
                               side_effect=openers):
            self.assertEqual(
                net_fetch.fetch_public_url("http://example.com/a", timeout=1, max_bytes=1024),
                b"cena")

    def test_presmerovani_na_interni_adresu_je_odmitnuto(self):
        """Jadro obrany: cil se overuje u KAZDEHO skoku, ne jen u prvniho."""
        hosts = {"example.com": _public_dns, "vnitrni.example": _internal_dns}

        def dns(host, port):
            return hosts[host](host, port)

        with mock.patch.object(net_fetch.socket, "getaddrinfo", dns), \
             mock.patch.object(net_fetch.urllib.request, "build_opener",
                               return_value=_opener_redirecting("http://vnitrni.example/meta")):
            with self.assertRaises(ValueError) as ctx:
                net_fetch.fetch_public_url("https://example.com/a", timeout=1, max_bytes=1024)
            self.assertIn("interní", str(ctx.exception))

    def test_prilis_mnoho_presmerovani(self):
        with mock.patch.object(net_fetch.socket, "getaddrinfo", _public_dns), \
             mock.patch.object(net_fetch.urllib.request, "build_opener",
                               return_value=_opener_redirecting("https://example.com/dal")):
            with self.assertRaises(ValueError) as ctx:
                net_fetch.fetch_public_url("https://example.com/a", timeout=1,
                                           max_bytes=1024, max_redirects=2)
            self.assertIn("přesměrování", str(ctx.exception))

    def test_jina_http_chyba_propadne_volajicimu(self):
        """404/500 NENI ValueError - volajici je uz umi odlisit."""
        opener = mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError(
            "https://example.com/a", 404, "Not Found", {}, None)
        with mock.patch.object(net_fetch.socket, "getaddrinfo", _public_dns), \
             mock.patch.object(net_fetch.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(urllib.error.HTTPError):
                net_fetch.fetch_public_url("https://example.com/a", timeout=1, max_bytes=1024)

    def test_multicast_je_taky_interni(self):
        """ipaddress.is_global vraci u multicastu True - proto extra kontrola."""
        with mock.patch.object(net_fetch.socket, "getaddrinfo",
                               lambda h, p: [(2, 1, 6, "", ("224.0.0.1", p))]):
            self.assertIsNotNone(net_fetch.ensure_public_host("multicast.example", 80))


class PriceFetchIntegrationTest(unittest.TestCase):
    """Overuje, ze scrapery cen helper opravdu POUZIVAJI a ze jeho
    ValueError konci jako ok=False, ne jako traceback z Flask routy."""

    def test_refresh_prevede_odmitnuty_zdroj_na_ok_false(self):
        import remeslo_price_refresh as rpr
        with mock.patch.object(rpr, "_fetch", side_effect=ValueError("URL míří na interní adresu.")):
            ok, price, err = rpr.refresh_one_price(
                cur=mock.Mock(),
                price_row={"id": 1, "product_url": "http://127.0.0.1/x", "price_source_url": None},
                source_row={"supplier_name": "OBI.cz", "id": 9},
                now_fn=lambda: "2026-09-02 00:00:00")
        self.assertFalse(ok)
        self.assertIsNone(price)
        self.assertIn("odmitnut", err)

    def test_search_prevede_odmitnuty_zdroj_na_prazdny_vysledek(self):
        import remeslo_price_search as rps
        with mock.patch.object(rps, "_fetch", side_effect=ValueError("Odpověď je příliš velká.")):
            self.assertEqual(rps.search_obi("trubka"), [])


class PriceBoundsTest(unittest.TestCase):
    """Meze cen (bot6, revize 17, commit 2) - inf/nan driv proslo pres
    `<= 0`, vyscrapovana cena se zapisovala bez jakekoli kontroly."""

    def test_refresh_odmitne_cenu_mimo_rozsah(self):
        import remeslo_price_refresh as rpr
        cur = mock.Mock()
        for bad in (0.0, -5.0, float("inf"), float("nan"), 2_000_000.0):
            with mock.patch.object(rpr, "_fetch", return_value="<html/>"), \
                 mock.patch.dict(rpr._EXTRACTORS, {"OBI.cz": lambda _h: bad}):
                ok, price, err = rpr.refresh_one_price(
                    cur=cur,
                    price_row={"id": 1, "product_url": "https://obi.cz/x", "price_source_url": None},
                    source_row={"supplier_name": "OBI.cz", "id": 9},
                    now_fn=lambda: "2026-09-02 00:00:00")
                self.assertFalse(ok, f"{bad} nemelo projit")
                self.assertEqual(err, "cena mimo rozsah")
        cur.execute.assert_not_called()   # nic se nezapsalo

    def test_refresh_prijme_rozumnou_cenu(self):
        import remeslo_price_refresh as rpr
        cur = mock.Mock()
        with mock.patch.object(rpr, "_fetch", return_value="<html/>"), \
             mock.patch.dict(rpr._EXTRACTORS, {"OBI.cz": lambda _h: 1234.5}):
            ok, price, err = rpr.refresh_one_price(
                cur=cur,
                price_row={"id": 1, "product_url": "https://obi.cz/x", "price_source_url": None},
                source_row={"supplier_name": "OBI.cz", "id": 9},
                now_fn=lambda: "2026-09-02 00:00:00")
        self.assertTrue(ok)
        self.assertEqual(price, 1234.5)
        cur.execute.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
