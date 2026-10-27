# Web romanicomaps.com · cómo se actualiza sin romper nada

La web se publica con GitHub Pages desde `main`. Tiene tres partes y cada una
tiene su único sitio de edición:

| Parte | Ficheros publicados | Dónde se edita | Quién la genera |
|---|---|---|---|
| Portada | `index.html` | `_src/portada.html` (texto y estructura), `_src/portada.css` (estilo), `_build_site.py` (SEO, FAQ, precio) | `python3 _build_site.py` |
| Legales | `privacidad.html`, `aviso-legal.html`, `agradecimientos.html`, `condiciones-uso.html` | `_src/*.md` | `python3 _build_site.py` |
| `sitemap.xml`, `robots.txt`, `CNAME` | — | `_build_site.py` | `python3 _build_site.py` |
| Páginas temáticas | `mapa-romanico-espana.html`, `iglesias-romanicas.html`, `rutas-romanicas.html`, `monasterios-romanicos.html` | a mano, en el propio fichero | nadie (el generador solo las comprueba) |
| Fichas | `i/…` | `_fichas/` (ver su README) | tarea nocturna 23:40 |

## Reglas

1. **Nunca edites a mano** `index.html`, las legales, `sitemap.xml` ni
   `robots.txt`: el generador los sobrescribe. Edita `_src/` y regenera.
2. El **SEO de todas las páginas generadas** (title, description, canonical,
   Open Graph, Twitter, datos estructurados) está **solo** en `_build_site.py`
   (`PAGINAS`, `cabecera()`, `datos_estructurados()`). Así no se pierde al
   regenerar, que es lo que pasó el 2026-07-06.
3. Las **preguntas frecuentes** están en la lista `FAQ` de `_build_site.py`:
   de ahí salen a la vez el texto visible y el esquema `FAQPage`.
4. El **precio de Premium** está en `PRECIO_PRIMER_ANIO` y `PRECIO_RENOVACION`.
   Cámbialo solo ahí y solo cuando cambie en las tiendas.
5. El **dominio canónico** es `https://romanicomaps.com` (sin `www`; `www`
   redirige). El generador rechaza cualquier `www.romanicomaps.com`.
6. Las imágenes de la portada van en `img/`. Si cambias una, mantén el nombre
   o actualiza la referencia en `_src/portada.html`.
7. Las cifras del Folio I y II (censo por provincias y siglos) son del export
   del 2026-10-24. Al actualizarlas, cámbialas en `_src/portada.html`.

## Flujo

```bash
cd /Volumes/DevSSD_2TB/RomanicoMaps/romanicomaps-web
git switch -c web/lo-que-sea            # nunca directamente en main
# … editar _src/ o _build_site.py …
python3 _build_site.py                  # genera, comprueba y solo escribe si todo está bien
(cd _src && python3 -m unittest discover -s tests)
python3 -m http.server 8000             # vista previa: http://localhost:8000
git add -A && git commit                # y merge a main --no-ff tras revisarlo
```

Si el generador encuentra un problema, **no escribe nada** y lista los errores.
`python3 _build_site.py --comprobar` revisa lo que hay ahora en disco sin
generar (útil tras tocar una página temática a mano).

No publiques entre las 23:30 y las 00:30: a esa hora la tarea nocturna de las
fichas trabaja sobre `main`.

## Qué comprueba

- Cada página: `lang="es"`, un solo `<title>`, description de 50–170
  caracteres, canonical exacto, Open Graph completo, `twitter:card`, robots,
  JSON-LD válido, ningún `www.romanicomaps.com` y ningún enlace o imagen local
  que no exista.
- Portada: Organization, WebSite, MobileApplication y FAQPage; preguntas
  visibles idénticas a las del esquema; un solo `<h1>`; correo de soporte y
  enlaces a las dos tiendas; ninguna marca `{{…}}` sin rellenar.
- `sitemap.xml` con todas las páginas y `robots.txt` con los dos sitemaps y
  sin `Disallow`.
