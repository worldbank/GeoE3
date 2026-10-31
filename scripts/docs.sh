#!/usr/bin/env bash
# SPDX-FileCopyrightText: Kartoza
# SPDX-License-Identifier: MIT
#
# Lifecycle commands for the GeoE3 mkdocs site: one script, modes — not
# parallel start/stop scripts. Requires the nix devShell's .venv to be
# active (mkdocs/mkdocs-material come from requirements-dev.txt).
set -euo pipefail

# Silences mkdocs-material's own "MkDocs 2.0 is coming" nag banner —
# noise on every invocation, not something this project can act on.
export NO_MKDOCS_2_WARNING=true

PID_FILE="${TMPDIR:-/tmp}/geoe3-mkdocs-serve.pid"
LOG_FILE="${TMPDIR:-/tmp}/geoe3-mkdocs-serve.log"
ADDR="${GEOE3_DOCS_ADDR:-127.0.0.1:8005}"
NIX="nix --extra-experimental-features nix-command --extra-experimental-features flakes"

require_mkdocs() {
  if ! command -v mkdocs >/dev/null 2>&1; then
    echo "mkdocs not found on PATH — run this from inside 'nix develop'." >&2
    exit 1
  fi
}

require_nix() {
  if ! command -v nix >/dev/null 2>&1; then
    echo "nix not found on PATH — run this from inside 'nix develop'." >&2
    exit 1
  fi
}

is_running() {
  [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

cmd_serve() {
  require_mkdocs
  if is_running; then
    echo "mkdocs serve already running (pid $(cat "$PID_FILE")) at http://$ADDR"
    return 0
  fi
  echo "Starting mkdocs serve at http://$ADDR (log: $LOG_FILE)"
  nohup mkdocs serve --dev-addr "$ADDR" >"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  sleep 1
  if is_running; then
    echo "Running (pid $(cat "$PID_FILE")). Stop with: scripts/docs.sh stop"
  else
    echo "Failed to start — see $LOG_FILE" >&2
    rm -f "$PID_FILE"
    exit 1
  fi
}

cmd_stop() {
  if ! is_running; then
    echo "mkdocs serve is not running"
    rm -f "$PID_FILE"
    return 0
  fi
  pid="$(cat "$PID_FILE")"
  kill "$pid"
  rm -f "$PID_FILE"
  echo "Stopped mkdocs serve (pid $pid)"
}

cmd_status() {
  if is_running; then
    echo "mkdocs serve running (pid $(cat "$PID_FILE")) at http://$ADDR"
  else
    echo "mkdocs serve is not running"
  fi
}

cmd_build() {
  require_mkdocs
  mkdocs build --strict
}

cmd_pdf() {
  require_mkdocs
  require_nix

  # weasyprint (mkdocs-with-pdf's rendering engine) needs its cffi/pango/
  # cairo bindings linked the way nixpkgs links them — a pip install
  # breaks with dlopen errors. It's deliberately not a permanent devShell
  # dependency (see mkdocs-pdf.yml's header comment), so fetch it here,
  # on top of whatever's already on PYTHONPATH.
  echo "Resolving weasyprint + brand fonts for PDF rendering..."
  local weasyprint lato jbm dejavu fcdir pyver
  weasyprint="$($NIX build --no-link --print-out-paths nixpkgs#python3Packages.weasyprint)"
  pyver="$(python3 -c 'import sys; print(f"python{sys.version_info[0]}.{sys.version_info[1]}")')"
  export PYTHONPATH="$weasyprint/lib/$pyver/site-packages:${PYTHONPATH:-}"

  # weasyprint also needs real font files visible to fontconfig — this
  # sandbox/most nix machines have no system fontconfig at all, so
  # everything would silently fall back to whatever's on disk. Build a
  # throwaway fonts.conf pointing at the nix store, same approach (same
  # packages, even) as srs/build.sh uses for the SRS PDF. Lato, not the
  # site's own Nunito: there's no standalone top-level `nunito-fonts`
  # attribute in nixpkgs, and Lato is already the proven, working choice
  # here — it's the "Kartoza document typeface" per flake.nix.
  lato="$($NIX build --no-link --print-out-paths nixpkgs#lato)"
  jbm="$($NIX build --no-link --print-out-paths nixpkgs#jetbrains-mono)"
  dejavu="$($NIX build --no-link --print-out-paths nixpkgs#dejavu_fonts)"
  fcdir="$(mktemp -d)"
  # Double-quoted so $fcdir expands now, to a literal path baked into
  # the trap command — not deferred to fire-time, when this function's
  # `local fcdir` has already gone out of scope (with `set -u`, that's
  # an "unbound variable" error instead of a harmless no-op cleanup).
  # shellcheck disable=SC2064
  trap "rm -rf '$fcdir'" EXIT
  mkdir -p "$fcdir/fonts"
  cp "$jbm"/share/fonts/truetype/JetBrainsMono-{Regular,Bold,Italic,BoldItalic}.ttf "$fcdir/fonts/"
  {
    echo '<?xml version="1.0"?>'
    echo '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">'
    echo '<fontconfig>'
    echo "  <dir>$fcdir/fonts</dir>"
    echo "  <dir>$lato/share/fonts</dir>"
    echo "  <dir>$dejavu/share/fonts</dir>"
    echo "  <cachedir>$fcdir/cache</cachedir>"
    echo '</fontconfig>'
  } >"$fcdir/fonts.conf"

  # No --strict here: mkdocs-with-pdf's internal link checker piggybacks
  # on that flag and misfires on glightbox's image-zoom anchors (see the
  # comment at the top of mkdocs-pdf.yml). Real broken links are still
  # caught by the plain `mkdocs build --strict` used by
  # `scripts/docs.sh build` and CI.
  echo "Building PDF documentation (this also builds a separate copy of the HTML site)..."
  FONTCONFIG_FILE="$fcdir/fonts.conf" mkdocs build -f mkdocs-pdf.yml
  echo "PDF: site/pdf/GeoE3-Documentation.pdf"
}

case "${1:-}" in
  serve) cmd_serve ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  build) cmd_build ;;
  pdf) cmd_pdf ;;
  *)
    echo "Usage: $0 {serve|stop|status|build|pdf}" >&2
    exit 1
    ;;
esac
