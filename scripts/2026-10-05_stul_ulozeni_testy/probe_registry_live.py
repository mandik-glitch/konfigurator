#!/usr/bin/env python3
"""Zivy PRUZKUM overovacich sluzeb (jen cteni, nic se neuklada, e-mail se neodesila): ARES (CZ), RPO (SK), DNS-over-HTTPS + dig (MX) pres funkce api/stul_ulozeni.py.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-05_stul_ulozeni_testy/probe_registry_live.py"""
import os, sys, threading, time
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(REPO); sys.path.insert(0, os.path.join(REPO, "api"))
_o = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
import app  # noqa: F401
import stul_ulozeni as U
threading.Thread.start = _o


def zkus(popis, fn):
    t = time.time()
    try:
        r = fn(); print("%-46s -> %s (%.2f s)" % (popis, r, time.time() - t))
    except U.UlozChyba as e:
        print("%-46s -> chyba %s %s (%.2f s)" % (popis, e.status, e.code, time.time() - t))


zkus("CZ 28337638 (Logiman)", lambda: U.overit_ico("28337638", "CZ"))
zkus("CZ 27082440 (platná číslice, jiná firma)", lambda: U.overit_ico("27082440", "CZ"))
zkus("CZ 12345678 (špatná číslice)", lambda: U.overit_ico("12345678", "CZ"))
zkus("CZ 12345670? (číslice sedí, v ARES není?)", lambda: U.overit_ico("12345670", "CZ") if U.ico_checksum_ok("12345670") else "kontrolní číslice nesedí")
zkus("SK 35757442 (VW Slovakia)", lambda: U.overit_ico("35757442", "SK"))
zkus("SK 99999999 (neexistuje)", lambda: U.overit_ico("99999999", "SK"))
zkus("e-mail doména gmail.com", lambda: U.overit_domenu_emailu("a@gmail.com"))
zkus("e-mail doména seznam.cz", lambda: U.overit_domenu_emailu("a@seznam.cz"))
zkus("e-mail doména neexistuje-xyz-12345.cz", lambda: U.overit_domenu_emailu("a@neexistuje-xyz-12345.cz"))
zkus("dig MX gmail.com", lambda: U._mx_dig("gmail.com"))
zkus("dig MX neexistuje-xyz-12345.cz", lambda: U._mx_dig("neexistuje-xyz-12345.cz"))
