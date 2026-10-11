> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# WP-003 — resultaat iteratie 3/3

2026-10-10 UTC. **PASS offline voorbereiding; WARN operationele gereedheid.**
Geen GO-1, GO-2 of GO-3 verleend. Dit is de laatste ontwikkeliteratie.

## Scope en wijzigingen

Gelezen: WP-003, oorspronkelijke eisen, TEST-O-IDENTITY, remote_preflight.py,
preflight.py, swap_step.py, swap_validation.py en bestaande tests. Bestaande
wijzigingen uit eerdere iteraties behouden; geen archiefcode of credentials gebruikt.

| Controle | Resultaat | Bewijs / beperking |
| --- | --- | --- |
| SSH-authenticatie | PASS offline | `-F /dev/null`, `IdentitiesOnly=yes`, absolute publieke sleutel `/home/appo-admin/.ssh/id_ed25519_ramin_v2.pub`, expliciete `IdentityAgent=/run/user/1000/openssh_agent`. Paden uit lokale SSH-config/public-key-bestandsnaam; geen privésleutel gelezen of agent benaderd. |
| Hostkey | PASS offline | Uitsluitend `/home/appo-admin/ramin-control-panel-v2/infrastructure/ssh/test-o_known_hosts` in adapter; exacte ED25519-wirekeycontrole en SHA256:IwugsqszZLcsMjve5+ZLja/HaSe7ORMbc9ciWb354tg overeenkomstig onafhankelijke consoleverklaring in TEST-O-IDENTITY. Geen nieuwe consoleverificatie geclaimd. |
| Beperkte adapter | PASS offline | Vaste opnieuw opgebouwde argv/payload, wijzigingscontrole, `shell=False`, één poging, 90 s gedeelde deadline, maximaal 1 MiB per stdout/stderr. Beide pipes simultaan gelezen; timeout/overflow beëindigt proces en bewaart begrensd foutbewijs. Geen CLI of automatisch vervolg. |
| Remote metingen | PASS | Payload bevat collector, geen evaluator/evidencewriter. JSON met nonce, identiteit, timestamp, observations/errors. APP-O evalueert eigen beleid en bewaart bewijs; afwijkende envelop stopt. |
| GO-binding | PASS model / WARN autorisatie | Adapter vereist apart actor/reference/scope/target/payloadhash/tijdrecord. Recordvelden bewijzen geen menselijke autorisatie; fixture-GO's bestaan alleen in tests. |
| Swapreview | PASS offline | Pure typed model zonder executor behouden. POST vereist nu ook geldige schone PRE en exacte gemodelleerde vrije-ruimtedelta; afwijking stopt. Praktische filesystemallocatie/concurrente schijfruimteverandering vergt review vóór een live validator. |
| Veiligheidsgrenzen | PASS | Geen verbinding, sudo, echte swapinstallatie, sleutel/systemd-wijziging, commit, push of automatische GO. |

`prepare` blijft een pure fixture/proposalbouwer; alleen `test_o_proposal` plus
`run_preflight` vormt het beperkte TEST-O-pad. Adapter leest pin opnieuw vóór
uitvoering. Lokale bestandswijzigingsrace door een kwaadwillige APP-O-actor wordt
niet uitgesloten; APP-O/evidence-directory is geen onafhankelijke trustanker.

## Offline tests

Vanuit repository-root:
`python3 -B -W error::ResourceWarning -m unittest discover -s tests`.
Definitieve suite: **65 tests PASS**, geen fouten, mislukkingen of skips.
`git diff --check`: **PASS**.

`ssh -G` is uitsluitend configuratie-expansie zonder verbinding en bevestigt
identiteitsselectie, agent, absolute pin, strikte hostkeycontrole en geen forwarding.
Fake runner test exit 255, timeout, uitvoeroverschrijding, bewijsopslag en exact één
oproep. Negatieve tests blokkeren gewijzigde argv/stdin/pin, andere host en ontbrekende
GO vóór runneraanroep. Begrensde runner getest met uitsluitend lokale Python-processen:
stdoutlimiet, timeout en stdin/stdout/stderr. Bestaande tests controleren nonce,
freshness, identiteit, rootcontext, malformed JSON en opslaggrenzen. Swaptests
controleren PRE/POST, drift, partiële toestand, idempotentie en restorevergelijking.
Geen fake of APP-O-meting geldt als TEST-O-bewijs.

**FAIL:** geen definitieve test gefaald en geen verboden handeling uitgevoerd.
Verwachte FAIL-evidence uit negatieve tests is geslaagde veiligheidsvalidatie.

## GO-1-advies en resterend werk

**WARN — nog geen onvoorwaardelijk positief GO-1-advies.** Identiteit/pin en
transportvoorstel zijn reviewbaar. Actuele boot-ID en provider/snapshotgeneratie
ontbreken nog; `review-needed` is uitsluitend een fixture, geen operationele identiteit.
Vóór GO-1: menselijke bevestiging van die velden, verificatierecord/reviewer/tijd,
profiel/freshnessbeleid, exacte bevroren payload/release en afzonderlijk GO-record.
Agentontgrendeling en praktische keyauth zijn niet in deze iteratie getest.
Geen verdere ontwikkeliteratie ingepland; operationele review/uitvoering mag later
alleen binnen afzonderlijk expliciet verleende toestemming plaatsvinden.

Preflight-WARN/incompleet/afwijking betekent STOP en menselijke review; de huidige
beleidsevaluator bevat bewust WARN's voor niet bewezen SSH/sudo en ontbrekende swap.
PASS of een ingevuld GO-record is nooit automatische toestemming voor installatie.

GO-2 blijft afzonderlijk: grootte, pad, reserve, filesystem/mountbewijs, concrete
interactieve sudo-handelingen, fstabbackup/writeprocedure en rollback moeten worden
beoordeeld, gevolgd door verse PRE en onafhankelijke POST. GO-3 volgt uitsluitend
na menselijke snapshotrestore en herverificatie. Twee echte installaties,
rebootpersistentie, belasting, praktische sudo/rollback en evidence-authenticiteit
buiten APP-O blijven onbewezen. RAM-beleid 843 MiB en overige zes verbeterpunten
houden de status uit iteratie 2; geen extra journal/Task Manager-uitbreiding.

Werk stopt na dit rapport.
