# -*- coding: utf-8 -*-
"""Genera el sitio estatico de romanicomaps.com.

Escribe: index.html (portada), las paginas tematicas (mapa, iglesias, rutas,
monasterios; contenido en _src/paginas/), las legales (_src/*.md), sitemap.xml,
robots.txt y CNAME. Todas con la identidad comun de _src/marca.css.
No toca: las fichas /i/ (las genera _fichas/ con la misma identidad).

REGLAS (detalle en _src/README.md):
  * Nunca se edita a mano index.html ni las paginas legales: se editan los
    ficheros de _src/ y, si hace falta, este script.
  * El SEO (title, description, canonical, Open Graph, datos estructurados)
    vive SOLO aqui, en PAGINAS y en datos_estructurados(). Asi no se pierde
    al regenerar (es lo que paso el 2026-07-06).
  * Antes de escribir, comprueba el resultado. Si algo falla, no escribe nada.

Uso:
  python3 _build_site.py               genera, comprueba y escribe lo que cambie
  python3 _build_site.py --comprobar   solo comprueba lo que hay ahora en disco
"""
import datetime
import html
import json
import pathlib
import re
import sys

import qrcode

RAIZ = pathlib.Path(__file__).resolve().parent
SRC = RAIZ / "_src"
HOY = datetime.date.today()
sys.path.insert(0, str(SRC))
import marca  # noqa: E402  identidad común con las fichas (_src/marca.py + marca.css)

# --- Datos del sitio -----------------------------------------------------------
# Los comunes con las fichas vienen de _src/marca.py. Dominio canonico: el apex;
# www.romanicomaps.com redirige (301) aqui, asi que un canonical con www seria
# una senal contradictoria.
DOMINIO = marca.DOMINIO
NOMBRE = marca.NOMBRE
EMPRESA = "GATE2K MANAGEMENT SOLUTIONS S.L.N.E."
EMAIL = marca.EMAIL
APP_URL = marca.APP_URL
PLAY_URL = marca.PLAY_URL
IMAGEN_SOCIAL = "img/og-romanicomaps.jpg"   # 1200x630, para WhatsApp, redes, etc.
LOGO = marca.LOGO
CIFRA = marca.CIFRA_IGLESIAS

# Precio de Premium (lo que cobran las tiendas). Se usa en la portada y en la FAQ.
PRECIO_PRIMER_ANIO = "0,99 €"
PRECIO_RENOVACION = "2,99 €"

# Newsletter (formulario de Brevo, lista #4 "RM · Newsletter", doble confirmacion).
# STAND-BY (decision de Antonio, 2026-10-08): no se publica en la web hasta ~500 descargas.
NEWSLETTER_WEB = False
NEWSLETTER_FORM = "https://c490c023.sibforms.com/v2/serve/MUIFAKGHIiZIQKfViQYdo1N_2WUCwVhYNNQHwSeqjwTv_0Zu6bWOEwTSvGjW0pr7wAv4OtV_teuEhHEzgwFsM0eGyWOCYCyLJAof_WmL33IUATdbwMB3kVmAyT7eM-IgMcgeE0hcBhZ1xwcutg-ctchuMNGQamxNtwuWoPm91A361hd9LEuoHcXi9ZU4kXhq13F8dr9qtaoCfj73MA=="
NEWSLETTER_LEGAL = ("Tus datos se tratan con Brevo, nuestro proveedor de email. Te enviaremos un correo para "
  "confirmar el alta y podrás darte de baja en cualquier momento desde cualquier envío. "
  "Más información en la <a href=\"privacidad.html\">política de privacidad</a>.")

# Preguntas frecuentes: UNA sola lista para el texto visible y para el esquema FAQPage
# (Google exige que coincidan). Texto plano, sin HTML.
FAQ = [
    ("¿Qué es Románico Maps?",
     f"Románico Maps es una aplicación para iPhone y Android que reúne en un mapa {CIFRA} iglesias, "
     "ermitas y monasterios románicos geolocalizados, con su datación, su historia, su estado de "
     "conservación y sus restos románicos."),
    ("¿Necesito registrarme para usar la app?",
     "No. El mapa, la búsqueda y la navegación funcionan sin cuenta. El registro gratuito añade "
     "favoritos, valoraciones y comentarios."),
    ("¿Qué incluye la suscripción Premium y cuánto cuesta?",
     f"Premium retira los anuncios y te da un mapa más amplio, filtrado avanzado, fichas académicas y la "
     f"galería fotográfica completa, incluidas tus propias fotos en los comentarios. Además, ayuda a "
     f"expandir la comunidad. Cuesta {PRECIO_PRIMER_ANIO} el primer año y, después, "
     f"{PRECIO_RENOVACION} al año. Se gestiona desde la tienda de tu dispositivo."),
    ("¿Puedo usar Románico Maps para preparar rutas románicas?",
     "En un futuro podrás dar de alta rutas románicas propias o seguir rutas recomendadas por zonas y "
     "duraciones específicas. En este momento, Románico Maps solo geolocaliza iglesias y permite pasar la "
     "ubicación a tu aplicación de navegación del móvil. Románico Maps puede serte muy útil como "
     "herramienta de registro de favoritas y llevarlas seleccionadas de casa."),
    ("¿Qué tipo de patrimonio incluye la app?",
     "Principalmente iglesias, ermitas, monasterios, colegiatas y catedrales románicas, además de "
     "templos prerrománicos, cada uno con su ficha y su ubicación."),
    ("He visto un dato incorrecto en una iglesia",
     f"Gracias por ayudarnos a mejorar el catálogo. Escríbenos a {EMAIL} con el nombre de la iglesia y su "
     "localidad, o deja un comentario en su ficha indicando el error. Revisamos todos."),
]

# Paginas que genera este script. La clave es el fichero; el resto, su SEO.
PAGINAS = {
    "index.html": dict(
        titulo="Románico Maps | Mapa del románico en España",
        descripcion=(f"{CIFRA[0].upper() + CIFRA[1:]} iglesias, ermitas y monasterios románicos geolocalizados, con su datación, "
                     "historia y estado de conservación. Gratis en iPhone y Android."),
        og_tipo="website", prioridad="1.0", frecuencia="monthly"),
    # Tematicas: contenido en _src/paginas/<fichero>; aqui solo su SEO.
    "mapa-romanico-espana.html": dict(
        titulo="Mapa del románico en España | Románico Maps", nombre="Mapa del románico en España",
        etiqueta="Mapa del románico", cuerpo="paginas/mapa-romanico-espana.html",
        descripcion="Explora un mapa interactivo del románico en España con iglesias, ermitas, monasterios y catedrales geolocalizadas.",
        og_tipo="article", prioridad="0.8", frecuencia="monthly"),
    "iglesias-romanicas.html": dict(
        titulo="Iglesias románicas en España | Románico Maps", nombre="Iglesias románicas en España",
        etiqueta="Iglesias románicas", cuerpo="paginas/iglesias-romanicas.html",
        descripcion="Encuentra iglesias románicas en España con ubicación, fotografías, datos históricos y filtros para preparar visitas culturales.",
        og_tipo="article", prioridad="0.8", frecuencia="monthly"),
    "rutas-romanicas.html": dict(
        titulo="Rutas románicas por España | Románico Maps", nombre="Rutas románicas por España",
        etiqueta="Rutas románicas", cuerpo="paginas/rutas-romanicas.html",
        descripcion="Prepara tus rutas románicas: localiza iglesias, ermitas y monasterios en el mapa, guárdalos como favoritos y llévalos seleccionados de casa.",
        og_tipo="article", prioridad="0.8", frecuencia="monthly"),
    "monasterios-romanicos.html": dict(
        titulo="Monasterios románicos en España | Románico Maps", nombre="Monasterios románicos en España",
        etiqueta="Monasterios románicos", cuerpo="paginas/monasterios-romanicos.html",
        descripcion="Descubre monasterios románicos en España y otros enclaves medievales con Románico Maps, una guía geolocalizada del patrimonio románico.",
        og_tipo="article", prioridad="0.8", frecuencia="monthly"),
    "privacidad.html": dict(
        titulo="Política de privacidad · Románico Maps",
        descripcion="Política de privacidad de la app y la web de Románico Maps: qué datos se tratan, para qué y cómo ejercer tus derechos.",
        og_tipo="article", prioridad="0.3", frecuencia="yearly", fuente="politica_privacidad.md", cabecera="Privacidad"),
    "aviso-legal.html": dict(
        titulo="Aviso legal · Románico Maps",
        descripcion="Aviso legal de Románico Maps: titular del sitio y de la app, condiciones de acceso y propiedad intelectual.",
        og_tipo="article", prioridad="0.3", frecuencia="yearly", fuente="aviso_legal.md", cabecera="Aviso legal"),
    "agradecimientos.html": dict(
        titulo="Agradecimientos y fuentes · Románico Maps",
        descripcion="Fuentes y agradecimientos de Románico Maps, proyecto dedicado a la difusión del arte románico y el patrimonio románico.",
        og_tipo="article", prioridad="0.3", frecuencia="yearly", fuente="agradecimientos.md", cabecera="Agradecimientos"),
    "condiciones-uso.html": dict(
        titulo="Condiciones de uso · Románico Maps",
        descripcion="Condiciones de uso de Románico Maps y de la suscripción Premium.",
        og_tipo="article", prioridad="0.3", frecuencia="yearly", fuente="condiciones_uso.md", cabecera="Condiciones de uso"),
}

# Paginas tematicas (generadas desde _src/paginas/, con bloque de descarga y enlaces cruzados).
TEMATICAS = [a for a, p in PAGINAS.items() if "cuerpo" in p]
LEGALES = [a for a, p in PAGINAS.items() if "fuente" in p]


# --- Utilidades ----------------------------------------------------------------
def url_de(archivo):
    return f"{DOMINIO}/" if archivo == "index.html" else f"{DOMINIO}/{archivo}"


def esc(texto):
    return html.escape(texto, quote=True)


def qr_svg(data, module=4, color="#231D15"):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    m = qr.get_matrix()
    size = len(m) * module
    parts = [f"M{x*module},{y*module}h{module}v{module}h-{module}z"
             for y, row in enumerate(m) for x, v in enumerate(row) if v]
    return (f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="Código QR de descarga">'
            f'<path d="{"".join(parts)}" fill="{color}"/></svg>')


def rellenar(plantilla, valores, nombre):
    """Sustituye las marcas {{ASI}}. Para en seco si falta o sobra alguna."""
    marcas = set(re.findall(r"\{\{([A-Z_]+)\}\}", plantilla))
    faltan = marcas - valores.keys()
    sobran = valores.keys() - marcas
    if faltan or sobran:
        raise SystemExit(f"STOP {nombre}: marcas sin valor {sorted(faltan)}; valores sin marca {sorted(sobran)}")
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: valores[m.group(1)], plantilla)


def sin_comentario_inicial(texto):
    return re.sub(r"\A\s*<!--.*?-->\s*", "", texto, count=1, flags=re.S)


def inline(t):
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', t)
    t = re.sub(r'(?<![\">/])\b([\w.+-]+@[\w.-]+\.\w+)\b', r'<a href="mailto:\1">\1</a>', t)
    return t


def md2html(md):
    out, ul, ol = [], [], []

    def flush_ul():
        nonlocal ul
        if ul:
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in ul) + "</ul>")
            ul = []

    def flush_ol():
        nonlocal ol
        if ol:
            out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in ol) + "</ol>")
            ol = []

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush_ul(); flush_ol(); continue
        if line.startswith("### "):
            flush_ul(); flush_ol(); out.append(f"<h3>{inline(line[4:])}</h3>"); continue
        if line.startswith("## "):
            flush_ul(); flush_ol(); out.append(f"<h2>{inline(line[3:])}</h2>"); continue
        if line.startswith("# "):
            flush_ul(); flush_ol(); out.append(f"<h1>{inline(line[2:])}</h1>"); continue
        if line.strip() == "---":
            flush_ul(); flush_ol(); out.append("<hr>"); continue
        if line.startswith("- "):
            flush_ol(); ul.append(line[2:]); continue
        m = re.match(r'^\d+\.\s+(.*)', line)
        if m:
            flush_ul(); ol.append(m.group(1)); continue
        flush_ul(); flush_ol(); out.append(f"<p>{inline(line)}</p>")
    flush_ul(); flush_ol()
    return "\n".join(out)


# --- Cabecera comun (SEO) --------------------------------------------------------
FUENTES_PORTADA = marca.FUENTES


def cabecera(archivo, extra="", robots="index, follow"):
    p = PAGINAS[archivo]
    url = url_de(archivo)
    imagen = f"{DOMINIO}/{IMAGEN_SOCIAL}"
    t, d = esc(p["titulo"]), esc(p["descripcion"])
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t}</title>
<meta name="description" content="{d}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#F1EADB">
<link rel="icon" href="{LOGO}">
<link rel="apple-touch-icon" href="{LOGO}">
<meta property="og:site_name" content="{esc(NOMBRE)}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:image" content="{imagen}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:url" content="{url}">
<meta property="og:type" content="{p['og_tipo']}">
<meta property="og:locale" content="es_ES">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{imagen}">
<meta name="apple-itunes-app" content="app-id=6759716898">
{extra}"""


def datos_estructurados():
    org = f"{DOMINIO}/#organization"
    grafo = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "@id": org, "name": EMPRESA, "url": f"{DOMINIO}/",
             "logo": f"{DOMINIO}/{LOGO}",
             "contactPoint": {"@type": "ContactPoint", "email": EMAIL,
                              "contactType": "customer support", "availableLanguage": ["es"]}},
            {"@type": "WebSite", "@id": f"{DOMINIO}/#website", "url": f"{DOMINIO}/", "name": NOMBRE,
             "description": "Guía visual de las iglesias románicas de la Península Ibérica.",
             "inLanguage": "es", "publisher": {"@id": org}},
            {"@type": ["MobileApplication", "SoftwareApplication"], "@id": f"{DOMINIO}/#app",
             "name": NOMBRE, "applicationCategory": "TravelApplication", "operatingSystem": "iOS, Android",
             "url": f"{DOMINIO}/", "image": f"{DOMINIO}/{IMAGEN_SOCIAL}",
             "description": (f"Aplicación móvil con {CIFRA} iglesias, ermitas y monasterios románicos "
                             "geolocalizados, con su datación, historia, estado de conservación y restos románicos."),
             "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
             "publisher": {"@id": org}, "sameAs": [APP_URL, PLAY_URL]},
            {"@type": "FAQPage", "@id": f"{DOMINIO}/#faq",
             "mainEntity": [{"@type": "Question", "name": q,
                             "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
        ],
    }
    texto = json.dumps(grafo, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{texto}\n</script>'


# --- Portada ---------------------------------------------------------------------
def faq_html():
    bloques = []
    for i, (q, a) in enumerate(FAQ):
        abierto = " open" if i == 0 else ""
        bloques.append(f"        <details{abierto}><summary>{esc(q)}</summary><p>{esc(a)}</p></details>")
    return "\n".join(bloques)


def portada():
    css = marca.css() + (SRC / "portada.css").read_text(encoding="utf-8")
    cuerpo = sin_comentario_inicial((SRC / "portada.html").read_text(encoding="utf-8"))
    cuerpo = rellenar(cuerpo, {
        "TIENDAS": marca.insignias(), "EMAIL": EMAIL, "FAQ": faq_html(),
        "QR_APP": qr_svg(marca.url_app_store("web_qr")),
        "QR_PLAY": qr_svg(marca.url_play(utm_source=marca.CAMPANA_WEB, utm_medium="qr")),
        "PRECIO_PRIMER_ANIO": PRECIO_PRIMER_ANIO, "PRECIO_RENOVACION": PRECIO_RENOVACION,
        "ANIO": str(HOY.year),
        "ENLACE_NEWSLETTER": '\n      <a href="newsletter.html">Newsletter</a>' if NEWSLETTER_WEB else "",
    }, "portada.html")
    extra = ('<link rel="preload" as="image" href="img/beato-silos-dragon.webp">\n'
             f"{FUENTES_PORTADA}\n{datos_estructurados()}\n<style>\n{css}</style>")
    return cabecera("index.html", extra) + "</head>\n<body>\n" + cuerpo + "</body></html>\n"


# --- Paginas interiores (tematicas y legales) --------------------------------------
# Misma identidad que la portada y las fichas: marca.css + _src/interior.css.
def webpage_ld(archivo):
    p, url = PAGINAS[archivo], url_de(archivo)
    datos = {"@context": "https://schema.org", "@type": "WebPage", "@id": f"{url}#webpage", "url": url,
             "name": p["nombre"], "description": p["descripcion"], "inLanguage": "es",
             "isPartOf": {"@id": f"{DOMINIO}/#website"}}
    texto = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{texto}\n</script>\n'


def pie_interior():
    tem = "".join(f'\n    <a href="{a}">{esc(PAGINAS[a]["etiqueta"])}</a>' for a in TEMATICAS)
    leg = "".join(f'\n    <a href="{a}">{esc(PAGINAS[a]["cabecera"])}</a>' for a in LEGALES)
    if NEWSLETTER_WEB:
        leg += '\n    <a href="newsletter.html">Newsletter</a>'
    return (f'<footer class="pie"><div class="env">\n  <nav aria-label="El románico">\n    <a href="./">Portada</a>{tem}\n  </nav>\n'
            f'  <nav aria-label="Información legal">{leg}\n  </nav>\n'
            f'  <p>© {HOY.year} Románico Maps · GATE2K Management Solutions · romanicomaps.com</p>\n</div></footer>\n')


def pagina_interior(archivo, cuerpo_html, robots="index, follow", con_descarga=False):
    p = PAGINAS[archivo]
    css = marca.css() + (SRC / "interior.css").read_text(encoding="utf-8")
    ld = webpage_ld(archivo) if "nombre" in p else ""
    bloque = ""
    if con_descarga:
        otras = "".join(f'<a href="{a}">{esc(PAGINAS[a]["etiqueta"])}</a>' for a in TEMATICAS if a != archivo)
        bloque = (f'<section class="cta">\n  <h2>Ver en <em>Románico Maps</em></h2>\n'
                  f'  <p>Mapa, fotografías y ficha completa de {CIFRA} iglesias románicas de la Península.</p>\n'
                  f'{marca.insignias(sangria="  ")}\n</section>\n'
                  f'<nav class="relacionadas" aria-label="Más sobre el románico">{otras}</nav>\n')
    return (cabecera(archivo, f"{marca.FUENTES}\n{ld}<style>\n{css}</style>", robots) + "</head>\n<body>\n"
            '<header class="cabecera"><div class="env barra">\n'
            f'  <a class="marca" href="./"><img src="{LOGO}" alt="" width="38" height="38"><span>Románico Maps</span></a>\n'
            '  <a class="btn btn--almagre" href="./#descargar">Descargar</a>\n</div></header>\n'
            f'<main class="env doc">\n{cuerpo_html}\n{bloque}</main>\n'
            + pie_interior() + "</body></html>\n")


def paginas_newsletter():
    """Solo si NEWSLETTER_WEB. La de confirmacion no se indexa."""
    PAGINAS["newsletter.html"] = dict(
        titulo="Newsletter · Románico Maps", cabecera="Newsletter", og_tipo="article",
        descripcion="Newsletter gratuita de Románico Maps: una iglesia, una escapada y un término del glosario cada semana.",
        prioridad="0.5", frecuencia="monthly")
    PAGINAS["newsletter-confirmada.html"] = dict(
        titulo="Alta confirmada · Románico Maps", cabecera="Newsletter", og_tipo="article",
        descripcion="Alta en la newsletter de Románico Maps confirmada.", sitemap=False)
    iframe = (f'<iframe class="nl-frame" src="{NEWSLETTER_FORM}" height="250" '
              f'title="Formulario de alta en la newsletter" loading="lazy" frameborder="0" scrolling="auto"></iframe>')
    alta = ("<h1>El románico, cada semana</h1>\n<p>Apúntate a la newsletter gratuita de Románico Maps: una iglesia "
            "para descubrir, una escapada de fin de semana y un término del glosario. Un correo a la semana, sin compromiso.</p>\n"
            f'{iframe}<p class="nl-legal">{NEWSLETTER_LEGAL}</p>')
    ok = ("<h1>¡Alta confirmada!</h1>\n<p>Gracias por suscribirte. El próximo envío de la newsletter llegará a tu correo.</p>\n"
          f'{marca.insignias(sangria="")}')
    return {"newsletter.html": pagina_interior("newsletter.html", alta),
            "newsletter-confirmada.html": pagina_interior("newsletter-confirmada.html", ok, robots="noindex, follow")}


# --- sitemap.xml y robots.txt ------------------------------------------------------------
def lastmods_actuales():
    """Fecha de cada URL en el sitemap publicado (por ruta, con o sin www)."""
    f = RAIZ / "sitemap.xml"
    if not f.exists():
        return {}
    pares = re.findall(r"<loc>https?://(?:www\.)?romanicomaps\.com/([^<]*)</loc>\s*<lastmod>([^<]+)</lastmod>",
                       f.read_text(encoding="utf-8"))
    return {ruta or "index.html": fecha for ruta, fecha in pares}


def sitemap(salida):
    previas = lastmods_actuales()
    filas = []
    entradas = [(a, p["prioridad"], p["frecuencia"]) for a, p in PAGINAS.items() if p.get("sitemap", True)]
    for archivo, prioridad, frecuencia in entradas:
        disco = RAIZ / archivo
        sin_cambios = archivo not in salida or (disco.exists() and disco.read_text(encoding="utf-8") == salida[archivo])
        fecha = previas.get(archivo) if sin_cambios and previas.get(archivo) else HOY.isoformat()
        filas.append(f"  <url>\n    <loc>{url_de(archivo)}</loc>\n    <lastmod>{fecha}</lastmod>\n"
                     f"    <changefreq>{frecuencia}</changefreq>\n    <priority>{prioridad}</priority>\n  </url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(filas) + "\n</urlset>\n")


def robots():
    # Las fichas /i/ tienen su propio sitemap (lo genera _fichas/). No poner Disallow: rompe su indexacion.
    return (f"User-agent: *\nAllow: /\n\nSitemap: {DOMINIO}/sitemap.xml\nSitemap: {DOMINIO}/i/sitemap.xml\n")


# --- Construccion ----------------------------------------------------------------------
def construir():
    """Devuelve {fichero: contenido} sin escribir nada."""
    salida = {"index.html": portada()}
    for archivo, p in list(PAGINAS.items()):
        if "fuente" in p:
            md = (SRC / p["fuente"]).read_text(encoding="utf-8")
            salida[archivo] = pagina_interior(archivo, md2html(md))
        elif "cuerpo" in p:
            cuerpo = sin_comentario_inicial((SRC / p["cuerpo"]).read_text(encoding="utf-8")).strip()
            salida[archivo] = pagina_interior(archivo, cuerpo, con_descarga=True)
    if NEWSLETTER_WEB:
        salida.update(paginas_newsletter())
    salida["sitemap.xml"] = sitemap(salida)
    salida["robots.txt"] = robots()
    salida["CNAME"] = "romanicomaps.com"
    return salida


# --- Comprobaciones ----------------------------------------------------------------------
def _meta(doc, atributo, nombre):
    return re.findall(rf'<meta {atributo}="{re.escape(nombre)}" content="([^"]*)"', doc)


def comprobar_pagina(archivo, doc, existe):
    """Errores de SEO basico y de enlaces locales de una pagina HTML."""
    e = []
    url = url_de(archivo)
    if '<html lang="es">' not in doc:
        e.append("falta lang=es")
    if len(re.findall(r"<title>[^<]+</title>", doc)) != 1:
        e.append("debe tener exactamente un <title>")
    desc = _meta(doc, "name", "description")
    if len(desc) != 1 or not (50 <= len(html.unescape(desc[0])) <= 170):
        e.append("meta description ausente, repetida o fuera de 50-170 caracteres")
    canon = re.findall(r'<link rel="canonical" href="([^"]+)"', doc)
    if canon != [url]:
        e.append(f"canonical {canon} != {url}")
    for prop in ("og:title", "og:description", "og:image", "og:url", "og:type"):
        if len(_meta(doc, "property", prop)) != 1:
            e.append(f"falta {prop}")
    if _meta(doc, "property", "og:url") not in ([url], []):
        e.append("og:url distinto del canonical")
    for img in _meta(doc, "property", "og:image"):
        if img.startswith(DOMINIO + "/") and not existe(img[len(DOMINIO) + 1:]):
            e.append(f"og:image no existe: {img}")
    if not _meta(doc, "name", "twitter:card"):
        e.append("falta twitter:card")
    robots_meta = _meta(doc, "name", "robots")
    if not robots_meta or not robots_meta[0].startswith(("index", "noindex")):
        e.append("falta meta robots")
    if "www.romanicomaps.com" in doc:
        e.append("aparece www.romanicomaps.com (el dominio canonico es el apex)")
    for bloque in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S):
        try:
            json.loads(bloque)
        except ValueError as err:
            e.append(f"JSON-LD invalido: {err}")
    # Enlaces y recursos locales
    refs = re.findall(r'(?:src|href)="([^"]+)"', doc) + re.findall(r"url\(([^)]+)\)", doc)
    for ref in refs:
        ref = ref.strip("'\"")
        if re.match(r"^(https?:|mailto:|tel:|data:|#|\./?$|/$)", ref):
            continue
        ruta = ref.split("#")[0].split("?")[0]
        if ruta and not existe(ruta):
            e.append(f"enlace o recurso local inexistente: {ref}")
    return [f"{archivo}: {x}" for x in e]


def comprobar(salida):
    """Lista de errores (vacia = todo bien)."""
    def existe(ruta):
        return ruta in salida or (RAIZ / ruta).exists()

    errores = []
    paginas = {a: c for a, c in salida.items() if a.endswith(".html")}
    for archivo in PAGINAS:
        if PAGINAS[archivo].get("sitemap", True) and archivo not in paginas:
            errores.append(f"{archivo}: no se ha generado")
    for archivo, doc in paginas.items():
        errores += comprobar_pagina(archivo, doc, existe)
        # Todas con la identidad común (y sin restos del estilo anterior).
        if "--pergamino" not in doc or "--piedra-2" in doc:
            errores.append(f"{archivo}: no usa la identidad común (_src/marca.css)")
        if len(re.findall(r"<h1[ >]", doc)) != 1:
            errores.append(f"{archivo}: debe haber exactamente un <h1>")
    for archivo in TEMATICAS:
        if '"@type": "WebPage"' not in paginas.get(archivo, ""):
            errores.append(f"{archivo}: faltan los datos estructurados WebPage")

    # Portada: datos estructurados, FAQ visible = FAQ del esquema, h1, contacto y tiendas.
    idx = salida.get("index.html", "")
    tipos, preguntas_ld = set(), []
    for bloque in re.findall(r'<script type="application/ld\+json">(.*?)</script>', idx, re.S):
        try:
            datos = json.loads(bloque)
        except ValueError:
            continue
        for nodo in datos.get("@graph", [datos]):
            t = nodo.get("@type")
            tipos.update(t if isinstance(t, list) else [t])
            if t == "FAQPage":
                preguntas_ld = [q["name"] for q in nodo.get("mainEntity", [])]
    for tipo in ("Organization", "WebSite", "MobileApplication", "FAQPage"):
        if tipo not in tipos:
            errores.append(f"index.html: falta {tipo} en los datos estructurados")
    visibles = [html.unescape(s) for s in re.findall(r"<summary>(.*?)</summary>", idx, re.S)]
    if len(visibles) < 3 or visibles != preguntas_ld:
        errores.append("index.html: las preguntas visibles no coinciden con el FAQPage")
    if len(re.findall(r"<h1[ >]", idx)) != 1:
        errores.append("index.html: debe haber exactamente un <h1>")
    for imprescindible in (f"mailto:{EMAIL}", APP_URL, PLAY_URL, "id=\"soporte\""):
        if imprescindible not in idx:
            errores.append(f"index.html: falta {imprescindible}")
    if re.search(r"\{\{[A-Z_]+\}\}", idx):
        errores.append("index.html: quedan marcas {{...}} sin rellenar")
    if CIFRA.lower() not in idx.lower():
        errores.append(f"index.html: no aparece la cifra del catálogo ({CIFRA})")
    for recurso in (marca.LOGO, marca.INSIGNIA_APPLE, marca.INSIGNIA_GOOGLE):  # también los usan las fichas
        if not existe(recurso):
            errores.append(f"falta {recurso} (lo usan la portada y las fichas)")

    # sitemap y robots
    sm = salida.get("sitemap.xml", "")
    for archivo in [a for a, p in PAGINAS.items() if p.get("sitemap", True)] + TEMATICAS:
        if f"<loc>{url_de(archivo)}</loc>" not in sm:
            errores.append(f"sitemap.xml: falta {archivo}")
    if "www.romanicomaps.com" in sm:
        errores.append("sitemap.xml: contiene www.romanicomaps.com")
    rb = salida.get("robots.txt", "")
    for linea in (f"Sitemap: {DOMINIO}/sitemap.xml", f"Sitemap: {DOMINIO}/i/sitemap.xml"):
        if linea not in rb:
            errores.append(f"robots.txt: falta '{linea}'")
    if re.search(r"^Disallow:\s*/\S*", rb, re.M):
        errores.append("robots.txt: hay un Disallow (romperia la indexacion de las fichas)")
    return errores


def en_disco():
    nombres = list(PAGINAS) + ["sitemap.xml", "robots.txt", "CNAME"]
    return {n: (RAIZ / n).read_text(encoding="utf-8") for n in nombres if (RAIZ / n).exists()}


def main(argv):
    if "--comprobar" in argv:
        errores = comprobar(en_disco())
        print("\n".join(errores) if errores else "COMPROBACION OK: el sitio en disco cumple todo")
        return 1 if errores else 0
    if NEWSLETTER_WEB is False:
        PAGINAS.pop("newsletter.html", None)
    salida = construir()
    errores = comprobar(salida)
    if errores:
        print("NO SE HA ESCRITO NADA. Errores:\n  - " + "\n  - ".join(errores))
        return 1
    cambiados = []
    for nombre, contenido in salida.items():
        destino = RAIZ / nombre
        if not destino.exists() or destino.read_text(encoding="utf-8") != contenido:
            destino.write_text(contenido, encoding="utf-8")
            cambiados.append(nombre)
    print("SITIO GENERADO OK. Cambiados: " + (", ".join(cambiados) if cambiados else "ninguno"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
