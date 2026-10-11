#!/usr/bin/env bash
swap_active_bytes() { swapon --show --bytes --noheadings --output SIZE | awk '{s+=$1} END {printf "%.0f\n",s}'; }
swap_ensure() {
  local minimum=4294967296 active deficit file marker phase bytes fs available temporary
  file=$ROOT/var/lib/universal-linux-installer/swapfile
  marker=$STATE_DIR/swap-owner
  active=$(swap_active_bytes) || return
  if [[ -e $marker ]]; then
    [[ -f $marker && ! -L $marker && $(stat -c %u "$marker") == 0 && $(stat -c %a "$marker") == 600 ]] || { fail 'Onzekere swap-eigendomsregistratie'; return 1; }
    read -r phase bytes < "$marker"
    [[ $phase =~ ^(allocated|formatted|active|persistent)$ && $bytes =~ ^[0-9]+$ ]] || { fail 'Onzekere swapfase'; return 1; }
    [[ -f $file && ! -L $file && $(stat -c %u "$file") == 0 && $(stat -c %a "$file") == 600 && $(stat -c %h "$file") == 1 && $(stat -c %s "$file") == "$bytes" ]] || { fail 'Swapbestand wijkt af; handmatig onderzoek vereist'; return 1; }
  elif [[ -e $file || -L $file ]]; then
    fail 'Onbekend bestaand swapbestand; wordt niet overschreven'; return 1
  elif (( active >= minimum )); then
    pass 'Bestaande actieve swap is minimaal 4 GiB'; return
  else
    [[ ${1:-install} != verify ]] || { fail 'Afgeronde installatie mist swap; handmatige beoordeling vereist'; return 1; }
    deficit=$((minimum-active)); bytes=$(( (deficit+$(getconf PAGESIZE)+1048575)/1048576*1048576 ))
    fs=$(findmnt -n -o FSTYPE -T "$STATE_DIR")
    [[ $fs == ext4 || $fs == xfs ]] || { fail "Ongeschikt swapbestandssysteem: $fs"; return 1; }
    available=$(df -B1 --output=avail "$STATE_DIR" | tail -1 | tr -d ' ')
    (( available >= bytes+1073741824 )) || { fail 'Onvoldoende schijfruimte voor swap en 1 GiB reserve'; return 1; }
    # Exclusive creation; an interrupted allocation has no ownership marker and blocks recovery.
    (set -o noclobber; umask 077; : > "$file") || { fail 'Swapbestand bestaat al'; return 1; }
    if ! dd if=/dev/zero of="$file" bs=1048576 count=$((bytes/1048576)) conv=fsync status=none; then fail 'Swapallocatie onderbroken; handmatige inspectie vereist'; return 1; fi
    phase=allocated
    swap_marker "$phase" "$bytes"
  fi
  if [[ $phase == allocated ]]; then
    mkswap "$file" || return
    phase=formatted; swap_marker "$phase" "$bytes"
  fi
  if ! swapon --show --noheadings --raw --output NAME | grep -Fx -- "$file" >/dev/null; then
    swapon "$file" || return
  fi
  phase=active; swap_marker "$phase" "$bytes"
  local fstab=$ROOT/etc/fstab
  [[ -f $fstab && ! -L $fstab ]] || { fail 'Onveilige of ontbrekende fstab'; return 1; }
  if awk -v path="$file" '$1==path {found++; if ($2!="none" || $3!="swap" || $4!="sw") bad=1} END {exit (bad || found>1)?2:(found?0:1)}' "$fstab"; then :
  else
    local code=$?
    (( code == 1 )) || { fail 'Conflicterende fstab-regel'; return 1; }
    temporary=$(mktemp "$ROOT/etc/.uli-fstab.XXXXXX") || return
    cp --preserve=mode,ownership "$fstab" "$temporary"
    printf '\n%s none swap sw 0 0\n' "$file" >> "$temporary"
    mv -f "$temporary" "$fstab"
    sync -f "$ROOT/etc"
  fi
  swap_marker persistent "$bytes"
  (( $(swap_active_bytes) >= minimum )) || { fail 'Actieve swap is minder dan 4 GiB'; return 1; }
  pass 'Minimaal 4 GiB actieve persistente swap'
}
swap_marker() {
  local temporary
  temporary=$(mktemp "$STATE_DIR/.swap-owner.XXXXXX") || return
  chmod 600 "$temporary"
  printf '%s %s\n' "$1" "$2" > "$temporary"
  mv -f "$temporary" "$STATE_DIR/swap-owner"
  sync -f "$STATE_DIR"
}
