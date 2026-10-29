# Universal Linux Installer 1.0.0-bash.6 — release notes

Status: **gepubliceerd als prerelease** op 29 oktober 2026
([release](https://github.com/jantodjamin-lab/linux-server-installer/releases/tag/v1.0.0-bash.6), tag
`v1.0.0-bash.6` = `0db1998`). Voor TEST-/ontwikkelservers op Ubuntu 26.04 LTS. Niet voor productie
gevalideerd.

## Nieuw ten opzichte van 1.0.0-bash.4

- Eén menu: 1 APP, 2 DB, 3 APP + DB installeren; 4 installatiestatus; 5 systeem bijwerken
  (apt update + apt upgrade); 6 alleen controle (read-only); 0 afsluiten.
- Read-only controle vóór elke installatiebevestiging (rechten, RAM, swap, schijf, bestaande
  Nginx/PostgreSQL, poorten 80/443/5432). Een FAIL stopt vóór vraag, sudo of wijziging.
- Systeem bijwerken: eerst een read-only plan; alleen na het woord `bijwerken` volgen sudo,
  `apt-get update`, een nieuw plan (bij wijziging opnieuw bevestigen) en `apt-get upgrade` zonder
  `-y`. Nooit `full-upgrade`, `autoremove`, verwijderingen of een automatische herstart.
  Gesaneerd auditrapport in `/var/lib/universal-linux-installer/`.
- Compacte read-only installatiestatus met volgende veilige actie.
- Kleuren (groen/geel/rood) alleen op een terminal; nooit in logbestanden.
- Leesbaar één-commando dat de bootstrap verifieert vóór uitvoering.
- Installatiemodules (APP, DB, swap, status, voortgang) functioneel gelijk aan bash.4.

## Validatie

- Live (eigenaar, schone Ubuntu 26.04.1-testhost): combined-profiel installatie 10/10 `COMPLETE`,
  twee herstarts, systeemupdate van 66 pakketten — PASS. Zie README.
- **APP-only en DB-only: niet live getest**, alleen offline met mocks.
- Offline: volledige testsuite (`bash tests/run.sh`), deterministische build
  (`bash tests/release.sh`), shellcheck.

## Artefacten

| Bestand | SHA256 |
| --- | --- |
| `universal-linux-installer-1.0.0-bash.6.tar.gz` | `64171ef6d1f67f79e76920a7a0fba7f2f2755214974a0bcc64832f36e676dd20` |
| `bootstrap.sh` | `8481178940339c20f18f0d7d8b02bcb19c4fb9b7589e8b10176a73caa6a213f8` |

Bouwen: `bash tools/release.sh` en
`bash tools/render-bootstrap.sh 1.0.0-bash.6 release/universal-linux-installer-1.0.0-bash.6.tar.gz <map>`
(GNU tar 1.35, gzip 1.12).

## Bekende beperkingen

- De checksum in het één-commando staat op dezelfde GitHub-bron als de download; neem hem voor
  echte onafhankelijkheid uit een tweede kanaal.
- Een server met een bash.4-installatie wordt niet door bash.6 opnieuw geïnstalleerd (bewuste STOP).
- Optionele Ubuntu Pro/ESM-updates vallen buiten menukeuze 5.
