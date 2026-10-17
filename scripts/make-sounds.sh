#!/usr/bin/env bash
# Régénère les notifications Kenney et les impacts synthétiques originaux de public/sounds/.
# CC0 1.0 ; rien de chess.com ni de lichess : voir public/sounds/LICENSES.md.
# Prérequis : curl, unzip, ffmpeg avec libmp3lame, Python 3 avec numpy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/public/sounds"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

IMPACT_ZIP="https://kenney.nl/media/pages/assets/impact-sounds/87b4ddecda-1677589768/kenney_impact-sounds.zip"
IFACE_ZIP="https://kenney.nl/media/pages/assets/interface-sounds/fa43c1dd4d-1677589452/kenney_interface-sounds.zip"

curl -fsSL "$IMPACT_ZIP" -o "$WORK/impact.zip"
curl -fsSL "$IFACE_ZIP" -o "$WORK/iface.zip"
# Empreintes des packs utilisés pour les sons actuels : un pack modifié en amont ne passe pas en silence.
( cd "$WORK" && shasum -a 256 -c - <<'SUMS'
029d734af1582474edf3a694d1b0cebc97c1c152f2f39fa34d4c2bafc5de77f8  impact.zip
f2193d072726d6758a5f7871b2dcc54dcce0d5c35c6f0a62f92549b327c81232  iface.zip
SUMS
)
unzip -qo "$WORK/impact.zip" -d "$WORK/impact"
unzip -qo "$WORK/iface.zip" -d "$WORK/iface"
F="$WORK/iface/Audio"

# render <nom> <crête dBFS> <filtre> <entrées...> : mixe les entrées par le filtre ffmpeg (sortie [m]),
# passe en mono 44,1 kHz, coupe le silence de tête, puis ramène la crête à la valeur demandée.
render() {
  local name="$1" peak="$2" filter="$3"
  shift 3
  local args=()
  for f in "$@"; do args+=(-i "$f"); done
  local wav="$WORK/$name.wav"
  ffmpeg -v error -y "${args[@]}" -filter_complex "$filter;[m]aformat=channel_layouts=mono,aresample=44100,silenceremove=start_periods=1:start_threshold=-50dB[o]" -map "[o]" "$wav"
  local max
  max=$(ffmpeg -hide_banner -i "$wav" -af volumedetect -f null - 2>&1 | sed -n 's/.*max_volume: \(-*[0-9.]*\) dB.*/\1/p')
  local gain
  gain=$(awk -v p="$peak" -v m="$max" 'BEGIN { printf "%.2f", p - m }')
  ffmpeg -v error -y -i "$wav" -af "volume=${gain}dB" -c:a libmp3lame -q:a 4 "$OUT/$name.mp3"
}

one='[0]anull[m]'
mkdir -p "$OUT"
# Les deux packs portent le même texte CC0, à leur nom et leur date près : les deux sont gardés.
{
  tr -d '\r' < "$WORK/impact/License.txt" | sed 's/^\t*//'
  printf '\n==============================\n'
  tr -d '\r' < "$WORK/iface/License.txt" | sed 's/^\t*//'
} > "$OUT/LICENSE-Kenney-CC0.txt"

# Les coups sont extraits séparément : voir scripts/extract-video-sounds.py.
# Notifications, un cran sous les coups.
render game-start -4 "$one" "$F/question_004.ogg"
render game-end -4 "$one" "$F/confirmation_004.ogg"
render low-time -4 "[1]adelay=160:all=1[b];[0][b]amix=inputs=2:normalize=0[m]" "$F/tick_004.ogg" "$F/tick_004.ogg"
render success -4 "$one" "$F/confirmation_002.ogg"
render fail -4 "$one" "$F/error_006.ogg"

ls -l "$OUT"/*.mp3
