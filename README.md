# Universal Linux Installer

Interactieve Bash-installer voor een **TEST-/ontwikkelserver** op Ubuntu 26.04 LTS,
met drie profielen: **APP**, **DB** of **APP + DB**. Niet voor productie gevalideerd.

## Welke versie?

| Versie | Status | Bron |
| --- | --- | --- |
| `1.0.0-bash.4` | Gepubliceerde prerelease; **huidige aanbevolen route** | Git `78f8c2c`; de tarball is byte-voor-byte reproduceerbaar met `tools/release.sh` |
| `1.1.0-bash.3` | Als prerelease gepubliceerd, **niet aanbevolen** | Bron niet in deze repository (wel reproduceerbaar uit niet-publieke ontwikkelhistorie); vereist Python; de eigen release notes noemen het een niet-vrijgegeven ontwikkelkandidaat |
| `1.0.0-bash.5` | Kandidaat, niet gepubliceerd, vervangen door bash.6 | Branch `feature/uli-one-command-001` |
| `1.0.0-bash.6` | **Kandidaat op deze branch, niet gepubliceerd** | Branch `feature/uli-consolidation-002`: de gekozen, enige verder te ontwikkelen lijn (bash.4 + bash.5 + menu, systeemupdate, kleuren, status). De niet-publieke 1.1/1.2-lijn wordt niet voortgezet |

Versienummers zijn vaste pins, geen upgradepad: een server die met een andere
versie is geïnstalleerd, wordt door een nieuwe versie niet stilzwijgend
opnieuw verwerkt (harde STOP, status blijft ongewijzigd).

## Aanbevolen: één commando

Plak in een terminal op de server, als **gewone gebruiker** (niet als root):

```bash
curl --proto '=https' --tlsv1.2 -fsSLo uli-bootstrap.sh https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-bash.4/bootstrap.sh && echo '51f6681f01ffc7c2c007266f7c98ba354972ed4139fc50034b1fc46d349c109d  uli-bootstrap.sh' | sha256sum -c - && bash uli-bootstrap.sh
```

Wat er gebeurt:

1. De bootstrap wordt via HTTPS gedownload naar `uli-bootstrap.sh`.
2. `sha256sum -c` controleert hem tegen de vastgepinde hash. Bij een afwijking
   stopt de regel en wordt **niets** uitgevoerd.
3. De bootstrap downloadt de installer-tarball, controleert die tegen een
   tweede, in de bootstrap vastgelegde hash, inspecteert het archief
   (eigenaar, padtraversal, symlinks, bestandstypes, limieten, verplichte
   bestanden), controleert de interne versie en Bash-syntax, en opent pas dan
   het menu.
4. U kiest een profiel, ziet het installatieplan en bevestigt met `ja`. Pas
   daarna vraagt `sudo` om uw wachtwoord.

Geen `curl | bash`, geen root-download, geen `apt upgrade`, geen SSH-, firewall-
of rebootwijziging.

### Trustmodel

- De **eerste pin** (de hash in het commando hierboven) staat op dezelfde
  GitHub-pagina als het bestand. Dat beschermt tegen beschadigde of gewijzigde
  downloads, maar **niet** tegen iemand die zowel deze README als de release kan
  wijzigen. Neem de hash voor echte onafhankelijkheid uit een tweede kanaal dat
  u vertrouwt (bijvoorbeeld uw eigen notities of de private projectdocumentatie)
  en vergelijk.
- De **tweede pin** (archief-hash) zit in de bootstrap zelf en wordt dus door
  de eerste pin beschermd.
- Er zijn geen uitgeverhandtekeningen. HTTPS en GitHub zijn de transportlaag,
  geen herkomstbewijs.

## Kandidaat 1.0.0-bash.6 (niet gepubliceerd)

Eén menu:

```text
UNIVERSAL LINUX INSTALLER
1. APP SERVER INSTALLEREN
2. DATABASE SERVER INSTALLEREN
3. APP + DATABASE SERVER INSTALLEREN
4. INSTALLATIESTATUS
5. SYSTEEM BIJWERKEN (APT UPDATE + APT UPGRADE)
6. ALLEEN CONTROLE (READ-ONLY)
0. AFSLUITEN
```

| Keuze | bash.4 | bash.5 | bash.6 | CLI |
| --- | --- | --- | --- | --- |
| APP / DB / APP + DB | 1 / 2 / 3 | 1 / 2 / 3 | 1 / 2 / 3 | `--profile app\|database\|combined` |
| Status | 4 (details) | — | 4 (compact) | `--summary`; details `--status` |
| Systeem bijwerken | — | — | 5 | `--system-update` |
| Controle (read-only) | — | 4 | 6 | `--audit` of `--control` |
| Afsluiten | 5 | 0 (5 = alias) | 0 | — |

Let op: in bash.4 was 5 "afsluiten". In bash.6 opent 5 alleen het **plan** voor
een systeemupdate; er gebeurt niets zonder terminal en zonder het woord `bijwerken`.

- **Systeem bijwerken (5)**: toont eerst read-only (`apt-get -s upgrade` op de
  bestaande index) OS-versie, aantal en lijst upgrades, nieuwe pakketten,
  holds/kept back, vrije schijf, mogelijke dienstonderbrekingen en
  herstartindicatie. Pas na het woord `bijwerken` volgt sudo (wachtwoord alleen
  via de terminal), dan onder de installerlock `apt-get update`, een nieuw plan
  (gewijzigd ⇒ opnieuw tonen en bevestigen) en `apt-get upgrade` zonder `-y`
  (APT vraagt zelf ook nog). Nooit `dist-upgrade`/`full-upgrade`,
  `autoremove`, verwijderingen of een automatische herstart. STOP bij
  niet-Ubuntu-bronnen, onveilige APT-configuratie, dpkg-conflict, removals,
  installerlock, onderbroken installatie of geen interactieve terminal.
  Gesaneerd auditrapport (0600) in `/var/lib/universal-linux-installer/`.
- **Installatiestatus (4)**: compact en read-only: versie, toestand
  (niet geïnstalleerd / bezig / voltooid / onderbroken / fout), stap x/y,
  laatste geslaagde stap, Nginx/PostgreSQL/Codex (vereist `0.128.0`), swap,
  herstart, updates volgens lokale index, logpad en volgende veilige actie.
  Onbekend = WARN. Geen sudo, writes of netwerk.
- **Kleuren**: PASS groen, WARN geel, FAIL rood, alleen op een terminal.
  Uit bij `NO_COLOR`, `TERM=dumb`, redirects en in het installatielog.
- **Controle (6)** en de preflight vóór elke installatiebevestiging uit bash.5
  zijn functioneel ongewijzigd (nu met kleurlabels).

Lokaal gebouwde, deterministische pins (nog **niet** gepubliceerd; de URL
geeft nu 404):

| Bestand | SHA256 |
| --- | --- |
| `universal-linux-installer-1.0.0-bash.6.tar.gz` | `540d3813a2198240e26fe998ca6742fc9f49d4163ac396915439563b5a5004fc` |
| `bootstrap.sh` (standaard-URL's) | `a605bc43c465a10a23a950e0a4a9979f6584892260996f7909a4259e908451f6` |

## Geavanceerde routes

- **Direct een profiel** (bevestiging blijft verplicht):
  `bash uli-bootstrap.sh --profile app|database|combined`
- **Alleen controleren**: `bash uli-bootstrap.sh --audit` (bash.6: menukeuze 6)
- **Systeem bijwerken**: `bash uli-bootstrap.sh --system-update` (bash.6: menukeuze 5)
- **Status**: `bash uli-bootstrap.sh --status`
- **Offline**: download de tarball en `SHA256SUMS` van de release, controleer met
  `sha256sum -c SHA256SUMS`, pak uit en start `bash install.sh`.
- **`install-now` registreren** (`install-now.sh`, bash.4): blijft werken voor
  bestaande gebruikers, maar is voor nieuwe gebruikers niet meer nodig. Het
  eerste script van die route wordt niet zelf gecontroleerd.

## Bouwen en testen (offline)

```bash
bash tests/run.sh        # alle offline contracttests, met mocks; geen sudo of systeemwijziging
bash tests/release.sh    # deterministische build, exacte payload, checksums
bash tools/release.sh    # release/universal-linux-installer-$(cat VERSION).tar.gz
bash tools/render-bootstrap.sh "$(cat VERSION)" release/universal-linux-installer-$(cat VERSION).tar.gz out/
```

Provenance van bash.4 nagaan: pak `git archive 78f8c2c` uit, kopieer
`tools/release.sh` van deze branch erin en bouw; de hash moet
`3e86da621994748b5687dd5edd35948328e9e2eb6a712185a150402a46baa931` zijn
(getest met GNU tar 1.35 en gzip 1.12).

Bestanden in de root (`bootstrap.sh`, `BOOTSTRAP.sha256`, `SHA256SUMS`,
`install-now.sh`, de bash.4-tarball) zijn de ongewijzigde gepubliceerde
bash.4-distributie.
