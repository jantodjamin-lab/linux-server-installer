> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# WP-001 — Resultaat iteratie 3 van maximaal 3

Datum: 2026-10-10 UTC. **PASS oplevering en tests / WARN volledigheid en lokale
preflight / geen installatie-GO**. WP-001 is afgerond binnen de aangevraagde
read-only scope; de maximale drie iteraties zijn verbruikt. Een muterende
installer of live acceptatie vereist een afzonderlijk besloten vervolgwerkpakket.

Vooraf gelezen: kennisbaseline, bronregister, WP-001, beide eerdere
iteratieverslagen, projectbaseline en huidige architectuur/implementatie/tests.
De kennisdocumenten en eerdere verslagen/evidence zijn ongewijzigd behouden.
Geen archiefcode overgenomen of uitgevoerd.

## PASS — implementatie en verificatie

- Preflight schema 2 en CLI behouden. Ontbrekende hoofd-inventarissignalen geven
  nu expliciet WARN. Evidencewrites weigeren ook references en beschermde
  configuratiemappen, inclusief opgeloste symlinkpaden.
- Pure planbuilder voor APP, DB en APP-DB: deterministisch schema 1, volledige
  inhoudsbinding, componenten/afhankelijkheden/rechten/PRE/POST/stops, open
  besluiten, operatorstappen en recoverygrenzen. Geen executor of shellpayloads.
- Preflight-PASS/WARN is geen GO: alle plannen zijn OPEN, niet uitvoerbaar en
  `installation_authorized=false`. Preflight-FAIL blijft plan-FAIL; ook dat
  resultaat blijft reviewbaar en opslaanbaar.
- `python3 -B -m unittest discover -s tests -v`: **27/27 PASS**, 0 fouten,
  0 mislukkingen, 0 skips, exit 0. 21 preflighttests en 6 plantests; 8 nieuwe
  testmethoden boven de eerdere 19. Fictieve tests bewijzen geen live installatie.
- Nieuw gedrag gericht getest: ontbrekende signalen, beschermde writepaden,
  profielcomponenten, kleine capaciteit/geen swap, determinisme/inputbehoud,
  geen probes/writes/subprocesses in de builder, inhoudsbinding, FAIL-plan,
  ontbrekende inventory, afwijzen inconsistent/schema-1/nonfinite bewijs,
  JSON-roundtrip van meerdere probe-fouten en FAIL-opslag/geen overschrijven.
- Drie lokale CLI-preflights uitgevoerd, plus drie contracten uit hun JSON.
  Bij de eerste plancontrole bleek foutmeldingsvolgorde na sorted JSON niet
  stabiel. Binnen deze iteratie gecorrigeerd: semantische checkvergelijking en
  volledige foutinhoudbinding; regressie PASS. Geen eerder bewijs overschreven.

## WARN — actuele evidence en open risico’s

| Profiel | Preflight | Plan | CLI-exit | Evidence |
| --- | --- | --- | ---: | --- |
| APP | WARN | WARN / OPEN | 0 | [PRE](evidence/iteration-3-app.json), [plan](evidence/iteration-3-app-plan.json) |
| DB | WARN | WARN / OPEN | 0 | [PRE](evidence/iteration-3-db.json), [plan](evidence/iteration-3-db-plan.json) |
| APP-DB | WARN | WARN / OPEN | 0 | [PRE](evidence/iteration-3-app-db.json), [plan](evidence/iteration-3-app-db-plan.json) |

CPU 1 en RAM 843,0625 MiB geven WARN bij alle profielen; toegestane O-capaciteit.
Lokale swap is positief en geeft PASS. Ontbrekende swap op TEST-O is alleen een
overgedragen feit, niet opnieuw gemeten; nul/onbekend blijft WARN in tests/beleid.
OS/kernel, vrije schijf, voorgestelde poorten en aanwezigheid sshd/sudo/context
geven lokaal PASS. Systemd-service/socketqueries mislukken, TCP 22 ontbreekt en
SSH-security/sudo-autorisatie zijn niet geverifieerd: WARN met foutdetails.

Resterende risico’s: volledige fysieke host/targetidentiteit niet bewezen;
OS/kernelcompatibiliteit, stack/packageversies/bronvertrouwen, pad/mountbinding,
accounts, bindadressen, privileges, swapbeleid en releasekeuzes OPEN. Bezetting
van voorgestelde poorten is geen bewijs van volledige conflictvrijheid. Geen
MFA/RBAC/SSH-sleutellifecycle, live validator, operationele audit/retentie of
backup/rollback gerealiseerd. Hashes bewijzen geen authenticiteit/actualiteit.
Preflighttimestamp is geen freshnesscontrole. Evidence is lokaal herschrijfbaar
buiten deze API; geen WORM-garantie. Padcontrole plus exclusieve creatie beschermt
tegen normale escapes/overschrijven, niet tegen een gelijktijdig kwaadwillig
gewijzigde parentdirectory; later privilegewerk moet dit afzonderlijk behandelen.
Crash/stroomuitval kan bewijsverlies geven; geen fsync-/atomische crashgarantie.

## FAIL — interpretatie

Geen actuele FAIL-controles en geen gefaalde tests. FAIL betekent een aangetoonde
criteriumafwijking (resource onder O/TEST-grens, schijf/kernel of bewijsopslag),
geen onbekendheid. Gesimuleerde FAIL’s zijn geslaagde tests. Historische
iteratie-1-FAIL blijft bewaard. Plan-FAIL volgt preflight-FAIL; ongeldige input
wordt afgewezen. PASS betekent uitsluitend voldoen aan de beschreven test of
controle; WARN betekent beperking/onbekendheid/open besluit.

## Eis → controle → bewijs → grens

| Eis | Controle / testbewijs | Resterende grens |
| --- | --- | --- |
| Python, APP/DB/APP-DB | Stdlib preflight + builder; profieltests en zes nieuwe JSON’s | Geen uitvoerende installer |
| OS/kernel/CPU/RAM/swap/disk | Parsers/evaluator, boundary-, fout- en O/TEST-tests | Geen volledige host/sizing/versiematrix |
| SSH/services/poorten/sudo | Vaste lokale queries, states/conflicts/context-tests | Geen remote/auth/sudo-probe; privilege UNKNOWN |
| PASS/WARN/FAIL + JSON bij fouten | Foutdetails/timeouts/raw, FAIL-opslag, stdoutfallback, beschermde paden | Procescrash/opslaguitval niet volledig gedekt |
| Read-only reviewplan | Componenten/PRE/POST/dependencies/rechten/stops/open besluiten | Target/versies/paden niet gekozen; nooit GO |
| Recovery/reproduceerbaarheid | [Runbook en fasegrenzen](PLAN-CONTRACT.md) | Twee echte installaties met gebruikersrestore NOT TESTED |
| Nieuwe code / scope / iteratiegrens | Reference-integriteit, tests en bestandscontrole | Geen vierde WP-001-iteratie |

## Bestanden en veiligheidsgrenzen

Gewijzigd: `infrastructure/installer/preflight.py`, `tests/test_preflight.py`,
`docs/installer/ARCHITECTURE.md`, `docs/workpackages/WP-001.md`.
Toegevoegd: `infrastructure/installer/plan.py`, `tests/test_plan.py`,
`docs/installer/PLAN-CONTRACT.md`, dit verslag en zes hierboven gelinkte JSON’s.

Geen installatie, sudo, netwerkactie, TEST-O, SSH-configwijziging, commit of push.
Tests en bewijswrites uitsluitend lokaal in repository; tijdelijk
integriteitsmanifest in `/tmp`. Bestaande ongetrackte bestanden behouden,
niets gestaged. References, kennisdocumenten, eerdere verslagen en zes oude
JSON’s zijn op bestandenset/inhoudshash gecontroleerd en ongewijzigd.
Alle 12 evidence-JSON’s zijn leesbaar; de drie nieuwe plannen zijn exact opnieuw
te genereren uit hun invoer. Lokale links in installer/WP-documentatie bestaan.
Whitespacecontrole van gewijzigde/toegevoegde tekstbestanden PASS;
`git diff --check` PASS, met de beperking dat deze bestanden ongetrackt zijn.
