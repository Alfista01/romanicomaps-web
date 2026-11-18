#!/usr/bin/env python3
"""Ficheros de sincronización de la app (romanicomaps.com/sync/), 2026-11-18.

La app (desde la 1.7.16) ya no pregunta a Airtable por los cambios del
catálogo: se baja de la web los cambios del día que genera esta tarea cada
noche, con el mismo export que usan las fichas. Las versiones anteriores siguen
sincronizando con airtable-proxy, que no cambia.

Cada pasada compara el export de hoy con el anterior (huella de cada iglesia en
`_fichas/estado/sync_huellas.json`) y publica:

  sync/cambios-<AAAAMMDDTHHMMSSZ>.json
      {"desde", "hasta", "iglesias": [registros en el formato de la BD de la
       app], "bajas": [ids que ya no están activos]}
  sync/manifiesto.json
      {"version": 1, "generado", "dias": [{"fichero", "desde", "hasta",
       "cambiados", "bajas"}, ...]}  (los últimos DIAS_CONSERVADOS)

Las iglesias nunca se borran en Airtable, solo se desactivan (convención de
Antonio, 2026-11-18): una desactivada deja de salir en el export y llega como
baja. La URL firmada de la portada (`image01`) cambia en cada export, así que
no cuenta para la huella; un cambio de foto se detecta por el id de adjunto.

    python3 _fichas/generar_sync.py --export export.json --salida sync \\
        --huellas _fichas/estado/sync_huellas.json
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

DIAS_CONSERVADOS = 45
VOLATILES = {"image01"}  # URL firmada de Airtable: cambia en cada export


def huella(registro: dict) -> str:
    estable = {k: v for k, v in registro.items() if k not in VOLATILES}
    texto = json.dumps(estable, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def compacta(fecha_iso: str) -> str:
    f = dt.datetime.fromisoformat(fecha_iso.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    return f.strftime("%Y%m%dT%H%M%SZ")


def iso(fecha_iso: str) -> str:
    f = dt.datetime.fromisoformat(fecha_iso.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    return f.strftime("%Y-%m-%dT%H:%M:%SZ")


def calcular(export: dict, anterior: dict | None) -> tuple[dict, dict | None]:
    """Devuelve (huellas nuevas, fichero del día o None si no hay anterior)."""
    hasta = iso(export["exportDate"])
    actuales = {r["id"]: r for r in export["iglesias"]}
    huellas = {"generado": hasta, "huellas": {i: huella(r) for i, r in actuales.items()}}
    if not anterior:
        return huellas, None
    previas = anterior.get("huellas", {})
    cambiadas = [r for i, r in actuales.items() if previas.get(i) != huellas["huellas"][i]]
    bajas = sorted(set(previas) - set(actuales))
    dia = {"desde": anterior["generado"], "hasta": hasta,
           "iglesias": sorted(cambiadas, key=lambda r: r["id"]), "bajas": bajas}
    return huellas, dia


def publicar(dia: dict | None, huellas: dict, salida: Path, ruta_huellas: Path) -> str:
    salida.mkdir(parents=True, exist_ok=True)
    ruta_manifiesto = salida / "manifiesto.json"
    manifiesto = (json.loads(ruta_manifiesto.read_text(encoding="utf-8"))
                  if ruta_manifiesto.exists() else {"version": 1, "dias": []})
    if dia is not None:
        nombre = f"cambios-{compacta(dia['hasta'])}.json"
        (salida / nombre).write_text(json.dumps(dia, ensure_ascii=False, separators=(",", ":")),
                                     encoding="utf-8")
        manifiesto["dias"] = [d for d in manifiesto["dias"] if d["fichero"] != nombre]
        manifiesto["dias"].append({"fichero": nombre, "desde": dia["desde"], "hasta": dia["hasta"],
                                   "cambiados": len(dia["iglesias"]), "bajas": len(dia["bajas"])})
    manifiesto["dias"].sort(key=lambda d: d["hasta"])
    limite = (dt.datetime.fromisoformat(huellas["generado"].replace("Z", "+00:00"))
              - dt.timedelta(days=DIAS_CONSERVADOS))
    vigentes = []
    for d in manifiesto["dias"]:
        if dt.datetime.fromisoformat(d["hasta"].replace("Z", "+00:00")) < limite:
            (salida / d["fichero"]).unlink(missing_ok=True)
        else:
            vigentes.append(d)
    manifiesto["dias"] = vigentes
    manifiesto["generado"] = huellas["generado"]
    ruta_manifiesto.write_text(json.dumps(manifiesto, ensure_ascii=False, indent=1), encoding="utf-8")
    ruta_huellas.parent.mkdir(parents=True, exist_ok=True)
    ruta_huellas.write_text(json.dumps(huellas, ensure_ascii=False, indent=0, sort_keys=True),
                            encoding="utf-8")
    if dia is None:
        return "sync: primera pasada (solo huellas, sin fichero de cambios)"
    return f"sync: {len(dia['iglesias'])} cambiadas · {len(dia['bajas'])} bajas"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True, type=Path)
    ap.add_argument("--salida", required=True, type=Path)
    ap.add_argument("--huellas", required=True, type=Path)
    a = ap.parse_args()
    export = json.loads(a.export.read_text(encoding="utf-8"))
    if not export.get("iglesias") or not export.get("exportDate"):
        raise SystemExit("STOPPER: export sin iglesias o sin exportDate")
    anterior = json.loads(a.huellas.read_text(encoding="utf-8")) if a.huellas.exists() else None
    # Salvaguarda: si desaparece más del 10 % del catálogo, algo ha ido mal en el
    # export; no se publica nada (las apps seguirían borrando iglesias).
    if anterior and len(export["iglesias"]) < 0.9 * len(anterior.get("huellas", {})):
        raise SystemExit("STOPPER: el export tiene más de un 10 % menos de iglesias que el anterior")
    huellas, dia = calcular(export, anterior)
    print(publicar(dia, huellas, a.salida, a.huellas))


if __name__ == "__main__":
    main()
