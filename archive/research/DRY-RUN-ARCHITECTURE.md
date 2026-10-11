> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# WP-002 — Offline dry-run architectuur

Iteratie 1/3, 2026-10-10. Python-stdlib, uitsluitend lokale simulatie.
Het [plancontract](PLAN-CONTRACT.md) en zijn OPEN besluiten blijven geldig.
Er bestaat geen echte executor, adapter, vrije commandpayload, shellhook,
sudo-pad of netwerkclient. Er is geen live modus of enable-vlag.

## Declaratief contract

`build_dry_run(evidence, simulation_target)` roept alleen de pure WP-001
planbuilder aan. Invoer is bestaand schema-2-bewijs of fictieve testdata;
er worden geen preflightprobes gestart. Een target is een begrensd fictief
label, geen hostidentiteit. Het volledige reviewcontract blijft in het resultaat.
`installation_authorized=false` en `executable=false` gelden altijd.

APP: `review → app.prepare → app.validate → final-review`.
DB: dezelfde structuur met DB. APP-DB bevat beide onafhankelijke roletakken;
de slotreview hangt af van beide validatiestappen. De huidige deterministische
volgorde is APP vóór DB; er wordt geen onbewezen echte APP→DB-afhankelijkheid
opgelegd. Werkelijke stack- en verbindingsafhankelijkheden blijven OPEN.

Elke stap heeft een uniek ID, eerder gedeclareerde afhankelijkheden,
expliciete privilegecategorieën, PRE/POST en uitsluitend `describe-only`.
Voorbereiding beschrijft scoped package/account/directory/config/service-rechten.
Review/validatie beschrijven lokale of toekomstige onafhankelijke controle.
Geen recht wordt verleend, getest of gebruikt. PRE/POST worden beschreven,
niet operationeel geëvalueerd. Preflight-FAIL maakt een taak BLOCKED; WARN/OPEN
mag alleen worden gesimuleerd. Simulatiesucces sluit geen OPEN besluit.

Canonical JSON/SHA-256 bindt het volledige plan inclusief inputbewijs,
targetlabel, reviewcontract en stappen. Stapkeys binden plan-ID plus volledige
stapinhoud. Wijziging van input, target of declaratie geeft een nieuwe identiteit.
De validator weigert onbekende stapvelden, uitvoeringsvlaggen, foutieve hashes,
duplicaten, ontbrekende privilegecategorieën en voorwaartse/cyclische dependencies.
Hashes bewijzen geen authenticiteit of goedkeuring. Een gewijzigde plan-ID is
een afzonderlijke simulatie; dit voorkomt geen dubbele echte hostmutaties.

## Journal en taakstatus

`Journal(directory, create=True)` maakt exclusief een eigen directory onder
`logs/wp002/` (mode 0700). Een bestaande directory wordt niet geadopteerd.
Reopen gebruikt `create=False`, bestaand SQLite-bestand, application-ID,
schemaversie en quick-check. Andere bestemmingen, symlinks en bestaande
evidencepaden worden geweigerd. `close()` sluit expliciet de verbinding.
Geen CLI of automatische scan/herstel bij openen.

SQLite gebruikt `BEGIN IMMEDIATE` en `synchronous=FULL` met het standaard
rollbackjournal. Elke statusverandering en bijbehorende event worden samen
gecommit; bij exception volgt rollback. Events hebben oplopende globale cursor,
taak-ID, UTC-tijd, event, stap en begrensde code. Het oorspronkelijke plan wordt
opgeslagen. Geen vrije exceptiontekst, credentials of uitvoerpayloads in events.
Het volledige inputbewijs kan wel brondata bevatten: gebruik uitsluitend
gesanitiseerde lokale evidence. Snapshot is JSON-serialiseerbaar en bevat
events, plan-ID en permanent uitgeschakelde uitvoeringsvlaggen.

| Status | Betekenis / overgang |
| --- | --- |
| PENDING | Nieuw of expliciet hersteld; `start` geeft RUNNING |
| BLOCKED | Preflight-FAIL; start en recovery geweigerd |
| RUNNING | Alleen huidige sessie mag één volgende stap simuleren |
| INTERRUPTED | Expliciet onderbroken; geen automatische voortgang |
| FAILED | Fictieve foutcode vastgelegd; dependencies worden niet vervolgd |
| SIMULATED | Alle stappen uitsluitend gesimuleerd; terminal, geen installatiebewijs |

`create_task` retourneert voor dezelfde plan-ID dezelfde taak zonder nieuwe
events, ook na herstart. `advance` schrijft maximaal één stap en slaat reeds
gesimuleerde stappen over. Dubbel starten, doorgaan na terminale status en
onbekende taken worden geweigerd. Geen retries op de achtergrond.

Een herstart behoudt RUNNING als onzekere opgeslagen toestand. De nieuwe sessie
mag daarop niet doorgaan. `recover(..., review_acknowledged=True)` registreert
bij RUNNING eerst INTERRUPTED en vervolgens RECOVERY_REVIEWED, en zet PENDING.
FAILED/INTERRUPTED vereisen dezelfde expliciete review. Daarna kan een nieuwe
`start` vanaf het eerste onvoltooide checkpoint verder. Het oude sessietoken
wordt ingetrokken; een oude verbinding kan niet meer schrijven als owner.
De boolean is uitsluitend een offline reviewbevestiging, geen RBAC/MFA of GO.
Er is geen herstel van remote-effecten, rollback of snapshotrestore.

## Grenzen en vervolg

De tests bewijzen lokale transactionaliteit, reopen, session fencing en
simulatie-idempotentie. Geen stroomuitval-, fysieke disk-/filesystemfout- of
remote-effectacceptatie. SQLite-duurzaamheid blijft afhankelijk van filesystem
en storage. Het journal is lokaal wijzigbaar: geen WORM, externe auditautoriteit
of cryptografische eventketen. Parentdirectory-races door een kwaadwillige lokale
actor, quotas, retentie, bounded totale taakgrootte en workerhealth zijn niet
opgelost. Geen distributed locks, leases, remote fencing of productieautorisatie.

Eventuele iteraties 2/3 moeten expliciet begrensd worden; deze oplevering start
ze niet. Echte uitvoering blijft een afzonderlijk besluit met exact target,
release, least privilege, onafhankelijke validatie en herstelvoorbereiding.
De twee installaties met gebruikersrestore uit de baseline blijven NOT TESTED.

## Aanvulling iteratie 2/3 — persistente lokale recovery

2026-10-10. Deze aanvulling vervangt de schema-/integriteitsbeschrijving van
iteratie 1; de declaratieve stappen, API voor taakvoortgang en uitvoeringsgrens
blijven behouden. Nieuwe journals gebruiken SQLite user_version 2.

Elke taak heeft een SHA-256-seal over taak-ID, plan-ID, volledig plan, status,
owner en alle geordende events inclusief cursor en timestamp. Openen en iedere
transactie controleren alle seals, planbindingen en orphan-events vóór gebruik.
Status, events en gewijzigde seals worden in dezelfde BEGIN IMMEDIATE/FULL
transactie opgeslagen. Afwijkingen blokkeren lezen, schrijven en recovery;
er is geen automatisch repareren of opnieuw baselinen van een schema-2-journal.
De seals detecteren wijzigingen zonder bijbehorende checksumaanpassing, maar
zijn lokaal herschrijfbaar: geen authenticiteit, WORM of onafhankelijke head.
Ook volledige rollback naar een oudere consistente database is niet detecteerbaar.

Schema-1-journals worden standaard geweigerd. Alleen
`Journal(path, approve_legacy_upgrade=True)` mag na menselijke review expliciet
schema 1 transactioneel naar schema 2 omzetten. Dit behoudt taak-ID, events,
status en checkpoints; het valideert plannen en orphan-events. Het legt een
baseline van de aanwezige bytes vast en bewijst **geen** historische integriteit.
Geen automatische upgrade, herstel of taakstart. Nieuwe schema-2-corruptie kan
niet via deze vlag worden omzeild.

Binnen één journal kan maximaal één taak per fictief target RUNNING zijn,
ook voor verschillende plannen. De claim en STARTED zijn transactioneel;
gelijktijdige starters leveren één owner op. Een oud sessietoken wordt door
expliciete recovery ingetrokken. Dit is geen claim over meerdere journals of
remote hosts. SQLite-locks zijn begrensd door de standaard busy-timeout (5 s).

Verbindingsverlies, procesuitval en serverherstart laten het laatste duurzame
checkpoint staan. Reopen verricht geen voortgang. RUNNING blijft onzeker en
mag door de nieuwe sessie niet worden vervolgd. Alleen literal
`review_acknowledged=True` registreert review en zet PENDING; een afzonderlijke
`start` is daarna nodig. Reeds SIMULATED stappen worden overgeslagen. Een
onvoltooide stap wordt uitsluitend na die review weer gesimuleerd. Een bool
is een offline menselijke bevestiging, geen bewijs van actoridentiteit/RBAC/MFA.
Er zijn geen remote-effecten waarvan herstel of heruitvoering wordt toegestaan.

Tests beëindigen lokale Python-fixtureprocessen abrupt vóór commit en na commit,
inclusief SQLite rollback-journalherstel, en injecteren fouten na status/event/
sealwrites. SSH-verbreking en reboot worden alleen door close/reopen gemodelleerd;
geen echte SSH, serverreboot, stroomuitval of storagehardwaretest. Integriteits-
controle scant alle taken/events; schaalbaarheid, quota, retentie en kwaadwillige
pad-/schema-aanpassing blijven buiten deze iteratie.

## Afronding iteratie 3/3 — onzeker target blijft geblokkeerd

2026-10-10. Binnen hetzelfde journal blokkeren nu RUNNING, INTERRUPTED én
FAILED een andere taak voor hetzelfde fictieve target. Alleen duurzaam
vastgelegde `RECOVERY_REVIEWED` na literal `review_acknowledged=True` zet de
onzekere taak PENDING en heft deze blokkering op. De review en statuswijziging
blijven één transactie; een gedeeltelijke write of procesuitval vóór commit
laat geen toestemming achter. Een afzonderlijke `start` blijft verplicht.
Geen locktimeout, vrijgekomen OS-lock, reopen of verstreken tijd geldt als
menselijke goedkeuring. Een corrupt journal blijft geheel geweigerd, ook met
review of legacy-upgradegoedkeuring; die flags zijn geen reparatiebevoegdheid.

Initialisatiefouten sluiten nu altijd de SQLite-verbinding, inclusief fouten
bij PRAGMA/schema-inspectie van een afgekapt bestand. Er is geen retrylus,
achtergrondworker of automatische herstelactie toegevoegd. SQLite kan bij
openen zijn eigen onafgemaakte rollbacktransactie terugdraaien; dat is herstel
naar het laatste checkpoint, geen taakretry of toestemming om door te gaan.

De afsluitende tests gebruiken twee zelfstandige Python-processen (`spawn`)
voor één claim, abrupte procesuitval tijdens review en een proces dat zijn
SQLite-writerlock met `os._exit` achterlaat. Afgekapt databasebestand en orphan-
events worden op eigen wegwerpjournals getest. Eerdere proeven voor uitval
vóór/na stapcommit, status/event/sealrollback, sessiefencing en close/reopen
blijven onderdeel van de suite. Serverherstart blijft uitsluitend een lokaal
reopenmodel; echte reboot, stroomuitval en remote-effecten zijn onbewezen.

WP-002 eindigt bij iteratie 3/3 als offline dry-run. Het menselijke reviewevent
is een lokale API-bevestiging zonder geauthenticeerde actor; alle eerder
benoemde trust-, opslag-, pad-, schaal- en operationele grenzen blijven gelden.
Zie [eindresultaat en acceptatieadvies](WP-002-ITERATION-3-RESULTS.md).
