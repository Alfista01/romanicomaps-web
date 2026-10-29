"""Identidad común de romanicomaps.com.

La importan _build_site.py (portada y páginas legales) y
_fichas/generar_fichas_web.py (fichas de cada iglesia). Todo lo que deba verse
igual en las dos (datos de la app, cifra del catálogo, tipografías, colores,
logo e insignias de las tiendas) vive SOLO aquí y en marca.css.
"""
from pathlib import Path
from urllib.parse import quote

SRC = Path(__file__).resolve().parent

DOMINIO = "https://romanicomaps.com"
NOMBRE = "Románico Maps"
EMAIL = "soporte@romanicomaps.com"
APP_ID = "6759716898"
APP_URL = f"https://apps.apple.com/app/id{APP_ID}"
PLAY_URL = "https://play.google.com/store/apps/details?id=com.romanicomaps"
LOGO = "logo_romanico_maps.png"            # en la raíz del sitio

# Cifra del catálogo tal como se anuncia en la web (portada y fichas).
CIFRA_IGLESIAS = "casi 7.000"

FUENTES = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
           '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
           '<link href="https://fonts.googleapis.com/css2?family=Marcellus+SC&'
           'family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">')

# Insignias oficiales (Apple Marketing Tools y Google Play, en español), sin modificar.
INSIGNIA_APPLE = "img/tiendas/app-store-es.svg"
INSIGNIA_GOOGLE = "img/tiendas/google-play-es.png"


def css():
    """CSS común (tokens, logo, botones, arco, insignias)."""
    return (SRC / "marca.css").read_text(encoding="utf-8")


# R5 (atribución de campañas). Convención: anexo R5 de
# romanico_maps/claude/entrada/CMO_monetizacion.md.
CAMPANA_WEB = "web"            # portada, temáticas y legales
CAMPANA_FICHA = "ficha_web"    # fichas /i/


def url_app_store(ct=None):
    """Enlace al App Store con campaña `ct` (≤ 40 caracteres): App Store Connect
    cuenta las descargas por campaña en Analytics → Fuentes → Campañas."""
    return f"{APP_URL}?ct={quote(ct, safe='')}" if ct else APP_URL


def url_play(**referrer):
    """Enlace a Google Play con `referrer` (utm_source, utm_medium, utm_campaign
    y, en las fichas, idCode). Play lo entrega a la app en el primer arranque."""
    ref = "&".join(f"{k}={v}" for k, v in referrer.items() if v not in (None, ""))
    return f"{PLAY_URL}&referrer={quote(ref, safe='')}" if ref else PLAY_URL


def insignias(raiz="", play_url=None, app_url=None, sangria="      "):
    """Bloque de insignias. raiz="" para páginas en la raíz; "/" para las fichas (/i/...).
    Por defecto, enlaces con la campaña de la web (R5); las fichas pasan los suyos."""
    play_url = play_url or url_play(utm_source=CAMPANA_WEB, utm_medium="boton")
    app_url = app_url or url_app_store(CAMPANA_WEB)
    return (f'{sangria}<div class="marco-tiendas">\n'
            f'{sangria}  <a class="insignia" href="{app_url.replace("&", "&amp;")}"><img src="{raiz}{INSIGNIA_APPLE}" '
            'alt="Descárgalo en el App Store" width="144" height="48"></a>\n'
            f'{sangria}  <a class="insignia" href="{play_url.replace("&", "&amp;")}"><img src="{raiz}{INSIGNIA_GOOGLE}" '
            'alt="Disponible en Google Play" width="162" height="48"></a>\n'
            f'{sangria}</div>')
