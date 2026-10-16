#!/usr/bin/env python3
"""Genera de forma incremental las portadas permanentes de la ficha web.

La identidad de una portada se obtiene de los metadatos estables del attachment
de Airtable incluidos en el export. Si esa identidad ya figura en el manifiesto,
no se descarga la imagen. Solo las altas y sustituciones hacen trabajo de red.

Las nuevas imágenes se publican en rutas versionadas por identidad. Esto hace
seguro servirlas con ``Cache-Control: immutable`` y evita que una portada
reemplazada quede un año en la caché de navegadores o crawlers sociales.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import io
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageOps

# Vive en el repo web (romanicomaps-web/_fichas), junto a su manifiesto.
RAIZ = Path(__file__).resolve().parent
EXPORT_PREDETERMINADO = RAIZ.parent.parent / "romanico_maps/assets/database/iglesias_db.json"
MANIFIESTO_PREDETERMINADO = RAIZ / "estado/manifiesto_portadas.json"
# SUPABASE_URL (no es secreto) sale del entorno o del .env de la app.
ENV_APP = RAIZ.parent.parent / "romanico_maps/.env"
BUCKET = "fichas-web"
PREFIJO = "portadas"
LADO_MAYOR = 850
CALIDAD = 82
REINTENTOS_RED = 4
TRABAJADORES_PREDETERMINADOS = 6
CLAVE_LOCAL = Path.home() / ".config/romanico/web.env"


@dataclass(frozen=True)
class PortadaPendiente:
    iglesia: dict[str, Any]
    fingerprint: str
    estado: str


def leer_clave_local() -> str:
    if not CLAVE_LOCAL.exists():
        return ""
    for linea in CLAVE_LOCAL.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea.startswith("SUPABASE_SERVICE_ROLE_KEY="):
            return linea.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def cargar_entorno() -> tuple[str, str]:
    env: dict[str, str] = {}
    if os.environ.get("SUPABASE_URL"):
        env["SUPABASE_URL"] = os.environ["SUPABASE_URL"]
    elif ENV_APP.exists():
        for linea in ENV_APP.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, valor = linea.split("=", 1)
                env[clave.strip()] = valor.strip().strip('"').strip("'")

    service = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not service:
        service = leer_clave_local()
    if not service:
        raise RuntimeError(
            "No encuentro SUPABASE_SERVICE_ROLE_KEY en el entorno ni en "
            f"{CLAVE_LOCAL}. No debe guardarse dentro del repositorio."
        )
    try:
        base = env["SUPABASE_URL"].rstrip("/")
    except KeyError as exc:
        raise RuntimeError(
            f"Falta SUPABASE_URL (en el entorno o en {ENV_APP})"
        ) from exc
    return base, service


def cargar_json(ruta: Path, predeterminado: Any) -> Any:
    if not ruta.exists():
        return predeterminado
    return json.loads(ruta.read_text(encoding="utf-8"))


def fingerprint_origen(iglesia: dict[str, Any]) -> str:
    """Huella estable del attachment, independiente de su URL firmada."""
    attachment_id = str(iglesia.get("image01AttachmentId") or "").strip()
    if not attachment_id:
        raise ValueError(
            f"idCode {iglesia.get('idCode')}: Image01 no tiene attachment ID"
        )
    identidad = {
        "id": attachment_id,
        "filename": iglesia.get("image01Filename"),
        "size": iglesia.get("image01Size"),
        "type": iglesia.get("image01MimeType"),
        "width": iglesia.get("image01Width"),
        "height": iglesia.get("image01Height"),
    }
    serializado = json.dumps(
        identidad, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()[:16]


def obtener_activas(export: dict[str, Any]) -> list[dict[str, Any]]:
    activas = [
        iglesia
        for iglesia in export.get("iglesias", [])
        if iglesia.get("activa") == "Sí" and iglesia.get("image01")
    ]
    vistos: set[str] = set()
    duplicados: set[str] = set()
    for iglesia in activas:
        codigo = str(iglesia.get("idCode"))
        if codigo in vistos:
            duplicados.add(codigo)
        vistos.add(codigo)
        fingerprint_origen(iglesia)
    if duplicados:
        raise ValueError(f"idCode duplicados en iglesias activas: {sorted(duplicados)[:10]}")
    return activas


def clasificar(
    iglesias: list[dict[str, Any]], manifiesto: dict[str, Any]
) -> tuple[list[PortadaPendiente], dict[str, Any], int, list[dict[str, Any]]]:
    """Clasifica sin red: pendientes, manifiesto base, iguales y obsoletas.

    Los registros creados por la primera versión no tienen ``sourceFingerprint``.
    Se migran adoptando la identidad actual sin descargar. Esto evita repetir
    miles de descargas para las portadas que ya se publicaron correctamente.
    """
    salida: dict[str, Any] = {}
    pendientes: list[PortadaPendiente] = []
    iguales = 0

    esperados = {str(i["idCode"]) for i in iglesias}
    obsoletas = [entrada for codigo, entrada in manifiesto.items() if codigo not in esperados]

    for iglesia in iglesias:
        codigo = str(iglesia["idCode"])
        fingerprint = fingerprint_origen(iglesia)
        previa = manifiesto.get(codigo)

        if previa and previa.get("sourceFingerprint") == fingerprint:
            salida[codigo] = previa
            iguales += 1
            continue

        if previa and not previa.get("sourceFingerprint") and previa.get("url"):
            migrada = dict(previa)
            migrada.update(metadatos_origen(iglesia, fingerprint))
            salida[codigo] = migrada
            iguales += 1
            continue

        pendientes.append(
            PortadaPendiente(
                iglesia=iglesia,
                fingerprint=fingerprint,
                estado="cambio" if previa else "alta",
            )
        )

    return pendientes, salida, iguales, obsoletas


def metadatos_origen(iglesia: dict[str, Any], fingerprint: str) -> dict[str, Any]:
    return {
        "sourceAttachmentId": iglesia["image01AttachmentId"],
        "sourceFingerprint": fingerprint,
        "sourceFilename": iglesia.get("image01Filename"),
        "sourceSize": iglesia.get("image01Size"),
    }


def con_reintentos(accion, descripcion: str):
    ultimo: Exception | None = None
    for intento in range(1, REINTENTOS_RED + 1):
        try:
            return accion()
        except requests.RequestException as exc:
            ultimo = exc
        except RuntimeError as exc:
            ultimo = exc
            if "HTTP 4" in str(exc) and "HTTP 429" not in str(exc):
                break
        if intento < REINTENTOS_RED:
            time.sleep(2 ** intento)
    raise RuntimeError(f"{descripcion}: {ultimo!r}")


def descargar(url: str) -> bytes:
    def intento() -> bytes:
        respuesta = requests.get(url, timeout=(15, 90))
        if respuesta.status_code != 200:
            raise RuntimeError(f"HTTP {respuesta.status_code} al descargar")
        if not respuesta.content:
            raise RuntimeError("respuesta vacía al descargar")
        return respuesta.content

    return con_reintentos(intento, "descarga fallida")


def normalizar(binario: bytes) -> tuple[bytes, tuple[int, int], tuple[int, int]]:
    with Image.open(io.BytesIO(binario)) as original_imagen:
        original_imagen.load()
        original = original_imagen.size
        imagen = ImageOps.exif_transpose(original_imagen).convert("RGB")
    ancho, alto = imagen.size
    factor = LADO_MAYOR / max(ancho, alto)
    if abs(factor - 1.0) > 0.01:
        imagen = imagen.resize(
            (max(1, round(ancho * factor)), max(1, round(alto * factor))),
            Image.Resampling.LANCZOS,
        )
    buffer = io.BytesIO()
    imagen.save(buffer, "JPEG", quality=CALIDAD, optimize=True, progressive=True)
    return buffer.getvalue(), original, imagen.size


def subir(base: str, service: str, ruta: str, jpeg: bytes) -> str:
    destino = f"{base}/storage/v1/object/{BUCKET}/{ruta}"

    def intento() -> None:
        respuesta = requests.post(
            destino,
            headers={
                "Authorization": f"Bearer {service}",
                "apikey": service,
                "Content-Type": "image/jpeg",
                "x-upsert": "true",
                "cache-control": "public, max-age=31536000, immutable",
            },
            data=jpeg,
            timeout=(15, 120),
        )
        if respuesta.status_code not in (200, 201):
            raise RuntimeError(
                f"HTTP {respuesta.status_code} al subir: {respuesta.text[:150]}"
            )

    con_reintentos(intento, "subida fallida")
    return f"{base}/storage/v1/object/public/{BUCKET}/{ruta}"


def procesar_una(base: str, service: str, pendiente: PortadaPendiente) -> tuple[str, dict[str, Any]]:
    iglesia = pendiente.iglesia
    codigo = str(iglesia["idCode"])
    original = descargar(str(iglesia["image01"]))
    jpeg, tam_original, tam_final = normalizar(original)
    hash_contenido = hashlib.sha256(jpeg).hexdigest()[:16]
    ruta = f"{PREFIJO}/{codigo}-{pendiente.fingerprint}.jpg"
    url = subir(base, service, ruta, jpeg)
    entrada = {
        "url": url,
        "objectPath": ruta,
        "hash": hash_contenido,
        "bytes": len(jpeg),
        "origen": f"{tam_original[0]}x{tam_original[1]}",
        "final": f"{tam_final[0]}x{tam_final[1]}",
        "upscaled": max(tam_original) < LADO_MAYOR,
        **metadatos_origen(iglesia, pendiente.fingerprint),
    }
    return codigo, entrada


def guardar_atomico(ruta: Path, datos: dict[str, Any]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(prefix=f".{ruta.name}.", dir=ruta.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=1, sort_keys=True)
            archivo.write("\n")
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, ruta)
    except BaseException:
        try:
            os.unlink(temporal)
        except FileNotFoundError:
            pass
        raise


def validar_manifiesto(
    iglesias: list[dict[str, Any]], manifiesto: dict[str, Any]
) -> None:
    esperados = {str(i["idCode"]): fingerprint_origen(i) for i in iglesias}
    actuales = set(manifiesto)
    if actuales != set(esperados):
        raise RuntimeError(
            f"manifiesto inconsistente: faltan {sorted(set(esperados)-actuales)[:10]}, "
            f"sobran {sorted(actuales-set(esperados))[:10]}"
        )
    obligatorios = {"url", "bytes", "hash", "sourceFingerprint", "sourceAttachmentId"}
    for codigo, fingerprint in esperados.items():
        entrada = manifiesto[codigo]
        faltan = obligatorios - set(entrada)
        if faltan:
            raise RuntimeError(f"portada {codigo}: faltan campos {sorted(faltan)}")
        if entrada["sourceFingerprint"] != fingerprint:
            raise RuntimeError(f"portada {codigo}: identidad de origen desactualizada")


def main() -> None:
    parser = argparse.ArgumentParser(description="Portadas incrementales de ficha web")
    parser.add_argument("--export", type=Path, default=EXPORT_PREDETERMINADO)
    parser.add_argument("--manifest", type=Path, default=MANIFIESTO_PREDETERMINADO)
    parser.add_argument("--output-manifest", type=Path)
    parser.add_argument("--workers", type=int, default=TRABAJADORES_PREDETERMINADOS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    destino = args.output_manifest or args.manifest
    export = cargar_json(args.export, {})
    iglesias = obtener_activas(export)
    manifiesto_previo = cargar_json(args.manifest, {})
    pendientes, nuevo, iguales, obsoletas = clasificar(iglesias, manifiesto_previo)

    altas = sum(p.estado == "alta" for p in pendientes)
    cambios = sum(p.estado == "cambio" for p in pendientes)
    migradas = sum(
        1
        for codigo, entrada in nuevo.items()
        if codigo in manifiesto_previo
        and not manifiesto_previo[codigo].get("sourceFingerprint")
        and entrada.get("sourceFingerprint")
    )
    print(
        f"Export {export.get('exportDate', '?')} · {len(iglesias)} activas con portada\n"
        f"Sin cambios: {iguales} ({migradas} manifiestos legacy adoptados) · "
        f"altas: {altas} · cambios: {cambios} · bajas: {len(obsoletas)}"
    )

    if args.dry_run:
        print(f"DRY-RUN: se descargarían y subirían {len(pendientes)} portadas.")
        return

    base, service = cargar_entorno() if pendientes else ("", "")
    fallos: list[str] = []
    if pendientes:
        trabajadores = max(1, min(args.workers, 12))
        with concurrent.futures.ThreadPoolExecutor(max_workers=trabajadores) as executor:
            futuros = {
                executor.submit(procesar_una, base, service, pendiente): pendiente
                for pendiente in pendientes
            }
            completadas = 0
            for futuro in concurrent.futures.as_completed(futuros):
                pendiente = futuros[futuro]
                try:
                    codigo, entrada = futuro.result()
                    nuevo[codigo] = entrada
                except Exception as exc:
                    fallos.append(f"{pendiente.iglesia.get('idCode')}: {exc}")
                completadas += 1
                if completadas % 25 == 0 or completadas == len(pendientes):
                    print(
                        f"  {completadas}/{len(pendientes)} procesadas · "
                        f"fallos {len(fallos)}"
                    )

    if fallos:
        for fallo in fallos[:25]:
            print(f"FALLO {fallo}", file=sys.stderr)
        raise RuntimeError(
            f"{len(fallos)} portadas fallaron; el manifiesto no se ha modificado"
        )

    validar_manifiesto(iglesias, nuevo)
    guardar_atomico(destino, nuevo)
    ocupacion = sum(int(e["bytes"]) for e in nuevo.values()) / 1024 / 1024
    print(
        f"Manifiesto validado: {len(nuevo)} portadas, {ocupacion:.1f} MB.\n"
        f"Escrito atómicamente en {destino}"
    )
    if obsoletas:
        print(
            f"Aviso: {len(obsoletas)} objetos remotos antiguos quedan como huérfanos; "
            "no forman parte del manifiesto nuevo."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"STOPPER: {exc}", file=sys.stderr)
        raise SystemExit(1)
