"""B4.4 - Pruebas de la ficha web publica.

Cubren las tres garantias que no pueden romperse nunca: el noindex, el
contrato de campos y la longitud del preview. Sin red ni ficheros del repo.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "generar_fichas_web.py"
SPEC = importlib.util.spec_from_file_location("generar_fichas_web", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)

PORTADA = "https://cdn.example/portadas/182-abc.jpg"


def iglesia(**extra):
    base = dict(
        idCode=182,
        idUnico="Girona-Sant Esteve d'en Bas-Iglesia de Sant Esteve",
        nombre="Iglesia de Sant Esteve",
        provincia="Girona",
        ciudad="Sant Esteve d'en Bas",
        tipoConstruccion="Iglesia parroquial de origen monástico",
        datacion="El edificio actual fue consagrado en 1050, " * 8,
        siglo="XI",
        estadoConservacion="Parcialmente conservada, " * 10,
        image01="https://airtable/x.jpg",
        activa="Sí",
    )
    base.update(extra)
    return base


PDF = "https://romanicodigital.com/sites/default/files/pdfs/files/girona_BAS.pdf"


class NoindexTest(unittest.TestCase):
    def test_por_defecto_la_ficha_lleva_noindex(self):
        html = MOD.render(iglesia(), PORTADA)
        self.assertIn('name="robots" content="noindex, nofollow"', html)

    def test_validar_rechaza_una_pagina_sin_noindex(self):
        html = MOD.render(iglesia(), PORTADA).replace("noindex, nofollow", "index")
        with self.assertRaises(SystemExit):
            MOD.validar(html, iglesia())

    def test_la_ficha_de_la_tanda_se_abre_y_valida(self):
        html = MOD.render(iglesia(), PORTADA, indexable=True)
        self.assertIn('name="robots" content="index, follow"', html)
        MOD.validar(html, iglesia(), indexable=True)

    def test_validar_rechaza_abrir_una_ficha_fuera_de_la_tanda(self):
        html = MOD.render(iglesia(), PORTADA, indexable=True)
        with self.assertRaises(SystemExit):
            MOD.validar(html, iglesia(), indexable=False)


class TandaTest(unittest.TestCase):
    def activas(self):
        return [iglesia(idCode=1, notasVisita="Abierta los domingos", pdf=PDF),
                iglesia(idCode=2),
                iglesia(idCode=3, notasVisita="Abierta", resumenElementos="Ábside",
                        pdf=PDF)]

    def test_rellena_con_las_mas_completas(self):
        elegidas = MOD.seleccionar_indexables(self.activas(),
                                              {"limite": 2, "indexadas": []})
        self.assertEqual(elegidas, ["1", "3"])

    def test_una_ficha_abierta_no_se_cierra(self):
        elegidas = MOD.seleccionar_indexables(self.activas(),
                                              {"limite": 2, "indexadas": ["2"]})
        self.assertEqual(elegidas, ["2", "3"])

    def test_una_ficha_que_deja_de_estar_activa_sale(self):
        elegidas = MOD.seleccionar_indexables(self.activas()[1:],
                                              {"limite": 5, "indexadas": ["1"]})
        self.assertNotIn("1", elegidas)

    def test_limite_nulo_abre_todas(self):
        elegidas = MOD.seleccionar_indexables(self.activas(),
                                              {"limite": None, "indexadas": []})
        self.assertEqual(elegidas, ["1", "2", "3"])

    def test_sitemap_lista_solo_urls_canonicas(self):
        xml = MOD.sitemap([MOD.url_canonica(iglesia())])
        self.assertIn("<loc>https://romanicomaps.com/i/182/girona-sant-esteve-d-en-bas-"
                      "iglesia-de-sant-esteve</loc>", xml)
        self.assertEqual(xml.count("<url>"), 1)


class FuenteTest(unittest.TestCase):
    def test_con_pdf_se_cita_la_fuente(self):
        html = MOD.render(iglesia(pdf=PDF), PORTADA)
        self.assertIn(f'href="{PDF}"', html)
        self.assertIn("Fuente principal: <a", html)
        self.assertIn("Románico Digital", html)

    def test_sin_pdf_no_hay_linea_de_fuente(self):
        for vacio in (None, "", "   "):
            html = MOD.render(iglesia(pdf=vacio), PORTADA)
            self.assertNotIn('class="fuente"', html)
            self.assertNotIn("Fuente principal", html)

    def test_un_pdf_de_otro_dominio_no_se_publica(self):
        html = MOD.render(iglesia(pdf="https://otro.example/x.pdf"), PORTADA)
        self.assertNotIn("otro.example", html)

    def test_datos_estructurados_sin_campos_de_la_app(self):
        ig = iglesia(lat=42.1, lon=2.4, notasVisita="CENTINELA_NOTAS")
        html = MOD.render(ig, PORTADA)
        self.assertIn('"@type":"Church"', html)
        self.assertIn('"latitude":42.1', html)
        self.assertNotIn("CENTINELA_NOTAS", html)


class ContratoTest(unittest.TestCase):
    def test_no_se_filtran_campos_de_la_ficha_completa(self):
        """La ficha publica es un subconjunto: estos campos viven en la App."""
        ig = iglesia(
            notasVisita="Abierta los domingos por la mañana, preguntar en el bar",
            resumenElementos="Abside semicircular con arcuaciones lombardas y frisos",
            vinculos="https://ejemplo.org/sant-esteve-den-bas-informacion",
            otraInfo="Restaurada en 1987 por la Diputacion provincial de Girona",
            urlGoogleMaps="https://maps.google.com/?cid=123456789012345",
        )
        html = MOD.render(ig, PORTADA)
        MOD.validar(html, ig)  # no debe lanzar
        for campo in ("notasVisita", "resumenElementos", "vinculos",
                      "otraInfo", "urlGoogleMaps"):
            self.assertNotIn(ig[campo][:40], html, f"{campo} se ha filtrado")

    def test_los_rellenos_de_la_bd_no_se_publican(self):
        """Misma regla que la App: "No disponible" y "No existe" no informan."""
        html = MOD.render(
            iglesia(estadoConservacion="No disponible",
                    datacion="No existe",
                    tipoConstruccion="  no DISPONIBLE  "),
            PORTADA)
        self.assertNotIn("No disponible", html)
        self.assertNotIn("No existe", html)
        self.assertNotIn("<dt>Estado</dt>", html)
        self.assertNotIn("<dt>Datación</dt>", html)
        self.assertNotIn("<dt>Tipo</dt>", html)

    def test_un_valor_real_si_se_publica(self):
        html = MOD.render(iglesia(estadoConservacion="Ruinoso"), PORTADA)
        self.assertIn("<dt>Estado</dt>", html)
        self.assertIn("Ruinoso", html)

    def test_la_galeria_no_aparece_solo_la_portada(self):
        html = MOD.render(iglesia(), PORTADA)
        self.assertEqual(html.count(PORTADA), 2)  # og:image + <img>


class PreviewTest(unittest.TestCase):
    def test_usa_siglo_y_no_la_datacion_larga(self):
        ig = iglesia()
        d = MOD.descripcion(ig)
        self.assertIn("Siglo XI", d)
        self.assertNotIn(ig["datacion"][:40], d)

    def test_cabe_en_lo_que_muestra_whatsapp(self):
        d = MOD.descripcion(iglesia())
        self.assertLess(len(d), 120, f"preview de {len(d)} caracteres: se truncaria")

    def test_sin_siglo_no_inventa_nada(self):
        d = MOD.descripcion(iglesia(siglo=None))
        self.assertNotIn("Siglo", d)
        self.assertIn("Girona", d)


class CasosLimiteTest(unittest.TestCase):
    def test_sin_tipoConstruccion_la_ficha_sigue_siendo_valida(self):
        ig = iglesia(tipoConstruccion=None)
        html = MOD.render(ig, PORTADA)
        MOD.validar(html, ig)
        self.assertNotIn("<dt>Tipo</dt>", html)

    def test_sin_estadoConservacion_no_deja_fila_vacia(self):
        html = MOD.render(iglesia(estadoConservacion=None), PORTADA)
        self.assertNotIn("<dt>Estado</dt>", html)

    def test_comillas_y_acentos_van_escapados(self):
        html = MOD.render(iglesia(nombre='Iglesia "de la" Asunción & Cía'), PORTADA)
        self.assertIn("&quot;de la&quot;", html)
        self.assertIn("&amp;", html)
        self.assertNotIn('content="Iglesia "de la"', html)


class IdentidadTest(unittest.TestCase):
    """La ficha usa la identidad común de la web (_src/marca.py y marca.css)."""

    def test_estilo_comun_con_la_portada(self):
        self.assertTrue(MOD.CSS.startswith(MOD.marca.css()))
        self.assertIn("--pergamino", MOD.CSS)

    def test_insignias_oficiales_con_rutas_absolutas(self):
        html = MOD.render(iglesia(), PORTADA)
        self.assertIn('src="/img/tiendas/app-store-es.svg"', html)
        self.assertIn('src="/img/tiendas/google-play-es.png"', html)
        self.assertIn(f'src="/{MOD.marca.LOGO}"', html)

    def test_google_play_conserva_el_referrer_de_la_iglesia(self):
        html = MOD.render(iglesia(), PORTADA)
        self.assertIn("id=com.romanicomaps&amp;referrer=idCode%3D182", html)

    def test_cifra_del_catalogo_comun(self):
        html = MOD.render(iglesia(), PORTADA)
        self.assertIn(MOD.marca.CIFRA_IGLESIAS, html)
        self.assertNotIn("6.500", html)

    def test_smart_app_banner_intacto(self):
        html = MOD.render(iglesia(), PORTADA)
        self.assertIn('name="apple-itunes-app" content="app-id=6759716898, app-argument=', html)


class SlugTest(unittest.TestCase):
    def test_quita_acentos_y_normaliza(self):
        self.assertEqual(
            MOD.slug("Girona-Sant Esteve d'en Bas-Iglesia de Sant Esteve"),
            "girona-sant-esteve-d-en-bas-iglesia-de-sant-esteve")

    def test_es_estable_entre_pasadas(self):
        t = "Barcelona-Sant Julià de Vilatorta-Iglesia de Sant Julià"
        self.assertEqual(MOD.slug(t), MOD.slug(t))

    def test_idUnico_vacio_no_rompe(self):
        self.assertEqual(MOD.slug(""), "")


if __name__ == "__main__":
    unittest.main()
