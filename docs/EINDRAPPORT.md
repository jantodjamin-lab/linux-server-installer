# Definitieve oplevering — Universal Linux Installer Bash V1
> Historical bash.1 acceptance only: Codex was checked as root. See BASH-V1-001.md for the bash.2 correction and current normal-user evidence.


**PASS voor implementatie en echte installatieacceptatie.** Productie-GO volgt uitsluitend na onafhankelijke verificatie van het publieke releasearchief. De releasebijlage `PUBLICATION-VERIFICATION.md` bevat het definitieve besluit, commitnummers en SHA256. Release `v1.0.0-bash.1` blijft de gevraagde prerelease.

| Onderdeel | Resultaat |
|---|---|
| Zelfstandige Bash-kern, menu, APP/DB/APP+DB | PASS |
| Echte pakketten op Ubuntu 26.04.1, alle drie profielen | PASS |
| Echte swap 0 → 4 GiB, 2 → 4 GiB, bestaande 4 GiB behouden | PASS |
| Echte reboot, automatische hervatting, persistentie en herhaling | PASS |
| Onderbroken swap: veilige stop zonder overschrijven | PASS |
| Echte sudo, APT/ontbrekende-pakkettenfouten, audit en vergrendeling | PASS |
| Ondertekende Ubuntu/TransIP-bronnen, component-/servicetests | PASS |
| Bash/ShellCheck, reproduceerbare release, interne/externe checksums | PASS lokaal; publieke controle in releasebijlage |
| Archivering, Markdown-afsluiting en Git-geschiedenis | PASS |
| Hoge/kritieke open bevindingen | Geen gevonden in onafhankelijke review |
| Minder dan 4 GiB gemeten VM-RAM | WARN, zichtbaar zoals vereist |
| APP-O/TEST-O live installatie | Niet uitgevoerd |

[Groene acceptatiematrix](https://github.com/jantodjamin-lab/linux-server-installer/actions/runs/38135968474): negen succesvolle jobs op `1fe418f7ada859562bf80927d1a055d6e7fed51b`. [VALIDATION.md](VALIDATION.md) vermeldt alle acht echte scenario's, artifactnummers, versies, reboot-/onderbrekingsbewijzen en bewijsgrenzen. De release voegt documentatie toe; [TESTED-INSTALLER.sha256](evidence/TESTED-INSTALLER.sha256) bewijst ongewijzigde actieve bestanden.

```text
linux-server-installer/
├── install.sh
├── README.md
├── VERSION
├── CHANGELOG.md
├── SECURITY.md
├── bash/
│   ├── common.sh
│   ├── checks.sh
│   ├── state.sh
│   ├── swap.sh
│   ├── app.sh
│   ├── database.sh
│   └── assets/codex/
├── docs/
│   ├── INSTALLATION.md
│   ├── RECOVERY.md
│   ├── ARCHITECTURE.md
│   ├── ARCHIVE.md
│   ├── VALIDATION.md
│   ├── EINDRAPPORT.md
│   └── evidence/TESTED-INSTALLER.sha256
├── tests/
├── tools/
├── .github/workflows/bash-v1.yml
└── archive/
    ├── python-installer/
    └── research/
```

Archief: 219 bestanden — 190 onder Python-installer, 28 onderzoeken en één archief-README. Daarbinnen zijn 104 Python-bestanden, 51 afgesloten Markdown-documenten en vijf historische releasearchieven behouden. Ook oorspronkelijke baseline, laatste publieke Python-commit, private preflight/tests en exacte working-treepatch zijn bewaard. De route is **CLOSED – SUPERSEDED BY BASH V1**. Actieve code gebruikt het archief niet. [ARCHIVE.md](ARCHIVE.md) bevat het volledige register.

README, CHANGELOG, SECURITY, INSTALLATION, RECOVERY, ARCHITECTURE, ARCHIVE en VALIDATION beschrijven de Bash-route. Historische private installer-/werkpakketdocumenten dragen de afsluitmarkering. De oorspronkelijke werkmap met bestaande wijzigingen en het historische Ramin-archief zijn onaangeroerd. Beide branches gebruiken gewone vervolgcommits zonder force-push.

Begrenzingen: Ubuntu 26.04.1 amd64 is werkelijk gevalideerd; geen onbewezen claim voor andere OS-versies/architecturen. Onbekende swapbestanden, vreemde Codex-installaties en afwijkende databaseconfiguraties vereisen handmatige beoordeling. Swap vervangt onvoldoende RAM niet. PostgreSQL is standaard lokaal bereikbaar. Codex-authenticatie en applicatie/TLS-configuratie zijn operatorwerk.

Na download/checksumcontrole, vanuit de uitgepakte map:

```bash
bash install.sh
```

Technische GO voor TEST-O geldt wanneer de publieke verificatiebijlage PASS vermeldt. Dit verleent geen live-installatietoestemming; TEST-O is niet gewijzigd.
