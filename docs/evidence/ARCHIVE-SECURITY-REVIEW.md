# Archivering en beveiliging — onafhankelijke deelrapportage

**PASS archivering en Bash-onafhankelijkheid. Geen concrete open HIGH/CRITICAL-bevindingen in de beoordeelde actieve code.** Dit oordeel betreft broncode en testopzet; productieacceptatie vereist daarnaast de daadwerkelijke CI- en releasebewijzen van het eindrapport.

## Archiefinventaris

Geteld met `rg --files --hidden --no-ignore` op de canonical werkmap. Het archief bevat **219 bestanden**: 190 onder `archive/python-installer/`, 28 onder `archive/research/` en één centrale `archive/README.md`.

| Bewaarde categorie | Bestanden |
|---|---:|
| Oude werkende Python-route en overige bestanden direct onder python-installer | 67 |
| Oorspronkelijke gecommitteerde baseline | 46 |
| Laatste historische publieke commit | 61 |
| Private historische preflight en tests | 16 |
| Onderzoeken, JSON-bewijs, historische testuitvoer en exacte working-treepatch | 28 |
| Centrale archiefuitleg | 1 |

Binnen het totale archief staan **104 Python-bestanden**, **51 Markdown-bestanden**, **9 historische shellscripts** en **5 historische releasearchieven**. Deze aantallen overlappen de bovenstaande categorieën en moeten niet worden opgeteld. Alle 51 historische Markdown-bestanden bevatten de afsluitmarkering **CLOSED – SUPERSEDED BY BASH V1**. De oude workflows bevinden zich uitsluitend binnen het archief en zijn daardoor geen actieve GitHub-workflows.

De publieke en private ontwikkelclone bevatten dezelfde archiefinventaris van 219 bestanden. Git-geschiedenis wordt behouden via gewone vervolgcommits; deze review heeft geen geschiedenis herschreven en geen historisch Ramin-archief aangepast. Historische bronnen zijn bewust bewaard, inclusief voormalige Python-startcommando's binnen duidelijk gesloten documenten.

## Actieve route en documentatie

De actieve route bestaat uit `install.sh`, `VERSION`, `bash/common.sh`, `checks.sh`, `state.sh`, `swap.sh`, `app.sh` en `database.sh`. Codex gebruikt uitsluitend twee declaratieve npm-bestanden onder `bash/assets/codex/`. Geen actieve module importeert of start bestanden uit het archief. Python 3 verschijnt uitsluitend als te installeren en te controleren APP-ontwikkelpakket; het is geen installerafhankelijkheid. DATABASE en de Bash-kern voeren geen Python-code uit.

Actieve documentatie: `README.md`, `CHANGELOG.md`, `docs/INSTALLATION.md`, `docs/RECOVERY.md`, `docs/ARCHITECTURE.md`, `docs/ARCHIVE.md` en `docs/VALIDATION.md`. README geeft `bash install.sh` als startopdracht; CHANGELOG sluit de Python-route formeel af. Het archiefregister vermeldt individuele historische bestanden.

## Beveiligingsreview

De review omvatte menu en autorisatie, root/sudo, APT-validatie en foutafhandeling, state-versies, exclusieve installatievergrendeling, rootbeschermde hervatcode, systemd-resume, swapallocatie en fstab, APP/npm-integriteit en PostgreSQL-configuratie. De code bevat geen `curl | bash`, algemene OS-upgrade, databaseverwijdering of automatische SSH/firewallwijzigingen.

De aanvankelijk gevonden HIGH-bevinding bij conditionele swapverificatie is gesloten: fouten in kopiëren, schrijven, hernoemen en synchroniseren stoppen expliciet voordat fstab door gedeeltelijke uitvoer kan worden vervangen. Swapmarkers en statusbestanden hebben dezelfde expliciete foutafhandeling. Swapinventarisatie gebruikt exacte `--show=SIZE` en `--show=NAME`-kolommen en stopt bij foutieve of mislukte inventarisatie. Twee eerdere observatieproblemen — niet-toegankelijke status ten onrechte als nieuw tonen en stille verificatiefouten bij afgeronde installaties — zijn eveneens opgelost. OS-identificatie overschrijft de installerversie niet meer.

Codex is vastgezet op 0.128.0 met lock-SHA256 `b2645d7cb42265680842553b3d16a5f512a645187c96abe55c6f1d1d5f859d71`, npm-SRI en genegeerde lifecycle-scripts. npm draait zonder overgenomen gebruikersconfiguratie; ruwe uitvoer wordt afgeschermd. PostgreSQL 18 behoudt data en gebruikers en vereist lokale luisteradressen en peer/SCRAM-authenticatie. Bestaande configuratie wordt vóór pakketinstallatie gecontroleerd.

## Bewijsgrens en beperkingen

- Dit deelrapport levert onafhankelijke broncodereview en inventarisatie; het vervangt geen daadwerkelijk uitgevoerde pakket-, swap- of reboottest.
- De VM-testopzet controleert een echte tweede boot en de hervatservice met resultaat, exitstatus en starttijd. Onderbroken swapallocatie moet veilig blokkeren, met ongewijzigde partial checksum en fstab. Deze review heeft de uiteindelijke CI-artefacten niet onafhankelijk gedownload.
- Beveiligde bestaande configuraties buiten het ondersteunde contract worden niet automatisch hersteld: vreemde Codex-installaties, afwijkende PostgreSQL-configuratie en onbekende swapbestanden vereisen handmatige beoordeling.
- Ondersteunde swapbestandssystemen zijn ext4 en XFS; ongeschikte bestandssystemen stoppen veilig. Minder dan 4 GiB fysiek RAM geeft een waarschuwing.
- Productie-GO en definitieve V1-publicatie mogen uitsluitend volgen wanneer alle verplichte acceptatiebewijzen voor de exact gepubliceerde code slagen. Anders blijft de oplevering een duidelijk gemarkeerde NO-GO-prerelease.
