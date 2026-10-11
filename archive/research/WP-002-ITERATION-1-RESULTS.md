> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# WP-002 — Resultaat iteratie 1 van maximaal 3

2026-10-10 UTC. **PASS lokale oplevering / WARN operationele bewijsgrens**.
WP-002 eerst aangemaakt, vervolgens architectuur, Python-implementatie en tests.
Iteraties 2 en 3 niet gestart; WP-001 blijft afgerond bij 3/3.

Gelezen: Knowledge Baseline, SOURCE_REGISTER (bronstatus en inventaris), WP-001,
PROJECT_BASELINE, PLAN-CONTRACT, alle drie eerdere resultaatverslagen en huidige
plan/preflight-code en tests. Historische archiefcode niet uitgevoerd/overgenomen.

## PASS

`python3 -B -m unittest discover -s tests -v`: **37/37 geslaagd**, exit 0,
0 fouten, 0 mislukkingen, 0 skips. Daarvan 10 nieuwe dry-run-tests en 27 bestaande
WP-001-tests. Nieuwe controles:

| Eis | Unit-test / bewijs |
| --- | --- |
| APP/DB/APP-DB, dependencies, rechten, geen acties | `test_profiles_order_privileges_and_no_actions`; collect/subprocess/netwerksocket geblokkeerd |
| Stabiele plan-/stapidentiteit | `test_binding_determinism_and_no_input_mutation` |
| Dubbele creatie/uitvoering geweigerd | `test_duplicate_creation_and_completion` |
| Onderbreking en expliciete recovery | `test_interruption_requires_review_and_preserves_completed_steps` |
| Reopen en intrekken oude sessie | `test_restart_recovery_and_stale_owner_fencing` |
| Foutstatus blijft bestaan; geen blinde retry | `test_failure_is_durable_and_retry_is_explicit` |
| State/event atomair bij opslag-exception | `test_transaction_rollback_keeps_state_and_events_together` |
| Preflight-FAIL blokkeert simulatie | `test_fail_preflight_blocks_simulation` |
| Payload/hash/dependencyvalidatie | `test_invalid_payloads_bindings_and_dependency_cycles` |
| Beschermde paden, exclusieve creatie, symlinks | `test_protected_paths_existing_files_and_symlinks_rejected` |

Transactioneel SQLite-journal met UTC-events, planbinding, herstelbare status
en lokale sessiecontrole. Alle writes van simulaties/tests in eigen tijdelijke
directories onder `logs/wp002/`; teststores na afloop verwijderd.
Geen bestaande evidence als schrijfbestemming gebruikt.

Integriteitscontrole: 481 vooraf geïnventariseerde bestanden ongewijzigd,
waaronder alle 444 referencebestanden; ook de referencebestandenset bleef gelijk.
Alle bestaande evidence-JSON's leesbaar. Links en whitespace van de vijf nieuwe
bestanden gecontroleerd: PASS. `git diff --check`: PASS; de nieuwe bestanden
zijn ongetrackt en daarom aanvullend rechtstreeks gecontroleerd. Gitstatus
toont uitsluitend de vijf nieuwe bestanden; niets gestaged.

## WARN

Geen live installatie of operationeel herstelbewijs. Privileges/PRE/POST zijn
declaraties; OPEN stack/target/release/backupbesluiten blijven behouden.
SIMULATED betekent uitsluitend fixturevoortgang. Geen echte hostidentiteit,
MFA/RBAC, sudo-autorisatie, worker, remote fencing of exact-once-effectgarantie.
Reopen/rollback zijn getest; echte proceskill/stroomuitval/storage-uitval niet.
Journal is lokaal herschrijfbaar en kent geen quota/retentie of externe audit.
Pathchecks beschermen normale escapes, niet kwaadwillige parentdirectory-races.
Zie [architectuur](DRY-RUN-ARCHITECTURE.md) voor alle bewijsgrenzen.

## FAIL

Geen gefaalde tests of aangetoonde afwijkingen in de uitgevoerde controles.
De fictieve FAILED/BLOCKED-scenario's zijn verwachte, geslaagde veiligheidsproeven.
Operationele installatieacceptatie krijgt geen PASS of GO.

## Bestanden en veiligheidsgrenzen

Uitsluitend toegevoegd:

- `docs/workpackages/WP-002.md`
- `infrastructure/installer/dry_run.py`
- `tests/test_dry_run.py`
- `docs/installer/DRY-RUN-ARCHITECTURE.md`
- `docs/installer/WP-002-ITERATION-1-RESULTS.md`

Geen echte executor, uitvoerende shellpayload, sudo, netwerkactie, TEST-O,
installatie, SSH-configwijziging, commit of push. Lokale ontwikkelcommando's
dienden alleen lezen, nieuwe code/docs schrijven en unit-tests/verificatie.
