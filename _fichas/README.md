# Fichas web (romanicomaps.com/i/)

Las fichas públicas de cada iglesia se generan desde Airtable y viven **solo en
este repo**. La app no las genera ni las publica: sus releases no tocan la web.

| Fichero | Qué es |
|---|---|
| `tarea_nocturna.sh` | Lo que ejecuta la tarea programada diaria (23:40). Prepara copias limpias y llama a `actualizar.sh`. |
| `actualizar.sh` | Export de Airtable → portadas → fichas → un commit en `main` con fichas y estado. |
| `generar_fichas_web.py` | Genera el árbol `i/` (HTML, `sitemap.xml`, alias de URL, indexación por tandas). |
| `generar_portadas_web.py` | Sube a Supabase Storage solo las portadas nuevas o cambiadas. |
| `estado/` | `manifiesto_portadas.json`, `alias_slugs.json`, `indexacion.json`. Siempre en el mismo commit que `i/`. |
| Identidad visual | Común con la portada: `_src/marca.py` y `_src/marca.css` (se copian en `i/estilo.css`). No se duplica aquí. |
| `tests/` | `python3 -m unittest discover -s _fichas/tests -p 'test_*.py'` |

## Uso

```bash
# Ejecutar ahora (o probar sin publicar):
bash /Volumes/DevSSD_2TB/RomanicoMaps/romanicomaps-web/_fichas/tarea_nocturna.sh [--dry-run]
```

- Copias de trabajo y registro: `Claude COO/fichas-web/{trabajo,logs}` (fuera de git).
- Requisitos: disco DevSSD_2TB, `~/.config/romanico/web.env` (service role, nunca en git),
  `.env` de la app (SUPABASE_URL) y `pip install -r _fichas/requirements.txt`.
- Del repo de la app solo se **lee** el exportador `scripts/export_airtable_to_json.dart`
  (rama `develop`).

## Indexación por tandas

`estado/indexacion.json` fija cuántas fichas se abren a Google (`limite`; `null`
abre todas) y cuáles ya están abiertas (nunca se vuelven a cerrar). Para pasar a
la siguiente tanda: cambiar `limite`, commit en `main`, y la siguiente pasada lo
aplica.

## Sincronización de la app (`/sync/`, desde la 1.7.16)

La misma pasada nocturna publica en `romanicomaps.com/sync/` los cambios del
catálogo para la app (`generar_sync.py`): compara el export de hoy con el de la
noche anterior (huellas en `estado/sync_huellas.json`) y deja un
`cambios-<fecha>.json` con las iglesias cambiadas o nuevas y las bajas, más
`manifiesto.json` con los últimos 45 días. La app 1.7.16+ se sincroniza con
estos ficheros, sin pasar por Supabase ni Airtable; las versiones anteriores
siguen con `airtable-proxy`. Las iglesias **nunca se borran en Airtable, solo
se desactivan** (una desactivada llega como baja). Si el export trae más de un
10 % menos de iglesias que el anterior, la pasada se para sin publicar.

