> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# WP-001 — Resultaat iteratie 1

Uitgevoerd op 2026-10-10, uitsluitend in de lokale ontwikkeluitvoeromgeving.
WP-001 is volledig gelezen. Geen commit of push uitgevoerd.

## PASS — implementatie en tests

`python3 -B -m unittest discover -s tests -v`: **12 tests geslaagd**.

De tests gebruiken fictieve waarnemingen en gemockte probes; ze controleren de
profielen, minimumgrenzen, onbekend OS, niet-Linux kernel, ontbrekende swap,
poortconflicten, parserfouten, probe-fouten en timeouts, toegestane queries,
bewijsopslag bij FAIL, weigeren van overschrijven, pad- en symlinkgrenzen,
JSON-terugval bij opslagfouten en afwijzen van ongeldige profielen.

> Correctie in [iteratie 2](ITERATION-2-RESULTS.md): onderstaande CPU/RAM-FAIL
> kwam door productieadvies als minimum te behandelen. Voor de afgesproken
> O/TEST-omgeving zijn 1 vCPU en 843 MiB toegestaan en hoogstens WARN.
> Het bewijs van iteratie 1 blijft ongewijzigd als historisch resultaat.

## FAIL — lokale resourcebeoordeling (historisch, beleid gecorrigeerd)

| Profiel | Uitslag | CPU waargenomen / minimum | RAM MiB waargenomen / minimum | Exitcode |
| --- | --- | --- | --- | ---: |
| APP | FAIL | 1 / 2 | 843,0625 / 2048 | 1 |
| DB | FAIL | 1 / 2 | 843,0625 / 4096 | 1 |
| APP-DB | FAIL | 1 / 4 | 843,0625 / 6144 | 1 |

Dit betreft de zichtbare uitvoeromgeving en de voorlopige minima uit het ontwerp.
Het is geen definitieve capaciteitsuitspraak over de volledige APP-O-host.
OS (Ubuntu), Linux-kernel, circa 87,22 GiB vrije schijfruimte, 4096 MiB swap,
aanwezigheid van sshd en sudo, en vrije voorgestelde profielpoorten kregen PASS.

## WARN — niet-verifieerbare controles

- `systemctl` gaf exitcode 1: actieve services konden niet worden geïnventariseerd.
- `ss` leverde geen zichtbare TCP-listener op poort 22 op. SSH-bereikbaarheid,
  authenticatie en configuratie zijn niet getest.
- Wachtwoordloze sudo is bewust niet geverifieerd vanwege het sudo-verbod.

Het JSON-bewijs is ondanks de FAIL-controles opgeslagen:

- [APP](evidence/iteration-1-app.json)
- [DB](evidence/iteration-1-db.json)
- [APP-DB](evidence/iteration-1-app-db.json)

## Toegevoegde bestanden

- `infrastructure/installer/preflight.py`: lokale preflight en JSON-rapportage.
- `tests/test_preflight.py`: automatische tests met fictieve gegevens.
- `docs/installer/ARCHITECTURE.md`: gebruik, ontwerp en veiligheidsgrenzen.
- `docs/installer/ITERATION-1-RESULTS.md`: dit resultaatverslag.
- De drie JSON-bewijsbestanden hierboven.

Het reeds aanwezige, ongetrackte `docs/workpackages/WP-001.md` is niet gewijzigd.
