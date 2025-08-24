#!/usr/bin/env bash
# =======================================================================================
#  kernel_cleanup.sh
#
#  Zweck:
#    - Behalte laufenden Kernel + genau eine andere Version (die neueste).
#    - Entferne alle älteren Kernel inkl. Headers/Modules/Modules-extra.
#    - Räume passende DKMS-Builds der entfernten Kernel-Versionen auf.
#    - Führe APT-Bereinigung aus; update-initramfs & update-grub.
#
#  Nutzung:
#    - Trockenlauf: sudo DRY_RUN=1 ./kernel_cleanup.sh
#    - Live:       sudo ./kernel_cleanup.sh
#
#  Hinweise:
#    - Flavor standardmäßig "generic". Bei Bedarf KEEP_FLAVOR=lowlatency o. ä. setzen.
#    - Meta-Pakete (linux-generic-*) werden nicht entfernt.
# =======================================================================================

set -euo pipefail

KEEP_FLAVOR="${KEEP_FLAVOR:-generic}"   # z. B. generic, lowlatency
DRY_RUN="${DRY_RUN:-0}"                 # 1 = nur anzeigen, 0 = ausführen

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[DRY-RUN] $*"
  else
    echo "+ $*"
    eval "$@"
  fi
}

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "Bitte als root ausführen (sudo)."
    exit 1
  fi
}

# Wandelt Paketnamen in reine Kernel-Versionsstrings um.
# Robust:
#  - akzeptiert optionales "-unsigned" (linux-image-unsigned-…)
#  - greift bis direkt vor "-${KEEP_FLAVOR}"
#  - behandelt linux-headers-<ver> (ohne Flavor) ebenfalls
pkg_to_ver() {
  sed -E \
    -e "s/^linux-(image|headers|modules|modules-extra)(-unsigned)?-([0-9].*)-${KEEP_FLAVOR}\$/\3/" \
    -e "s/^linux-headers-([0-9].*)\$/\1/"
}

# „harte“ Normalisierung: falls ein Element noch wie ein Paketname aussieht,
# nochmal in Version verwandeln (Schutz gegen falsch erkannte Einträge).
normalize_version() {
  local s="$1"
  sed -E \
    -e "s/^linux-(image|headers|modules|modules-extra)(-unsigned)?-([0-9].*)-${KEEP_FLAVOR}\$/\3/" \
    -e "s/^linux-headers-([0-9].*)\$/\1/" <<<"$s"
}

pkg_installed() {
  dpkg -l "$1" &>/dev/null
}

# ----------------------------------- Start --------------------------------------------
require_root

CURRENT="$(uname -r)"                 # z. B. 6.14.0-24-generic
CUR_VER="${CURRENT%-${KEEP_FLAVOR}}"  # → 6.14.0-24

echo "=================================================================="
echo " Kernel-Bereinigung mit DKMS-Aufräumung"
echo "------------------------------------------------------------------"
echo " Laufender Kernel     : $CURRENT"
echo " Behaltener Flavor    : $KEEP_FLAVOR"
echo " Modus                : $([[ $DRY_RUN == 1 ]] && echo DRY-RUN || echo LIVE)"
echo "=================================================================="

# Alle installierten Image-Pakete (einschl. -unsigned)
mapfile -t IMAGE_PKGS < <(dpkg -l | awk -v f="$KEEP_FLAVOR" '
  $1=="ii" && ($2 ~ ("^linux-image-[0-9].*-" f "$") || $2 ~ ("^linux-image-unsigned-[0-9].*-" f "$")) {print $2}
' | sort -u)

if (( ${#IMAGE_PKGS[@]} == 0 )); then
  echo "Keine installierten linux-image-* Pakete für Flavor '${KEEP_FLAVOR}' gefunden."
  echo "Es gibt nichts zu tun."
  exit 0
fi

# Versionen extrahieren, sortieren
mapfile -t VERSIONS < <(printf '%s\n' "${IMAGE_PKGS[@]}" | pkg_to_ver | sort -V)

# Validierung: falls etwas noch wie ein Paketname aussieht, erneut normalisieren
for i in "${!VERSIONS[@]}"; do
  if [[ "${VERSIONS[$i]}" =~ ^linux- ]]; then
    VERSIONS[$i]="$(normalize_version "${VERSIONS[$i]}")"
  fi
done

# Sicherstellen, dass die laufende Version gelistet ist
if ! printf '%s\n' "${VERSIONS[@]}" | grep -qx "$CUR_VER"; then
  echo "WARNUNG: Laufende Kernel-Version '$CUR_VER' wurde in den Paketen nicht gefunden."
  echo "Das Script entfernt dennoch niemals den laufenden Kernel."
fi

# Behalte: laufend + neueste andere Version (falls vorhanden)
KEEP=()
LATEST="${VERSIONS[-1]}"
if [[ "$LATEST" == "$CUR_VER" ]]; then
  if (( ${#VERSIONS[@]} >= 2 )); then
    PREV="${VERSIONS[-2]}"
    KEEP=("$CUR_VER" "$PREV")
  else
    KEEP=("$CUR_VER")
  fi
else
  KEEP=("$CUR_VER" "$LATEST")
fi

# Doppelte entfernen/sortieren
KEEP=($(printf '%s\n' "${KEEP[@]}" | awk 'NF' | sort -u))
echo "Behalte Version(en): ${KEEP[*]}"

# Welche Versionen entfernen?
to_remove_versions=()
for v in "${VERSIONS[@]}"; do
  keep_this=0
  for k in "${KEEP[@]}"; do
    [[ "$v" == "$k" ]] && keep_this=1 && break
  done
  (( keep_this == 0 )) && to_remove_versions+=("$v")
done

if (( ${#to_remove_versions[@]} == 0 )); then
  echo "Es gibt keine älteren Kernel zu entfernen."
else
  echo "Alte Version(en) zur Entfernung: ${to_remove_versions[*]}"
fi

# Paketlisten zum Entfernen (Images, Modules, Modules-Extra, Headers)
REMOVE_PKGS=()
for v in "${to_remove_versions[@]}"; do
  # Images (signed & unsigned), Modules …
  for base in linux-image linux-image-unsigned linux-modules linux-modules-extra; do
    pkg="${base}-${v}-${KEEP_FLAVOR}"
    pkg_installed "$pkg" && REMOVE_PKGS+=("$pkg") || true
  done
  # Headers (ohne & mit Flavor)
  for hdr in "linux-headers-${v}" "linux-headers-${v}-${KEEP_FLAVOR}"; do
    pkg_installed "$hdr" && REMOVE_PKGS+=("$hdr") || true
  done
done

# Entfernen
if (( ${#REMOVE_PKGS[@]} > 0 )); then
  echo "Pakete zum vollständigen Entfernen (purge):"
  printf '  - %s\n' "${REMOVE_PKGS[@]}"
  run "apt-get -y purge ${REMOVE_PKGS[*]}"
else
  echo "Keine zu entfernenden alten Kernel-Pakete gefunden."
fi

# Sicherstellen, dass für die beibehaltenen Versionen die notwendigen Pakete vorhanden sind
for v in "${KEEP[@]}"; do
  [[ -z "$v" ]] && continue
  need_pkgs=(
    "linux-image-${v}-${KEEP_FLAVOR}"
    "linux-headers-${v}"
    "linux-headers-${v}-${KEEP_FLAVOR}"
  )
  for p in "${need_pkgs[@]}"; do
    if ! pkg_installed "$p"; then
      echo "Fehlendes Paket für beibehaltene Version entdeckt: $p → wird installiert"
      run "apt-get -y install $p"
    fi
  done
done

# --------------------------- DKMS-Bereinigung (sicher) -------------------------------
if command -v dkms &>/dev/null; then
  echo "------------------------------------"
  echo "Bereinige DKMS-Builds (nur für tatsächlich entfernte Kernel) ..."

  # Menge aller noch vorhandenen Kernel (aus /lib/modules)
  declare -A EXISTING_KERNELS=()
  while IFS= read -r d; do
    kv="$(basename "$d")"             # z.B. 6.14.0-27-generic
    EXISTING_KERNELS["$kv"]=1
  done < <(find /lib/modules -maxdepth 1 -mindepth 1 -type d 2>/dev/null)

  # Menge der „behaltenen“ Kernel explizit schützen
  declare -A KEPT_KERNELS=()
  for v in "${KEEP[@]}"; do
    [[ -z "$v" ]] && continue
    KEPT_KERNELS["${v}-${KEEP_FLAVOR}"]=1
  done
  # zusätzlich laufenden Kernel auf jeden Fall schützen
  KEPT_KERNELS["$CURRENT"]=1

  # Jetzt über dkms status laufen und nur Einträge löschen,
  # deren Kernel NICHT mehr existiert UND NICHT in der Keep-Liste steht.
  while IFS= read -r line; do
    # Beispielzeile: nvidia/570.172.08, 6.14.0-27-generic, x86_64: installed
    mod_field="$(awk -F',' '{print $1}' <<<"$line" | xargs)"   # "nvidia/570.172.08"
    kern_field="$(awk -F',' '{print $2}' <<<"$line" | xargs)"  # "6.14.0-27-generic"
    [[ -z "$mod_field" || -z "$kern_field" ]] && continue

    mod_name="${mod_field%%/*}"
    mod_ver="${mod_field##*/}"
    kern_ver="$kern_field"

    # Schutz: wenn Kernel existiert oder explizit behalten wird → NICHT löschen
    if [[ -n "${EXISTING_KERNELS[$kern_ver]:-}" || -n "${KEPT_KERNELS[$kern_ver]:-}" ]]; then
      continue
    fi

    echo "→ Entferne verwaisten DKMS-Build: Modul '$mod_name' v$mod_ver für Kernel $kern_ver"
    run "dkms remove -m \"$mod_name\" -v \"$mod_ver\" -k \"$kern_ver\" --force || true"
  done < <(dkms status || true)
else
  echo "DKMS nicht installiert → überspringe DKMS-Bereinigung."
fi

# --- Schutz: Kritische Pakete vor Autoremove bewahren ---
PROTECT_PATTERNS=(
  '^nvidia-' '^libnvidia-' '^cuda-'     # NVIDIA / CUDA
  '^zfs-' '^libzfs' '^libzpool' '^libnvpair' '^libuutil'   # ZFS Stack
  '^virtualbox-'                         # (falls genutzt)
)
protect_manual() {
  local pat
  for pat in "${PROTECT_PATTERNS[@]}"; do
    pkgs=$(dpkg -l | awk -v re="$pat" '$1=="ii" && $2 ~ re {print $2}')
    if [[ -n "$pkgs" ]]; then
      echo "Schütze Pakete vor Autoremove (manual): $pat"
      run "apt-mark manual $pkgs"
    fi
  done
}

# --------------------------- APT-Bereinigung ------------------------------------------
protect_manual
# Autoremove optional machen
RUN_AUTOREMOVE="${RUN_AUTOREMOVE:-1}"  # 1=an (Default), 0=aus
if [[ "$RUN_AUTOREMOVE" == "1" ]]; then
  run "apt-get -y autoremove --purge"
else
  echo "Überspringe apt autoremove (RUN_AUTOREMOVE=0)."
fi

# --------------------------- initramfs / GRUB ------------------------------------------
run "update-initramfs -u -k all"
run "update-grub"

echo "=================================================================="
echo "Fertig. Systembereinigung abgeschlossen."
echo "Hinweis: Nach Kernel-Entfernung/Update ist ein Reboot empfehlenswert."
echo "=================================================================="
