#!/usr/bin/env python3
"""B4.2 - Fichas web publicas de Romanico Maps.

Genera una pagina estatica por iglesia activa a partir del export y del
manifiesto de portadas. Es un generador SEPARADO de _build_site.py (el del
repo web, que hace portada y paginas legales): escriben en directorios
disjuntos y este solo toca /i/.

CONTRATO (B4.0, test/public_ficha_contract_test.dart): la pagina muestra
EXACTAMENTE los 7 campos que ve un usuario anonimo en la App. Nada de notas de
visita, resumen, vinculos, Google Maps, galeria, comentarios ni valoraciones.
Unica ampliacion (decision de Antonio, 2026-10-08): una linea "Fuente principal" con el
enlace al PDF de romanicodigital.com (campo PDF de Airtable), que cita el
origen de los datos. Solo se publica si la URL es de romanicodigital.com.

INDEXACION POR TANDAS (decision de Antonio, 2026-10-08; sustituye al noindex
obligatorio de B4.2). Las fichas existen para compartir desde la App; si
alguien llega por buscador, es para descargarla. Se abren a Google por tandas
para no arriesgar el dominio entero de golpe:
  - _fichas/estado/indexacion.json guarda el limite de la tanda y la lista de
    idCodes ya abiertos. Una ficha abierta no se vuelve a cerrar mientras siga
    activa. Los huecos se rellenan con las fichas mas completas.
  - Tanda 1: "limite": 1000. Tanda 2 (todas): "limite": null.
  - Las abiertas llevan "index, follow" y van a /i/sitemap.xml; el resto
    sigue con "noindex, nofollow". `validar()` exige la etiqueta correcta.
El enriquecimiento para buscadores es invisible (meta description y datos
estructurados schema.org) y solo describe lo que la pagina ya muestra.
Importante: el robots.txt debe seguir permitiendo el rastreo. Un Disallow
impediria a Google LEER el noindex, y acabaria indexando la URL a ciegas.

Uso:
    python3 _fichas/generar_fichas_web.py --muestra [idCode]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# Vive en el repo web (romanicomaps-web/_fichas). El estado (portadas, alias y
# tandas de indexación) se guarda junto a las fichas que genera: se publican
# siempre en el mismo commit. El export de Airtable lo produce el exportador
# de la app (scripts/export_airtable_to_json.dart) y se pasa con --export.
RAIZ = Path(__file__).resolve().parent
WEB = RAIZ.parent
EXPORT = WEB.parent / "romanico_maps/assets/database/iglesias_db.json"
MANIFIESTO = RAIZ / "estado/manifiesto_portadas.json"
SALIDA_MUESTRA = RAIZ / "muestra"
ALIAS = RAIZ / "estado/alias_slugs.json"
INDEXACION = RAIZ / "estado/indexacion.json"
INDEXACION_INICIAL = {"limite": 1000, "indexadas": []}
DESTINO_WEB = WEB / "i"

# Identidad visual COMPARTIDA con la portada: colores, tipografías, logo,
# insignias de las tiendas y cifra del catálogo viven en _src/marca.py y
# _src/marca.css (los usa también _build_site.py). Si cambia el estilo de la
# web, las fichas lo heredan en la siguiente pasada; no se duplica aquí.
sys.path.insert(0, str(WEB / "_src"))
import marca  # noqa: E402

DOMINIO = marca.DOMINIO
APP_ID = marca.APP_ID
PLAY_URL = marca.PLAY_URL
APPSTORE_URL = marca.APP_URL

# Solo lo propio de la ficha; lo común llega de marca.css (va delante).
CSS_FICHA = """
.env{max-width:760px;margin:0 auto;padding:0 20px}
.cabecera{border-bottom:1px solid var(--linea);background:var(--pergamino)}
.barra{display:flex;align-items:center;justify-content:space-between;gap:14px;padding-top:12px;padding-bottom:12px}
.marca img{width:38px;height:38px}
.marca span{font-size:20px}
.barra .btn{min-height:44px;padding:0 18px;font-size:16px}
main.env{padding-top:30px;padding-bottom:20px}
.lugar{margin:0;font-family:"Marcellus SC",serif;letter-spacing:.16em;font-size:15px;color:var(--almagre)}
h1{margin:10px 0 0;font-size:clamp(32px,6vw,46px);line-height:1.1}
.foto{margin:28px auto 0;max-width:620px}
.foto .arco{aspect-ratio:4/3;border:8px solid var(--piedra);border-radius:50% 50% 0 0/34% 34% 0 0}
dl{margin:30px 0 0;border-top:1.5px solid var(--tinta)}
.fila{display:grid;grid-template-columns:170px 1fr;gap:16px;padding:14px 0;border-bottom:1px solid var(--linea)}
dt{font-family:"Marcellus SC",serif;letter-spacing:.14em;font-size:14px;color:var(--almagre);padding-top:3px}
dd{margin:0;font-size:19px;line-height:1.5}
.fuente{margin:14px 0 0;font-size:16px;font-style:italic;color:var(--tinta-2)}
.cta{margin:40px 0 0;padding:34px 22px;background:var(--pergamino-oscuro);text-align:center}
.cta h2{font-size:30px;line-height:1.1}
.cta h2 em{color:var(--almagre)}
.cta p{margin:10px auto 0;color:var(--tinta-2);font-size:18px;max-width:460px}
.cta .marco-tiendas{margin-top:22px}
.pie{margin-top:40px;padding:24px 0 36px;border-top:1px solid var(--linea);font-size:16px;color:var(--tinta-2)}
.pie nav{display:flex;flex-wrap:wrap;justify-content:center;gap:8px 20px}
.pie p{margin:12px 0 0;text-align:center;font-size:14px}
@media(max-width:560px){.fila{grid-template-columns:1fr;gap:3px}.marca span{font-size:18px}.barra .btn{padding:0 14px;font-size:15px}
  .cta{padding:28px 12px}.cta .insignia img{height:40px}}
@media(max-width:360px){.marca span{font-size:16px}.marca img{width:32px;height:32px}}
"""
CSS = marca.css() + CSS_FICHA

FUENTES = marca.FUENTES


def slug(texto: str) -> str:
    """idUnico -> slug SEO. La resolucion es SIEMPRE por idCode."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9]+", "-", t)
    return re.sub(r"-{2,}", "-", t).strip("-")[:80]


def esc(texto) -> str:
    return (str(texto or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def descripcion(ig: dict) -> str:
    """Linea del preview: compuesta SOLO con campos del contrato.

    Usa `siglo` (etiqueta corta: 'XII') y no `datacion`, que es un texto
    explicativo de 263 caracteres de media -- WhatsApp corta hacia los 120 y
    lo dejaria truncado a media frase. La pagina visible si muestra la
    datacion completa, igual que la App.
    """
    partes = [p for p in (ig.get("tipoConstruccion"),) if visible(p)]
    if ig.get("siglo"):
        partes.append(f"Siglo {ig['siglo']}")
    # La capitalizacion de `ciudad` se corrige en Airtable (tarea aparte), no
    # aqui: la web refleja la BD tal cual, sin capa correctora que la enmascare.
    lugar = ", ".join(p for p in (ig.get("ciudad"), ig.get("provincia")) if p)
    if lugar:
        partes.append(lugar)
    return " · ".join(partes)


ROBOTS_ABIERTA = "index, follow"
ROBOTS_CERRADA = "noindex, nofollow"


def url_canonica(ig: dict) -> str:
    s = slug(ig.get("idUnico", ""))
    codigo = ig["idCode"]
    return f"{DOMINIO}/i/{codigo}/{s}" if s else f"{DOMINIO}/i/{codigo}"


def pdf_fuente(ig: dict) -> str | None:
    """URL del PDF de romanicodigital.com, o None. Cualquier otro dominio se
    descarta: la linea "Fuente principal" solo cita romanicodigital.com; sin PDF no se genera."""
    url = ig.get("pdf")
    if not isinstance(url, str):
        return None
    url = url.strip()
    if re.match(r"^https://(www\.)?romanicodigital\.com/", url):
        return url
    return None


def datos_estructurados(ig: dict, canonica: str) -> str:
    """schema.org Church: invisible para el usuario y limitado a lo que la
    pagina ya muestra (nombre y lugar) mas las coordenadas del mapa."""
    datos = {"@context": "https://schema.org", "@type": "Church",
             "name": ig.get("nombre"), "url": canonica}
    direccion = {"@type": "PostalAddress", "addressCountry": "ES"}
    if ig.get("ciudad"):
        direccion["addressLocality"] = ig["ciudad"]
    if ig.get("provincia"):
        direccion["addressRegion"] = ig["provincia"]
    datos["address"] = direccion
    if isinstance(ig.get("lat"), (int, float)) and isinstance(ig.get("lon"), (int, float)):
        datos["geo"] = {"@type": "GeoCoordinates",
                        "latitude": ig["lat"], "longitude": ig["lon"]}
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    # Un "</" dentro del JSON cerraria el <script> antes de tiempo.
    return texto.replace("</", "<\\/")


def render(ig: dict, portada: str, css: str = "", indexable: bool = False) -> str:
    """css: ruta al CSS externo. Vacio = CSS embebido (modo muestra).
    indexable: True solo para las fichas de la tanda abierta a buscadores."""
    codigo = ig["idCode"]
    canonica = url_canonica(ig)
    robots = ROBOTS_ABIERTA if indexable else ROBOTS_CERRADA
    pdf = pdf_fuente(ig)
    fuente = (f'<p class="fuente">Fuente principal: <a href="{esc(pdf)}" rel="noopener" '
              f'target="_blank">ficha de Románico Digital (PDF)</a></p>'
              if pdf else "")
    lugar = ", ".join(p for p in (ig.get("ciudad"), ig.get("provincia")) if p)
    estilo = (f'<link rel="stylesheet" href="{css}">' if css
              else f"<style>{CSS}</style>")

    # B5 · deferred deep link (solo Android): Play conserva `referrer` y lo
    # entrega en el primer arranque, para aterrizar en ESTA iglesia en vez de
    # en el mapa. iOS no tiene equivalente, de ahi que su boton vaya limpio.
    play_url = f"{PLAY_URL}&referrer=idCode%3D{codigo}"
    filas = ""
    for etiqueta, valor in (("Tipo", ig.get("tipoConstruccion")),
                            ("Datación", ig.get("datacion")),
                            ("Estado", ig.get("estadoConservacion"))):
        if visible(valor):
            filas += (f'<div class="fila"><dt>{esc(etiqueta)}</dt>'
                      f"<dd>{esc(valor)}</dd></div>")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<!-- Indexacion por tandas (_fichas/estado/indexacion.json). El robots.txt debe
     seguir permitiendo el rastreo para que esta etiqueta pueda leerse. -->
<meta name="robots" content="{robots}">
<title>{esc(ig.get('nombre'))} · Románico Maps</title>
<meta name="description" content="{esc(descripcion(ig))}">
<link rel="canonical" href="{esc(canonica)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Románico Maps">
<meta property="og:locale" content="es_ES">
<meta property="og:title" content="{esc(ig.get('nombre'))}">
<meta property="og:description" content="{esc(descripcion(ig))}">
<meta property="og:image" content="{esc(portada)}">
<meta property="og:url" content="{esc(canonica)}">
<meta name="twitter:card" content="summary_large_image">
<!-- Smart App Banner: dentro de Safari el Universal Link no sale del
     navegador, asi que este es el unico camino a la app en iOS. -->
<meta name="apple-itunes-app" content="app-id={APP_ID}, app-argument={esc(canonica)}">
<script type="application/ld+json">{datos_estructurados(ig, canonica)}</script>
{FUENTES}
{estilo}
</head>
<body>
<header class="cabecera"><div class="env barra">
  <a class="marca" href="{DOMINIO}/"><img src="/{marca.LOGO}" alt="" width="38" height="38"><span>Románico Maps</span></a>
  <a class="btn btn--almagre" href="#descargar">Descargar</a>
</div></header>
<main class="env">
<p class="lugar">{esc(lugar)}</p>
<h1>{esc(ig.get('nombre'))}</h1>
<figure class="foto"><div class="arco"><img src="{esc(portada)}" alt="{esc(ig.get('nombre'))}"></div></figure>
<dl>{filas}</dl>
{fuente}
<section id="descargar" class="cta">
  <h2>Ver en <em>Románico Maps</em></h2>
  <p>Mapa, fotografías y ficha completa de {marca.CIFRA_IGLESIAS} iglesias románicas de la Península.</p>
{marca.insignias(raiz="/", play_url=play_url, sangria="  ")}
</section>
</main>
<footer class="pie"><div class="env">
  <nav aria-label="Románico Maps">
    <a href="{DOMINIO}/">Portada</a>
    <a href="{DOMINIO}/mapa-romanico-espana.html">Mapa del románico</a>
    <a href="{DOMINIO}/privacidad.html">Privacidad</a>
    <a href="{DOMINIO}/aviso-legal.html">Aviso legal</a>
  </nav>
  <p>© Románico Maps · romanicomaps.com</p>
</div></footer>
</body>
</html>"""


# Campos que NUNCA pueden aparecer en una ficha publica (contrato B4.0).
# No hace falta vigilarlos en tiempo de build: `render()` compone las filas
# desde una lista explicita de campos, asi que un campo no listado no puede
# salir. La garantia la sostienen los tests, no un guardian en el pipeline.

# Valores de relleno de la BD. La App los oculta (`_hasValidContent` en
# iglesia_ficha.dart) y la web hace lo mismo: una fila "Estado: No disponible"
# no informa de nada. No se reescribe el dato, simplemente no se imprime.
RELLENOS = ("no disponible", "no existe", "0")


def visible(valor) -> bool:
    """Replica `_hasValidContent` de la App: vacio o relleno = no se publica."""
    if not isinstance(valor, str):
        return False
    limpio = valor.strip()
    return bool(limpio) and limpio.lower() not in RELLENOS


def validar(html: str, ig: dict, indexable: bool = False) -> None:
    """Se niega a emitir una pagina cuya etiqueta robots no sea la que le toca:
    abierta solo si esta en la tanda; cerrada (noindex) en cualquier otro caso."""
    esperada = ROBOTS_ABIERTA if indexable else ROBOTS_CERRADA
    if f'<meta name="robots" content="{esperada}">' not in html:
        raise SystemExit(f"STOPPER {ig['idCode']}: etiqueta robots incorrecta "
                         f"(se esperaba '{esperada}').")


# ── Indexacion por tandas ───────────────────────────────────────────────────

# Campos de la ficha completa de la App. Solo sirven para MEDIR lo completa que
# esta una iglesia y decidir el orden de entrada en el buscador; ninguno se
# publica en la web (el contrato sigue siendo el de render()).
CAMPOS_COMPLETITUD = (
    "tipoConstruccion", "datacion", "siglo", "estadoConservacion",
    "resumenElementos", "notasVisita", "tipoPlanta", "materiales", "numNaves",
    "formaNaves", "tiposBoveda", "tipoCubierta", "numAbsides", "formaAbsides",
    "numAbsidiolos", "girola", "numTorres", "espadana", "cimborrio",
    "portadaRomanica", "portadaTransicion", "arquivoltas", "timpanos",
    "portico", "canecillos", "capitelesExt", "capitelesInt", "tiposArcos",
    "tiposSoportes", "tribuna", "triforio", "pilaBautismal", "pinturasMurales",
)


def completitud(ig: dict) -> int:
    """Numero de campos con contenido real, mas uno si cita su PDF fuente."""
    total = 0
    for campo in CAMPOS_COMPLETITUD:
        valor = ig.get(campo)
        if isinstance(valor, list):
            valor = ", ".join(str(v) for v in valor)
        if visible(valor):
            total += 1
    return total + (1 if pdf_fuente(ig) else 0)


def seleccionar_indexables(activas: list, estado: dict) -> list:
    """Lista ordenada de idCodes (str) abiertos a buscadores.

    - limite None: todas las activas (tanda final).
    - limite N: se conservan las ya abiertas que sigan activas (una ficha
      indexada no se cierra por un cambio de datos) y el hueco hasta N se
      rellena con las mas completas; a igualdad, la de idCode menor.
    """
    codigos = {str(i["idCode"]): i for i in activas}
    limite = estado.get("limite")
    if limite is None:
        return sorted(codigos, key=int)
    previas = [c for c in estado.get("indexadas", []) if c in codigos]
    restantes = sorted((c for c in codigos if c not in set(previas)),
                       key=lambda c: (-completitud(codigos[c]), int(c)))
    hueco = max(0, int(limite) - len(previas))
    return sorted(previas + restantes[:hueco], key=int)


def sitemap(urls: list) -> str:
    filas = "".join(f"<url><loc>{esc(u)}</loc></url>\n" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{filas}</urlset>\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="B4.2 · fichas web")
    ap.add_argument("--muestra", nargs="?", const="", metavar="IDCODE",
                    help="genera una sola ficha para revision visual")
    ap.add_argument("--completa", action="store_true",
                    help="genera las 4.359 fichas y publica en romanicomaps-web")
    ap.add_argument("--dry-run", action="store_true",
                    help="con --completa: genera y valida, pero NO publica")
    ap.add_argument("--export", type=Path, default=EXPORT,
                    help="export a usar (actualizar.sh pasa el de staging)")
    ap.add_argument("--manifest", type=Path, default=MANIFIESTO,
                    help="manifiesto de portadas de ESTA pasada")
    ap.add_argument("--salida", type=Path,
                    help="destino del arbol /i. Si se indica, NO publica: lo "
                         "deja ahi para que actualizar.sh lo mueva en su "
                         "commit atomico.")
    args = ap.parse_args()

    datos = json.loads(args.export.read_text())
    manifiesto = json.loads(args.manifest.read_text())
    activas = [i for i in datos["iglesias"]
               if i.get("activa") == "Sí" and i.get("image01")]
    estado_indexacion = (json.loads(INDEXACION.read_text())
                         if INDEXACION.exists() else dict(INDEXACION_INICIAL))
    indexables = seleccionar_indexables(activas, estado_indexacion)

    if args.completa:
        import shutil, tempfile
        # Con --salida el arbol se construye donde diga actualizar.sh, que
        # lo movera en su commit atomico; sin ella, se publica aqui mismo.
        if args.salida:
            temporal = args.salida
            temporal.mkdir(parents=True, exist_ok=True)
        else:
            temporal = Path(tempfile.mkdtemp(dir=DESTINO_WEB.parent,
                                             prefix=".i-nuevo-"))
        try:
            print(f"Generando {len(activas)} fichas...")
            informe = generar_completa(temporal, activas, manifiesto,
                                       set(indexables))
            cambios = comparar(temporal, DESTINO_WEB)

            # Validaciones antes de publicar nada.
            generadas = len([p for p in temporal.iterdir()
                             if p.is_dir() and p.name.isdigit()])
            if generadas != len(activas):
                raise SystemExit(
                    f"STOPPER: {generadas} fichas para {len(activas)} activas.")

            print(f"  {informe['paginas']} páginas HTML")
            limite = estado_indexacion.get("limite")
            print(f"  abiertas a buscadores: {len(indexables)} de {len(activas)}"
                  f" (limite de la tanda: {'todas' if limite is None else limite})")
            print(f"  altas {len(cambios['altas'])} · bajas {len(cambios['bajas'])}"
                  f" · cambios {len(cambios['cambios'])}")
            if cambios["bajas"]:
                print(f"  bajas (pasan a inactivas): {', '.join(cambios['bajas'][:20])}")

            if args.dry_run:
                if not args.salida:
                    shutil.rmtree(temporal)
                print("\n  DRY-RUN: generado y validado; no se ha publicado nada.")
                return

            ALIAS.write_text(json.dumps(informe["alias"], ensure_ascii=False,
                                        indent=1), encoding="utf-8")
            # Se persiste junto a los alias: una ficha abierta en esta pasada
            # sigue abierta en las siguientes aunque cambie su completitud.
            INDEXACION.write_text(json.dumps(
                {"limite": estado_indexacion.get("limite"),
                 "indexadas": indexables}, indent=1), encoding="utf-8")
            if args.salida:
                print(f"\n  en staging: {temporal}"
                      "  (lo publica actualizar.sh)")
                return

            publicar(temporal, DESTINO_WEB)
            total = sum(f.stat().st_size for f in DESTINO_WEB.rglob("*.html"))
            print(f"\n  publicado en {DESTINO_WEB}  ({total/1024/1024:.1f} MB)")
        except BaseException:
            # Con --salida el directorio es de actualizar.sh: su propio
            # trap lo limpia. Solo se borra lo que hemos creado nosotros.
            if not args.salida and temporal.exists():
                shutil.rmtree(temporal)
            raise
        return

    if args.muestra is None:
        sys.exit("Indica --muestra o --completa.")

    if args.muestra:
        elegida = next((i for i in activas if str(i["idCode"]) == args.muestra), None)
        if not elegida:
            sys.exit(f"idCode {args.muestra} no encontrado entre las activas.")
    else:
        # Una con los tres campos rellenos y portada de buena resolucion.
        elegida = next(
            i for i in activas
            if all(i.get(c) for c in ("tipoConstruccion", "datacion", "estadoConservacion"))
            and not manifiesto[str(i["idCode"])].get("upscaled"))

    entrada = manifiesto.get(str(elegida["idCode"]))
    if not entrada:
        sys.exit(f"{elegida['idCode']} no tiene portada en el manifiesto.")

    abierta = str(elegida["idCode"]) in set(indexables)
    html = render(elegida, entrada["url"], indexable=abierta)
    validar(html, elegida, indexable=abierta)

    SALIDA_MUESTRA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA_MUESTRA / f"{elegida['idCode']}.html"
    destino.write_text(html, encoding="utf-8")

    print(f"  {elegida['nombre']}")
    print(f"  {elegida.get('ciudad')}, {elegida.get('provincia')}  ·  idCode {elegida['idCode']}")
    print(f"  slug: {slug(elegida.get('idUnico',''))}")
    print(f"  preview: {descripcion(elegida)}")
    print(f"  portada: {entrada['final']} · {entrada['bytes']/1024:.0f} KB")
    print(f"\n  {destino}  ({len(html)/1024:.1f} KB)")



# ── Pasada completa (B4.3) ──────────────────────────────────────────────────

def generar_completa(destino: Path, activas: list, manifiesto: dict,
                     indexables: set | None = None) -> dict:
    """Genera el arbol /i completo en `destino` (temporal). Devuelve el informe.

    Cada iglesia se publica en su ruta canonica (/i/<idCode>/) y en la del slug
    actual. Los slugs historicos se conservan como PAGINA COMPLETA, no como
    redireccion: el crawler de WhatsApp no sigue un meta refresh, asi que un
    enlace antiguo compartido perderia el preview.
    """
    alias = json.loads(ALIAS.read_text()) if ALIAS.exists() else {}
    css_rel = "/i/estilo.css"
    (destino / "estilo.css").parent.mkdir(parents=True, exist_ok=True)
    (destino / "estilo.css").write_text(CSS, encoding="utf-8")

    indexables = indexables or set()
    paginas = 0
    urls_sitemap = []
    for ig in activas:
        codigo = str(ig["idCode"])
        entrada = manifiesto.get(codigo)
        if not entrada:
            raise SystemExit(f"STOPPER: {codigo} sin portada en el manifiesto.")

        abierta = codigo in indexables
        html = render(ig, entrada["url"], css=css_rel, indexable=abierta)
        validar(html, ig, indexable=abierta)
        if abierta:
            # Solo la URL canonica: los slugs historicos apuntan a ella.
            urls_sitemap.append(url_canonica(ig))

        actual = slug(ig.get("idUnico", ""))
        historicos = set(alias.get(codigo, []))
        if actual:
            historicos.add(actual)
        alias[codigo] = sorted(historicos)

        base = destino / codigo
        base.mkdir(parents=True, exist_ok=True)
        (base / "index.html").write_text(html, encoding="utf-8")
        paginas += 1
        for s in historicos:
            (base / s).mkdir(parents=True, exist_ok=True)
            (base / s / "index.html").write_text(html, encoding="utf-8")
            paginas += 1

    # Viaja dentro de /i/, en la misma sustitucion atomica que las fichas.
    (destino / "sitemap.xml").write_text(sitemap(urls_sitemap), encoding="utf-8")
    return {"alias": alias, "paginas": paginas, "sitemap": len(urls_sitemap)}


def comparar(destino: Path, publicado: Path) -> dict:
    """Altas, bajas y cambios frente a lo que hay publicado hoy."""
    def fichas(raiz: Path) -> set:
        if not raiz.exists():
            return set()
        return {p.name for p in raiz.iterdir() if p.is_dir() and p.name.isdigit()}

    nuevas, viejas = fichas(destino), fichas(publicado)
    cambios = []
    for codigo in nuevas & viejas:
        a = (publicado / codigo / "index.html")
        b = (destino / codigo / "index.html")
        if a.exists() and a.read_text() != b.read_text():
            cambios.append(codigo)
    return {"altas": sorted(nuevas - viejas), "bajas": sorted(viejas - nuevas),
            "cambios": sorted(cambios)}


def publicar(temporal: Path, destino: Path) -> None:
    """Sustitucion atomica: nunca se edita el arbol publicado en caliente."""
    previo = destino.parent / f"{destino.name}.previo"
    if previo.exists():
        __import__("shutil").rmtree(previo)
    if destino.exists():
        destino.rename(previo)
    temporal.rename(destino)
    if previo.exists():
        __import__("shutil").rmtree(previo)

if __name__ == "__main__":
    main()
