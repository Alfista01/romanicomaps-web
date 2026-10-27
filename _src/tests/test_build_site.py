"""Pruebas del generador de la web (portada, legales, sitemap, robots).

Cubren lo que no puede volver a romperse: el SEO de la portada, que la FAQ
visible coincida con la del esquema, el dominio canonico y que el generador se
niegue a escribir si algo falla. No escriben nada en disco.

    cd _src && python3 -m unittest discover -s tests
"""
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "_build_site.py"
SPEC = importlib.util.spec_from_file_location("_build_site", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class TestSitio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.salida = MOD.construir()
        cls.idx = cls.salida["index.html"]

    def test_todo_lo_generado_pasa_las_comprobaciones(self):
        self.assertEqual(MOD.comprobar(self.salida), [])

    def test_portada_conserva_el_seo(self):
        for marca in ('<link rel="canonical" href="https://romanicomaps.com/">',
                      'property="og:image" content="https://romanicomaps.com/img/og-romanicomaps.jpg"',
                      'name="twitter:card"', 'application/ld+json'):
            self.assertIn(marca, self.idx)

    def test_faq_visible_igual_a_faq_del_esquema(self):
        bloque = re.search(r'<script type="application/ld\+json">(.*?)</script>', self.idx, re.S).group(1)
        faq = [n for n in json.loads(bloque)["@graph"] if n["@type"] == "FAQPage"][0]
        self.assertEqual([q["name"] for q in faq["mainEntity"]], [q for q, _ in MOD.FAQ])

    def test_paginas_legales_con_canonical_propio(self):
        for archivo in ("privacidad.html", "aviso-legal.html", "agradecimientos.html", "condiciones-uso.html"):
            self.assertIn(f'<link rel="canonical" href="https://romanicomaps.com/{archivo}">', self.salida[archivo])

    def test_precio_coherente_en_portada_y_faq(self):
        self.assertIn(MOD.PRECIO_PRIMER_ANIO, self.idx)
        self.assertIn(MOD.PRECIO_RENOVACION, self.idx)
        self.assertTrue(any(MOD.PRECIO_PRIMER_ANIO in a for _, a in MOD.FAQ))

    def test_robots_y_sitemap(self):
        self.assertIn("Sitemap: https://romanicomaps.com/i/sitemap.xml", self.salida["robots.txt"])
        self.assertNotIn("Disallow: /", self.salida["robots.txt"])
        for archivo in MOD.TEMATICAS:
            self.assertIn(f"<loc>https://romanicomaps.com/{archivo}</loc>", self.salida["sitemap.xml"])

    # El comprobador tiene que detectar las roturas tipicas.
    def test_detecta_portada_sin_canonical(self):
        roto = dict(self.salida, **{"index.html": re.sub(r'<link rel="canonical"[^>]*>', "", self.idx)})
        self.assertTrue(any("canonical" in e for e in MOD.comprobar(roto)))

    def test_detecta_www(self):
        roto = dict(self.salida, **{"index.html": self.idx.replace("https://romanicomaps.com/", "https://www.romanicomaps.com/", 1)})
        self.assertTrue(any("www" in e for e in MOD.comprobar(roto)))

    def test_detecta_faq_descuadrada(self):
        roto = dict(self.salida, **{"index.html": self.idx.replace("<summary>", "<summary>X", 1)})
        self.assertTrue(any("FAQPage" in e for e in MOD.comprobar(roto)))

    def test_detecta_imagen_inexistente(self):
        roto = dict(self.salida, **{"index.html": self.idx.replace("img/mapa-iglesias.webp", "img/no-existe.webp")})
        self.assertTrue(any("no-existe" in e for e in MOD.comprobar(roto)))

    def test_detecta_disallow(self):
        roto = dict(self.salida, **{"robots.txt": "User-agent: *\nDisallow: /\n"})
        self.assertTrue(any("Disallow" in e or "falta" in e for e in MOD.comprobar(roto)))

    def test_marca_sin_valor_para_el_generador(self):
        with self.assertRaises(SystemExit):
            MOD.rellenar("<p>{{NO_EXISTE}}</p>", {}, "prueba")


if __name__ == "__main__":
    unittest.main()
