import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "generar_portadas_web.py"
SPEC = importlib.util.spec_from_file_location("generar_portadas_web", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def iglesia(codigo=182, attachment="attOriginal", size=100, url="https://signed/one"):
    return {
        "id": f"rec{codigo}",
        "idCode": codigo,
        "activa": "Sí",
        "image01": url,
        "image01AttachmentId": attachment,
        "image01Filename": "portada.jpg",
        "image01Size": size,
        "image01MimeType": "image/jpeg",
        "image01Width": 1200,
        "image01Height": 800,
    }


def entrada(iglesia_actual):
    fingerprint = MOD.fingerprint_origen(iglesia_actual)
    return {
        "url": f"https://storage/{iglesia_actual['idCode']}-{fingerprint}.jpg",
        "bytes": 123,
        "hash": "contenido",
        "sourceAttachmentId": iglesia_actual["image01AttachmentId"],
        "sourceFingerprint": fingerprint,
    }


class FingerprintTest(unittest.TestCase):
    def test_la_url_firmada_no_cambia_la_identidad(self):
        primera = iglesia(url="https://signed/one")
        segunda = iglesia(url="https://signed/two")
        self.assertEqual(
            MOD.fingerprint_origen(primera), MOD.fingerprint_origen(segunda)
        )

    def test_reemplazar_attachment_si_cambia_la_identidad(self):
        self.assertNotEqual(
            MOD.fingerprint_origen(iglesia(attachment="attOne")),
            MOD.fingerprint_origen(iglesia(attachment="attTwo")),
        )


class ClasificacionTest(unittest.TestCase):
    def test_sin_cambios_no_hay_descargas_pendientes(self):
        actual = iglesia()
        pendientes, nuevo, iguales, obsoletas = MOD.clasificar(
            [actual], {"182": entrada(actual)}
        )
        self.assertEqual(pendientes, [])
        self.assertEqual(iguales, 1)
        self.assertEqual(set(nuevo), {"182"})
        self.assertEqual(obsoletas, [])

    def test_alta_y_cambio_son_los_unicos_pendientes(self):
        anterior = iglesia(182, attachment="attAnterior")
        cambio = iglesia(182, attachment="attNueva")
        alta = iglesia(183, attachment="attAlta")
        pendientes, _, iguales, _ = MOD.clasificar(
            [cambio, alta], {"182": entrada(anterior)}
        )
        self.assertEqual(iguales, 0)
        self.assertEqual(
            {(p.iglesia["idCode"], p.estado) for p in pendientes},
            {(182, "cambio"), (183, "alta")},
        )

    def test_manifiesto_legacy_se_adopta_sin_descargar(self):
        actual = iglesia()
        legacy = {"url": "https://storage/182.jpg", "bytes": 123, "hash": "old"}
        pendientes, nuevo, iguales, _ = MOD.clasificar([actual], {"182": legacy})
        self.assertEqual(pendientes, [])
        self.assertEqual(iguales, 1)
        self.assertEqual(
            nuevo["182"]["sourceFingerprint"], MOD.fingerprint_origen(actual)
        )

    def test_las_bajas_desaparecen_del_manifiesto_nuevo(self):
        actual = iglesia()
        vieja = iglesia(999, attachment="attVieja")
        _, nuevo, _, obsoletas = MOD.clasificar(
            [actual], {"182": entrada(actual), "999": entrada(vieja)}
        )
        self.assertEqual(set(nuevo), {"182"})
        self.assertEqual(len(obsoletas), 1)


class ValidacionTest(unittest.TestCase):
    def test_exige_el_conjunto_exacto_de_ids(self):
        actual = iglesia()
        with self.assertRaisesRegex(RuntimeError, "manifiesto inconsistente"):
            MOD.validar_manifiesto([actual], {})

    def test_escritura_atomica_produce_json_completo(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "manifest.json"
            MOD.guardar_atomico(destino, {"182": entrada(iglesia())})
            cargado = MOD.cargar_json(destino, {})
            self.assertEqual(set(cargado), {"182"})
            self.assertEqual(list(Path(tmp).iterdir()), [destino])


if __name__ == "__main__":
    unittest.main()
