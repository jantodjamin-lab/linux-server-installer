# Universal Linux Installer

Interactieve Bash-installer voor een **TEST-/ontwikkelserver** op Ubuntu 26.04 LTS,
met drie profielen: **APP**, **DB** of **APP + DB**. Niet voor productie gevalideerd.

## Welke versie?

| Versie | Status | Bron |
| --- | --- | --- |
| `1.0.0-bash.4` | Gepubliceerde prerelease; vorige versie, blijft beschikbaar | Git `78f8c2c`; de tarball is byte-voor-byte reproduceerbaar met `tools/release.sh` |
| `1.1.0-bash.3` | Als prerelease gepubliceerd, **niet aanbevolen** | Bron niet in deze repository (wel reproduceerbaar uit niet-publieke ontwikkelhistorie); vereist Python; de eigen release notes noemen het een niet-vrijgegeven ontwikkelkandidaat |
| `1.0.0-bash.5` | Kandidaat, niet gepubliceerd, vervangen door bash.6 | Branch `feature/uli-one-command-001` |
| `1.0.0-bash.6` | **Gepubliceerde prerelease (29 oktober 2026); aanbevolen route** — combined-profiel live geaccepteerd, APP-only en DB-only nog niet live getest | [Release](https://github.com/jantodjamin-lab/linux-server-installer/releases/tag/v1.0.0-bash.6), tag `v1.0.0-bash.6` = `0db1998` op `bash-v1`: de gekozen, enige verder te ontwikkelen lijn (bash.4 + bash.5 + menu, systeemupdate, kleuren, status). De niet-publieke 1.1/1.2-lijn wordt niet voortgezet |

Versienummers zijn vaste pins, geen upgradepad: een server die met een andere
versie is geïnstalleerd, wordt door een nieuwe versie niet stilzwijgend
opnieuw verwerkt (harde STOP, status blijft ongewijzigd).

## Aanbevolen: één commando

Versie **1.0.0-bash.6** (prerelease). Plak in een terminal op de server, als
**gewone gebruiker** (niet als root), bij voorkeur in uw thuismap:

```bash
curl --proto '=https' --tlsv1.2 -fsSLo uli-bootstrap.sh https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-bash.6/bootstrap.sh && echo '8481178940339c20f18f0d7d8b02bcb19c4fb9b7589e8b10176a73caa6a213f8  uli-bootstrap.sh' | sha256sum -c - && bash uli-bootstrap.sh
```

Vorige versie 1.0.0-bash.4 (blijft werken):

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

## Versie 1.0.0-bash.6 (prerelease)

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

### Live-acceptatie (door de eigenaar, 29 oktober 2026)

Op een schone Ubuntu 26.04.1-testhost, commit `40c4d02`, profiel **APP + DB (combined)**:

| Controle | Uitslag |
| --- | --- |
| Schone installatie | PASS — 10/10 stappen, `COMPLETE` |
| Componenten | PASS — .NET 10.0.113, Node 22.22.1, npm 9.2.0, Codex CLI 0.128.0, Nginx actief, PostgreSQL 18.6, swap 4 GiB |
| Herstart vóór update | PASS — status, Nginx, PostgreSQL en swap blijven werken |
| Systeem bijwerken (5) | PASS — 66 Ubuntu-pakketten bijgewerkt, auditrapport aangemaakt, geen automatische herstart; daarna `dpkg --audit` leeg en diensten actief |
| Herstart ná update | PASS — status `COMPLETE`, tools en swap OK, geen herstart meer vereist |
| APP-only, DB-only | **Niet live getest** — alleen offline (gemockt) bewezen |

Optionele Ubuntu Pro/ESM-updates vallen buiten de standaard `apt upgrade` en
dus buiten menukeuze 5.

Na `40c4d02` zijn alleen twee weergavecorrecties gedaan die tijdens die test
opvielen (zie CHANGELOG): de RAM-waarschuwing telt nu mee in de
controle-uitslag, en een voltooide installatie eindigt met `DONE 10/10` in
plaats van `STOPPED 10/10`. De installatie- en updatelogica is ongewijzigd.

### Pins (gepubliceerd 29 oktober 2026)

| Bestand | SHA256 |
| --- | --- |
| `universal-linux-installer-1.0.0-bash.6.tar.gz` | `64171ef6d1f67f79e76920a7a0fba7f2f2755214974a0bcc64832f36e676dd20` |
| `bootstrap.sh` | `8481178940339c20f18f0d7d8b02bcb19c4fb9b7589e8b10176a73caa6a213f8` |

De gepubliceerde bestanden zijn byte-gelijk aan een schone herbouw vanaf tag
`v1.0.0-bash.6` met `tools/release.sh` (GNU tar 1.35, gzip 1.12).

### Migratie en compatibiliteit

- **Bestaande bash.4-installatie**: bash.6 installeert er niet overheen
  (andere installerversie ⇒ harde STOP, status ongewijzigd). Status (4),
  controle (6) en systeem bijwerken (5) werken wel op zo'n server. Een nieuwe
  installatie met bash.6 vereist een schone server of snapshot.
- **Menunummers**: zie de tabel hierboven. Wie gewend is aan bash.4 "5 =
  afsluiten" komt nu bij het updateplan; daar gebeurt niets zonder het
  woord `bijwerken`. Afsluiten is `0`.
- **`install-now`** (bash.4-registratie) blijft de bash.4-bootstrap starten;
  voor bash.6 gebruikt u het nieuwe één-commando.
- **Codex** blijft vastgepind op `0.128.0`; menukeuze 5 werkt alleen
  Ubuntu-pakketten bij, niet Codex.

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
bash.4-distributie. De bash.6-bestanden staan alleen bij de GitHub-release.
