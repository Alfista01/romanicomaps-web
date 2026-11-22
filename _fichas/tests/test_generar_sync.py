"""Pruebas de los ficheros de sincronización de la app (sync/)."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "generar_sync.py"
SPEC = importlib.util.spec_from_file_location("generar_sync", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def ig(i, nombre="Iglesia", url="https://v5.airtableusercontent.com/x", adj="att1"):
    return {"id": i, "nombre": nombre, "activa": "Sí", "image01": url, "image01AttachmentId": adj}


def export(fecha, *iglesias):
    return {"exportDate": fecha, "iglesias": list(iglesias)}


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.salida = self.tmp / "sync"
        self.huellas = self.tmp / "huellas.json"

    def pasada(self, exp):
        anterior = json.loads(self.huellas.read_text()) if self.huellas.exists() else None
        h, dia = MOD.calcular(exp, anterior)
        MOD.publicar(dia, h, self.salida, self.huellas)
        return dia

    def test_primera_pasada_solo_guarda_huellas(self):
        self.assertIsNone(self.pasada(export("2026-11-18T22:40:00Z", ig("a"), ig("b"))))
        m = json.loads((self.salida / "manifiesto.json").read_text())
        self.assertEqual(m["dias"], [])
        self.assertEqual(m["generado"], "2026-11-18T22:40:00Z")

    def test_cambio_alta_y_baja(self):
        self.pasada(export("2026-11-18T22:40:00Z", ig("a"), ig("b"), ig("c")))
        dia = self.pasada(export("2026-11-19T22:40:00Z", ig("a"), ig("b", nombre="Otra"), ig("d")))
        self.assertEqual([r["id"] for r in dia["iglesias"]], ["b", "d"])
        self.assertEqual(dia["bajas"], ["c"])
        self.assertEqual((dia["desde"], dia["hasta"]), ("2026-11-18T22:40:00Z", "2026-11-19T22:40:00Z"))
        m = json.loads((self.salida / "manifiesto.json").read_text())
        self.assertEqual(len(m["dias"]), 1)
        self.assertTrue((self.salida / m["dias"][0]["fichero"]).exists())

    def test_la_url_firmada_no_cuenta_pero_el_adjunto_si(self):
        self.pasada(export("2026-11-18T22:40:00Z", ig("a", url="u1"), ig("b", url="u1")))
        dia = self.pasada(export("2026-11-19T22:40:00Z", ig("a", url="u2"), ig("b", url="u2", adj="att2")))
        self.assertEqual([r["id"] for r in dia["iglesias"]], ["b"])

    def test_sin_cambios_publica_un_dia_vacio(self):
        self.pasada(export("2026-11-18T22:40:00Z", ig("a")))
        dia = self.pasada(export("2026-11-19T22:40:00Z", ig("a")))
        self.assertEqual((dia["iglesias"], dia["bajas"]), ([], []))

    def test_conserva_solo_los_ultimos_dias(self):
        self.pasada(export("2026-09-01T22:40:00Z", ig("a")))
        self.pasada(export("2026-09-02T22:40:00Z", ig("a", nombre="x")))
        self.pasada(export("2026-11-19T22:40:00Z", ig("a", nombre="y")))
        m = json.loads((self.salida / "manifiesto.json").read_text())
        self.assertEqual([d["hasta"] for d in m["dias"]], ["2026-11-19T22:40:00Z"])
        self.assertEqual(len(list(self.salida.glob("cambios-*.json"))), 1)



class IdiomasTest(unittest.TestCase):
    """sync/idiomas.json: idiomas de las fichas traducidas (tabla IDIOMAS)."""

    def test_publica_y_no_reescribe_si_no_cambia(self):
        with tempfile.TemporaryDirectory() as d:
            salida = Path(d)
            idiomas = {"pt": {"boton": "PT", "nombre": "Português"}}
            self.assertIn("publicados", MOD.publicar_idiomas(idiomas, salida))
            self.assertEqual(json.loads((salida / "idiomas.json").read_text()), idiomas)
            self.assertIn("sin cambios", MOD.publicar_idiomas(idiomas, salida))

    def test_sin_idiomas_publica_vacio(self):
        with tempfile.TemporaryDirectory() as d:
            MOD.publicar_idiomas({}, Path(d))
            self.assertEqual(json.loads((Path(d) / "idiomas.json").read_text()), {})


if __name__ == "__main__":
    unittest.main()
