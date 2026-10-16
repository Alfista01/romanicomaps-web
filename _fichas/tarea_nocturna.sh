#!/bin/bash
# Tarea diaria de las fichas web (la lanza la tarea programada de Claude
# "Románico · Actualización diaria de fichas web", 23:40 Madrid). También vale
# para lanzarla a mano en cualquier momento.
#
#   bash /Volumes/DevSSD_2TB/RomanicoMaps/romanicomaps-web/_fichas/tarea_nocturna.sh [--dry-run]
#
# Prepara copias limpias desde GitHub (web: main · app: develop, solo para leer
# el exportador) en "Claude COO/fichas-web/trabajo/" y ejecuta actualizar.sh de
# la copia web recién sacada. Nunca toca las copias de trabajo de Antonio ni
# commitea en el repo de la app.
#
# Registro: "Claude COO/fichas-web/logs/" (resumen.csv + log del día).
set -euo pipefail

export PATH="/Volumes/DevSSD_2TB/development/flutter/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export LANG="es_ES.UTF-8" LC_ALL="es_ES.UTF-8"

BASE="/Volumes/DevSSD_2TB/RomanicoMaps"
APP_REPO="$BASE/romanico_maps"
WEB_REPO="$BASE/romanicomaps-web"
COO_DIR="$BASE/Claude COO/fichas-web"
TRABAJO="$COO_DIR/trabajo"
WT_APP="$TRABAJO/romanico_maps"
WT_WEB="$TRABAJO/romanicomaps-web"
LOG_DIR="$COO_DIR/logs"
RESUMEN="$LOG_DIR/resumen.csv"
LOCK="$TRABAJO/.lock"
HOY="$(date +%Y-%m-%d)"
OPCION="${1:-}"

aviso() {  # notificación de macOS; nunca rompe la ejecución
  osascript -e "display notification \"$1\" with title \"Románico · fichas web\"" >/dev/null 2>&1 || true
}
[ -d "$BASE" ] || { aviso "Disco DevSSD_2TB no montado"; exit 1; }
mkdir -p "$LOG_DIR" "$TRABAJO"
LOG="$LOG_DIR/$HOY.log"
exec >>"$LOG" 2>&1
echo
echo "== $(date '+%F %T') · fichas web (${OPCION:-normal})"

resumen() {
  [ -f "$RESUMEN" ] || echo "fecha,hora,resultado,detalle" > "$RESUMEN"
  echo "$HOY,$(date +%H:%M),$1,\"$2\"" >> "$RESUMEN"
}
fallo() {
  echo "ERROR: $1"; resumen "error" "$1"; aviso "ERROR: $1 (ver logs/$HOY.log)"; exit 1
}

if ! mkdir "$LOCK" 2>/dev/null; then
  echo "Otra ejecución en curso ($LOCK). Salgo."; exit 0
fi
trap 'rm -rf "$LOCK"' EXIT

preparar_wt() {  # repo worktree rama
  git -C "$1" fetch -q origin "$3"
  if [ ! -e "$2/.git" ]; then
    git -C "$1" worktree prune
    git -C "$1" worktree add -q --detach "$2" "origin/$3"
  fi
  git -C "$2" checkout -q --detach "origin/$3"
  git -C "$2" reset -q --hard "origin/$3"
  git -C "$2" clean -qfd
}
preparar_wt "$APP_REPO" "$WT_APP" develop || fallo "no se pudo preparar la copia de la app"
preparar_wt "$WEB_REPO" "$WT_WEB" main    || fallo "no se pudo preparar la copia web"
# .env de la app (SUPABASE_URL) vive fuera de git; las claves, en web.env.
ln -sf "$APP_REPO/.env" "$WT_APP/.env"
[ -f "$HOME/.config/romanico/web.env" ] || fallo "falta ~/.config/romanico/web.env"

SALIDA="$(mktemp)"
if ! bash "$WT_WEB/_fichas/actualizar.sh" "$WT_APP" $OPCION 2>&1 | tee "$SALIDA"; then
  fallo "$(tail -1 "$SALIDA")"
fi
LINEA="$(grep '^RESULTADO:' "$SALIDA" | tail -1)"
rm -f "$SALIDA"
[ -n "$LINEA" ] || fallo "actualizar.sh terminó sin resultado"
RESULTADO="$(echo "$LINEA" | sed 's/^RESULTADO: \([a-z_]*\).*/\1/')"
DETALLE="$(echo "$LINEA" | sed 's/^RESULTADO: [a-z_]* | //')"
resumen "$RESULTADO" "$DETALLE"
[ "$RESULTADO" = "publicado" ] && aviso "Fichas web publicadas: $DETALLE"
echo "== OK $(date '+%T') · $RESULTADO"
