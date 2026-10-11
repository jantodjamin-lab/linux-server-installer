> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# WP-001 — Resultaat iteratie 2 van maximaal 3

Uitgevoerd op 2026-10-10, uitsluitend in de lokale repository en zichtbare
ontwikkeluitvoeromgeving. Werkpakket, architectuur en verslag en JSON-bewijzen
van iteratie 1 zijn gelezen. Iteratie 3 is niet gestart.

## PASS — implementatie en tests

- Voor alle profielen: 1 vCPU en 843 MiB RAM zijn toegestaan voor O/TEST,
  met WARN onder het behouden productieadvies. Onder het O/TEST-minimum: FAIL.
  De vrije-schijfminima blijven behouden.
- Swap is een afzonderlijke controle en telt niet mee als RAM: PASS bij positieve
  swap, WARN bij nul of onbekend, ook wanneer de geheugenprobe mislukt.
- Service-inventarisatie omvat nu actieve, inactieve en gefaalde geladen units.
  Gefaalde/onbruikbaar geladen services geven WARN. De parser verwerkt de
  systemd-markering voor gefaalde units.
- SSH-services vereisen loaded/active/running. SSH-sockets worden afzonderlijk
  op loaded/active/listening gecontroleerd. Binary, TCP 22 en toegang blijven
  afzonderlijke signalen. Aanwezige signalen bewijzen geen SSH-toegang.
- Sudo-programma en lokale UID/effectieve UID/numerieke groepen worden vastgelegd.
  Geen autorisatie of wachtwoordloos gebruik afgeleid uit aanwezigheid/groepen.
- JSON-schema 2 scheidt minima en productieadvies. Query-exits behouden
  exitcode/stdout/stderr, timeouts gedeeltelijke uitvoer, parserfouten ruwe
  inventaris. Bewijs bij FAIL en JSON op stdout bij opslagfouten blijven behouden.
- Vaste lokale subprocessqueries: geen shell, stdin DEVNULL, timeout vijf seconden.

`python3 -B -m unittest discover -s tests -v`: **19/19 PASS**, 0 fouten,
0 mislukkingen, 0 overgeslagen; exitcode 0 (laatste uitvoering: 0,018 s).
Zeven nieuwe testmethoden; bestaande tests aangepast en uitgebreid.

| Test | Resultaat |
| --- | --- |
| `test_all_profiles_and_safety_warnings` | PASS |
| `test_profile_minimum_boundaries` | PASS |
| `test_missing_swap_conflicts_and_unknown_os` | PASS |
| `test_non_linux_fails` | PASS |
| `test_unavailable_observations_warn` | PASS |
| `test_parsers` | PASS |
| `test_queries_are_fixed_local_and_bounded` | PASS |
| `test_collection_continues_after_read_and_query_failure` | PASS |
| `test_failed_checks_still_saved_and_no_overwrite` | PASS |
| `test_output_failure_preserves_json_on_stdout` | PASS |
| `test_output_path_limits_and_symlinks` | PASS |
| `test_otest_resources_and_production_advice` | PASS |
| `test_otest_floor_and_swap_independent` | PASS |
| `test_failed_services_and_ssh_states` | PASS |
| `test_port22_and_sudo_presence_do_not_prove_access` | PASS |
| `test_query_failure_details_preserved_in_json` | PASS |
| `test_parse_failure_preserves_raw_output` | PASS |
| `test_timeout_partial_output_is_json_serializable` | PASS |
| `test_invalid_profile_rejected_before_collection` | PASS |

Aanvullend: alle zes JSON-bewijzen (iteraties 1 en 2, drie profielen) zijn leesbaar
en geven bij herbeoordeling WARN zonder FAIL. De namen/statussen van controles
plus het beleid van de drie nieuwe bewijzen komen overeen met de huidige
evaluator. Bij de lokale CLI-runs was stdout gelijk aan het opgeslagen JSON.
Alle zes verificaties: PASS. `git diff --check`: PASS (de opleveringsbestanden
zijn ongetrackt; dit commando beoordeelt die bestanden niet).

## WARN — lokale preflight

| Profiel | Status | CPU | RAM MiB | Swap MiB | Vrije schijf GiB | Exitcode |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| APP | WARN | 1 | 843,0625 | 4095,9961 | 87,22 | 0 |
| DB | WARN | 1 | 843,0625 | 4095,9961 | 87,22 | 0 |
| APP-DB | WARN | 1 | 843,0625 | 4095,9961 | 87,22 | 0 |

PASS voor alle profielen: Ubuntu, Linux-kernel, vrije schijf, swap, sshd-programma,
sudo-programma, waargenomen gebruikerscontext en vrije voorgestelde profielpoorten.

WARN voor alle profielen:
- CPU/RAM: toegestaan voor O/TEST, lager dan het productieadvies.
- Services en SSH-sockets: systemctl exitcode 1, lokale systemd-bus niet
  toegankelijk vanuit deze uitvoeromgeving. Foutdetails opgeslagen in JSON.
- Geen zichtbare TCP-listener op poort 22; custom SSH-poorten niet onderzocht.
- SSH-toegang/configuratie/authenticatie en wachtwoordloze sudo niet geverifieerd.

## FAIL — geen actuele FAIL-controles

Geen FAIL-controles in de drie lokale rapporten en geen gefaalde tests.
De historische CPU/RAM-FAILs uit iteratie 1 zijn beleidsfouten en in het oude
verslag als gecorrigeerd gemarkeerd. Het oude JSON-bewijs is ongewijzigd behouden.
Gesimuleerde FAIL-scenario's (resources onder de grens, schijf, kernel en opslag)
blijven FAIL geven: deze zijn geslaagde regressietests.

## Bestanden en veiligheidsgrenzen

Gewijzigd in deze iteratie:
- `infrastructure/installer/preflight.py`
- `tests/test_preflight.py`
- `docs/workpackages/WP-001.md`
- `docs/installer/ARCHITECTURE.md`
- `docs/installer/ITERATION-1-RESULTS.md` (correctienotitie)

Toegevoegd:
- `docs/installer/ITERATION-2-RESULTS.md` (dit verslag)
- [APP JSON](evidence/iteration-2-app.json)
- [DB JSON](evidence/iteration-2-db.json)
- [APP-DB JSON](evidence/iteration-2-app-db.json)

Geen sudo uitgevoerd, wachtwoord gevraagd, netwerkverbinding gemaakt,
TEST-O-toegang, installatie, systeemwijziging, commit of push. Alle writes,
inclusief tijdelijke testbestanden, bleven binnen de repository. Oplevering
was deels al ongetrackt bij aanvang; niets gestaged.
