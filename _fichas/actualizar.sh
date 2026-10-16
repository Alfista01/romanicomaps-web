#!/bin/bash
# Genera y publica las fichas de romanicomaps.com/i/ desde Airtable.
#
# Todo lo de las fichas vive en este repo (romanicomaps-web): generadores,
# estado (_fichas/estado/) y el árbol publicado (i/). Fichas y estado salen
# SIEMPRE en el mismo commit de main. El repo de la app solo se lee, para usar
# su exportador de Airtable (scripts/export_airtable_to_json.dart).
#
# No se ejecuta a mano sobre las copias de trabajo: lo lanza
# _fichas/tarea_nocturna.sh en copias limpias (worktrees) de los dos repos.
#
# Uso: _fichas/actualizar.sh <repo-app> [--dry-run]
# Última línea de salida: "RESULTADO: <publicado|sin_cambios|dry_run> | <detalle>"
set -euo pipefail

WEB="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:?Uso: actualizar.sh <repo-app> [--dry-run]}"
DRY_RUN=0
[ "${2:-}" = "--dry-run" ] && DRY_RUN=1
FIRMA="Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
HOY="$(date +%Y-%m-%d)"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 1. Export de Airtable con el exportador de la app (solo lectura de ese repo).
cd "$APP"
if [ ! -f .dart_tool/package_config.json ] || [ pubspec.lock -nt .dart_tool/package_config.json ]; then
  flutter pub get >/dev/null
fi
dart run scripts/export_airtable_to_json.dart --output "$TMP/export.json"

# 2. Portadas: solo altas y fotos cambiadas (huella del adjunto de Airtable).
cd "$WEB"
python3 _fichas/generar_portadas_web.py --export "$TMP/export.json" \
  --manifest _fichas/estado/manifiesto_portadas.json \
  --output-manifest "$TMP/manifiesto.json"

# 3. Fichas en staging. Actualiza _fichas/estado/alias_slugs.json e
#    indexacion.json de esta copia.
python3 _fichas/generar_fichas_web.py --completa --export "$TMP/export.json" \
  --manifest "$TMP/manifiesto.json" --salida "$TMP/i" | tee "$TMP/fichas.txt"
cp "$TMP/manifiesto.json" _fichas/estado/manifiesto_portadas.json
DETALLE="$(grep -E 'altas|abiertas' "$TMP/fichas.txt" | sed 's/^ *//' | tr '\n' ' ' | tr -d '"|')"

# 4. ¿Cambia algo frente a lo publicado?
rsync -a --delete "$TMP/i/" "$WEB/i/"
CAMBIOS="$(git status --porcelain -- i _fichas/estado | wc -l | tr -d ' ')"
if [ "$CAMBIOS" -eq 0 ]; then
  echo "RESULTADO: sin_cambios | $DETALLE"; exit 0
fi
if [ "$DRY_RUN" -eq 1 ]; then
  echo "RESULTADO: dry_run | $CAMBIOS ficheros · $DETALLE"; exit 0
fi

# 5. Publicar: fichas y estado en un único commit (GitHub Pages sirve main).
git add -A i _fichas/estado
git commit -q -m "fichas web: actualización $HOY" -m "$DETALLE" -m "$FIRMA"
git push -q origin HEAD:main
echo "RESULTADO: publicado | $CAMBIOS ficheros · $DETALLE"
