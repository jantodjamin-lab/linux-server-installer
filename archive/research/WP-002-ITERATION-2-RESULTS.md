> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# WP-002 — Resultaat iteratie 2 van maximaal 3

2026-10-10 UTC. **PASS lokale dry-run recovery / WARN operationele bewijsgrens**.
Iteratie 3 is niet gestart. Gelezen: Ramin V2 Knowledge Baseline, WP-002,
DRY-RUN-ARCHITECTURE, resultaat iteratie 1, huidige Python-code en tests.

## PASS

`python3 -B -m unittest discover -s tests`: **44/44 geslaagd**, exit 0,
0 fouten, 0 mislukkingen, 0 skips. Dit zijn de 37 bestaande tests en 7 nieuwe
unieke tests; geen dubbeltelling of wijziging van de bestaande tests.

| Controle | Gerichte test / resultaat |
| --- | --- |
| Persistente checkpointrecovery na abrupte procesuitval | `test_process_loss_before_and_after_commit`: subprocess-fixture verlaat Python met exit 23 vóór commit en na commit; reopen behoudt alleen duurzame stappen; iedere stap uiteindelijk één keer SIMULATED |
| Atomaire status, events en integriteitsseal | `test_seal_write_failure_rolls_back_status_and_history`: fictieve opslagfout na sealwrite rolt alle wijzigingen terug; bestaande eventfouttest behouden |
| Journal-integriteit | `test_corruption_blocks_reads_mutations_and_recovery`: gewijzigde status, owner, plan-ID, eventcode, verwijderde events of seals blokkeren snapshot/advance/recovery en reopen |
| Dubbele creatie, targetclaim en lockcontention | `test_two_connections_duplicate_and_target_claim`: identieke planbytes geven dezelfde taak; tweede RUNNING-plan op hetzelfde target geweigerd; SQLite-writerlock geeft begrensde fout |
| Werkelijk gelijktijdige lokale starters | `test_simultaneous_starts_have_one_owner`: twee threads met eigen verbindingen; één owner, één STARTED, één SIMULATED |
| Verbindingsverlies / rebootmodel en menselijke recoveryreview | `test_disconnect_and_restart_need_literal_human_ack`: close/reopen; False/None/1/tekst geweigerd; review alleen maakt PENDING, geen voortgang zonder start |
| Bestaande journals behouden via expliciete upgrade | `test_legacy_upgrade_is_explicit_and_preserves_checkpoints`: schema 1 standaard geweigerd, expliciete upgrade behoudt identiteit/events/checkpoint en vereist daarna afzonderlijke recoveryreview |

Alle bestaande profiel-, dependency-, privileges-, failure-, idempotency-,
path-, session-fencing-, plan- en preflighttests blijven slagen.
De eerste nieuwe testuitvoering vond een fixturefout: opnieuw gegenereerd
preflightbewijs kan een andere timestamp en dus andere plan-ID hebben.
De duplicaatproef gebruikt nu dezelfde planbytes; de planbinding is behouden.

## WARN

SSH-verbreking en serverherstart zijn lokale close/reopen-modellen, geen echte
remote proeven. Abrupte Python-procesuitval is daadwerkelijk lokaal getest;
geen fysieke reboot, stroomuitval of storagehardwareacceptatie.

Seals zijn lokaal herschrijfbare checksums, geen externe auditautoriteit,
cryptografische actoridentiteit of bescherming tegen consistente database-rollback.
Schema-1-upgrade vereist expliciete menselijke baselinegoedkeuring en bewijst
geen integriteit van de oude historie. Boolean review is uitsluitend een offline
bevestiging, geen RBAC/MFA of installatie-GO. Targetclaims gelden binnen één
journal; geen distributed of remote fencing. Volledige integriteitsscan per
transactie is niet op operationele schaal getest. Quota/retentie en kwaadwillige
parentdirectory-races blijven open.

## FAIL

Geen gefaalde tests in de definitieve suite. Injecties en geweigerde acties
zijn verwachte veiligheidsuitkomsten. Geen operationele installatieacceptatie
of GO; geen automatische heruitvoering van onzekere stappen.

## Bestanden en veiligheidsgrenzen

Gewijzigd: `infrastructure/installer/dry_run.py` en
`docs/installer/DRY-RUN-ARCHITECTURE.md` (iteratie-2-aanvulling).
Toegevoegd: `tests/test_dry_run_recovery.py` en dit resultaatverslag.
Bestaande tests, iteratie-1-resultaat en WP-002-opdrachttekst ongewijzigd.

Geen echte executor, installatie, shelluitvoering vanuit de architectuur,
sudo, netwerkactie, TEST-O, commit of push. Lokale ontwikkelcommando's uitsluitend
voor lezen, bewerken en testen; childprocessen uitsluitend Python-faultfixtures.
Tijdelijke journals onder `logs/wp002/` zijn na tests verwijderd.
References en bestaande evidence/verslagen blijven strikt read-only.

Integriteitsverificatie: SHA-256 van alle 460 vooraf vastgelegde beschermde
bestanden ongewijzigd, inclusief 444 referencebestanden buiten `.git` en
bestaande evidence/RESULTS-verslagen. De referencebestandenset buiten `.git`
is gelijk; interne Git-metadata valt buiten deze inventaris. `git diff --check`
en aanvullende whitespacecontrole van de vier gewijzigde/nieuwe bestanden:
PASS. Bestanden uit iteratie 1 stonden al ongetrackt; niets gestaged.
