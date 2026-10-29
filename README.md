# Universal Linux Installer

Interactieve Bash-installer voor een **TEST-/ontwikkelserver** op Ubuntu 26.04 LTS,
met drie profielen: **APP**, **DB** of **APP + DB**. Niet voor productie gevalideerd.

## Welke versie?

| Versie | Status | Bron |
| --- | --- | --- |
| `1.0.0-bash.4` | Gepubliceerde prerelease; **huidige aanbevolen route** | Git `78f8c2c`; de tarball is byte-voor-byte reproduceerbaar met `tools/release.sh` |
| `1.1.0-bash.3` | Als prerelease gepubliceerd, **niet aanbevolen** | Geen bron in Git; vereist Python; de eigen release notes noemen het een niet-vrijgegeven ontwikkelkandidaat |
| `1.0.0-bash.5` | **Kandidaat op deze branch, niet gepubliceerd** | Deze branch |

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

## Kandidaat 1.0.0-bash.5 (niet gepubliceerd)

Wijzigingen ten opzichte van bash.4:

- Eén eenvoudig menu:

  ```text
  Universal Linux Installer
  1) APP       — applicatieserver
  2) DB        — databaseserver
  3) APP + DB  — gecombineerde server
  4) Controle  — read-only preflight
  0) Stoppen
  ```

  (`5` stopt ook, voor wie het oude menu gewend is.)
- Een read-only **Controle** vóór iedere bevestiging: rechten, swap, vrije
  schijfruimte, bestaande Nginx/PostgreSQL en bezette poorten 80/443/5432.
  Een FAIL (te weinig schijf voor swap, bezette poort, onbekend swapbestand,
  geen sudo) stopt het plan **voordat** er iets wordt gevraagd of gewijzigd.
- `tools/render-bootstrap.sh` maakt `ONE-COMMAND.txt` met het leesbare
  commando hierboven.
- De release-build bevat alleen wat de bootstrap uitvoert en reproduceert de
  gepubliceerde bash.4-tarball exact.

Lokaal gebouwde, deterministische pins (nog **niet** gepubliceerd; de URL
geeft nu 404):

| Bestand | SHA256 |
| --- | --- |
| `universal-linux-installer-1.0.0-bash.5.tar.gz` | `b1a74337b389975a52de41570cbd74ea102b55a8f1f9f0a3e547fe297035d684` |
| `bootstrap.sh` (standaard-URL's) | `95d5e03320100fbdb62101606df91ae5a4ca2701c6f320ad1582a0f91d02fbcd` |

Na publicatie wordt het commando gelijk aan het bash.4-commando, met `v1.0.0-bash.5`
in de URL en de bootstrap-hash hierboven.

## Geavanceerde routes

- **Direct een profiel** (bevestiging blijft verplicht):
  `bash uli-bootstrap.sh --profile app|database|combined`
- **Alleen controleren**: `bash uli-bootstrap.sh --audit` (bash.5: zelfde als menukeuze 4)
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
