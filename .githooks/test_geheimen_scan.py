#!/usr/bin/env python3
"""Tests voor geheimen-scan.py. De nep-geheimen worden hier pas bij het draaien
opgebouwd, zodat dit testbestand zelf geen treffer geeft."""
import base64
import importlib.util
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

HIER = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("geheimen_scan", os.path.join(HIER, "geheimen-scan.py"))
gs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gs)


def b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


def nep_jwt(rol):
    return ".".join([b64({"alg": "HS256", "typ": "JWT"}), b64({"role": rol, "iss": "supabase"}), "Ab3_" * 11])


class GeheimenScanTest(unittest.TestCase):
    def soorten(self, tekst):
        return [v[1] for v in gs.scan_tekst(tekst)]

    def test_service_role_jwt_geblokkeerd(self):
        self.assertEqual(self.soorten(f"const k = '{nep_jwt('service_role')}'"), ["jwt(role=service_role)"])

    def test_anon_jwt_toegestaan(self):
        self.assertEqual(self.soorten(f"url?apikey={nep_jwt('anon')}"), [])

    def test_ac_key_72_hex(self):
        self.assertEqual(self.soorten("AC_API_KEY=" + "ab12" * 18), ["activecampaign-key"])

    def test_sha256_64_hex_geen_treffer(self):
        self.assertEqual(self.soorten("sha=" + "ab12" * 16), [])

    def test_anthropic_key(self):
        self.assertEqual(self.soorten("sk-" + "ant-" + "a1B2" * 12), ["anthropic/openai-key"])

    def test_telegram_token(self):
        self.assertEqual(self.soorten("123456789:" + "AA" + "b" * 33), ["telegram-token"])

    def test_google_client_secret(self):
        self.assertEqual(self.soorten("GOCSPX" + "-" + "a" * 28), ["google-client-secret"])

    def test_negeer_marker(self):
        self.assertEqual(self.soorten(f"{nep_jwt('service_role')}  # geheimen-scan" + ":negeer"), [])

    def test_uitvoer_bevat_geen_waarde(self):
        tok = nep_jwt("service_role")
        nr, soort, lengte, h = gs.scan_tekst(tok)[0]
        self.assertNotIn(tok, f"{nr}{soort}{lengte}{h}")
        self.assertEqual(len(h), 8)

    def test_placeholder_xxxx_geen_treffer(self):
        self.assertEqual(self.soorten("ANTHROPIC_API_KEY=sk-ant-" + "x" * 40), [])

    def test_toegestane_sha8(self):
        tok = nep_jwt("service_role")
        self.assertEqual(gs.scan_tekst(tok, frozenset({gs.sha8(tok)})), [])

    def test_env_verwijzing_geen_treffer(self):
        self.assertEqual(self.soorten("const k = process.env.SUPABASE_SERVICE_ROLE_KEY"), [])


if __name__ == "__main__":
    unittest.main()
