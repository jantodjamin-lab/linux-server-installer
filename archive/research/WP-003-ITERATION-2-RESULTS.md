> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# WP-003 — resultaat iteratie 2/3

2026-10-10 UTC. **PASS offline oplevering; WARN operationele bewijsgrenzen;
geen GO-1/GO-2/GO-3.** Er resteert maximaal één ontwikkeliteratie.

Eerst gelezen: [leidende eisen](../workpackages/WP-003-ORIGINAL-REQUIREMENTS.md),
[WP-003](../workpackages/WP-003.md), [iteratie 1](WP-003-ITERATION-1-RESULTS.md),
kennisbaseline, WP-001/WP-002-documentatie, architectuur, plancontract en
iteratieresultaten. De oorspronkelijke bron is nu beschikbaar; de historische
melding over ontbreken is behouden en in het werkpakket expliciet gecorrigeerd.

## Volledige bronvergelijking

| Broneis | Status deze ontwikkeliteratie / bewijs | Resterende grens |
| --- | --- | --- |
| Doel: één echte persistente swapinstallatiestap | PASS voorbereiding typed stap; WARN echte installatie | Geen echte installatie geclaimd |
| Afzonderlijke GO-1/2/3 | PASS werkpakket en swapcontract | Geen toestemming verleend |
| A: SSH/stdin vanaf APP-O, strict pin, onafhankelijke verificatie, geen TOFU/forwarding, vaste timeouts | PASS bestaand remote proposal/tests | Transport ontbreekt; outer timeout nog niet operationeel bewezen |
| A: host/pin/provider/generatie/tijd/menselijke review; APP-O geen targetbewijs | PASS remote contract, tests, runbook | Assertions en providerrecord vereisen echte menselijke verificatie |
| A: services, sockets, poorten; onvolledig/afwijkend WARN en STOP | PASS bestaande inventory + typed complete/PASS gate | Remote assessment kan WARN bewaren; WARN verleent nooit uitvoertoestemming |
| B: interactieve sudo, mens aanwezig, geen wachtwoordverwerking/rootlogin/sudoers/NOPASSWD | PASS voorstel en fixturegate | Praktisch privilegepad ontbreekt |
| B: exacte handelingen vooraf | WARN zes begrensde operaties expliciet voorgesteld | Concrete argv/paden/methoden OPEN vóór GO-2 |
| C: grootte/vrije ruimte/pad/eigenaar/modus/fstabbackup/rollback | PASS typed contract en reviewlijst | Grootte/pad/reserve/compatibiliteit/rollback OPEN; root:root/0600/fstab liggen vast |
| C PRE: verse identiteit, geen swap/fstabconflict, ruimte, geen drift | PASS stoptests en exacte fstab/baselinebinding | Compatibiliteit en complete zijn fixtureassertions |
| C uitvoering: typed condities, idempotent, afwijking STOP | PASS enum/dataclasses/pure simulatie en tests | Geen live adapter; model bewijst geen remote idempotentie |
| C POST: actief/grootte/rechten/fstab/nevenwijzigingen/onafhankelijk | PASS afzonderlijke validator en foutinjecties | Geen onafhankelijke live collectie |
| Geen automatische retry/rollback/herstel | PASS modules zonder I/O/executor/recovery | Onzekere echte toestand later menselijk beoordelen |
| D: PRE1/POST1, menselijke restore, herverificatie, PRE2/POST2, APP-O-vergelijking | PASS voorbereide comparator/runbook | Snapshot/herhaalbaarheid niet uitgevoerd |
| D: alleen vooraf benoemde vluchtige velden normaliseren | PASS expliciete allowlist; configuratie/versietest | Ruwe evidence/GO/snapshotcompleetheid menselijk reviewen |
| D: meerdere dagen zonder extra ontwikkeliteratie | PASS bron behouden; runbook geen tijdgebonden live claim | Operationele dagen zijn geen vierde ontwikkeliteratie |
| Alle stopcondities en acceptatiegrenzen | PASS gates en documentatie | Preflight-WARN/incompleet stopt; geen operationele PASS |
| WP-001/002 behouden, geen generieke installer/journal/Task Manager-uitbreiding | PASS geen wijzigingen aan deze code in iteratie 2 | Bestaande SQL-correctie uit iteratie 1 behouden |
| Bewijsgrenzen: sudo, restore, reboot, belasting, rollback, authenticiteit | WARN expliciet behouden | Lokale hashes bewijzen geen authenticiteit |

## Zes technische verbeterpunten — actuele bron

| Punt | Status | Bevinding / correctie |
| --- | --- | --- |
| 1 Journal.start SQL quotes | PASS | `state IN ('RUNNING','INTERRUPTED','FAILED')`; id parametergebonden. Dubbele Python-delimiter is geen dubbele SQL-stringquote. Iteratie-1-fix aanwezig, dry_run.py nu niet gewijzigd. |
| 2 Architectuur iteratiekop | PASS | Verouderde 2/3-kop gewijzigd naar afgeronde 3/3 en introductie gecorrigeerd. |
| 3 references in gewone clone | PASS | README vermeldt lokale, genegeerde archieven, ontbrekende links in GitHub-clone en geen runtime/testafhankelijkheid. |
| 4 Dubbele ignore-regel | PASS | Tweede `/references/`-regel verwijderd; archieven blijven uitgesloten. |
| 5 Testcommando repository-root | PASS | README expliciet rootcommando; architectuur had dit al. Geen projectconfig nodig. |
| 6 RAM 843 MiB | WARN | preflight.OTEST_MINIMUM is 843; WP-001 noemt dit expliciet toegestaan O/TEST-beleid. Iteratie-2-metingen tonen APP-O 843,0625 MiB. De gekozen grens sluit daarop aan, maar primaire onafhankelijke sizingonderbouwing/afleidingsbesluit ontbreekt. Niet als universeel minimum beschouwen; beleid niet gewijzigd. |

## Tests en controles

Definitieve volledige suite vanuit repository-root:
`python3 -B -W error::ResourceWarning -m unittest discover -s tests`:
**60/60 PASS**, 4,544 s, exit 0, 0 fouten, 0 mislukkingen, 0 skips.
54 bestaande + 6 nieuwe unieke tests; subscenario's niet dubbel geteld.
Uitsluitend fictieve swapwaarnemingen; geen live collector, swapfile of sudo.

Nieuwe tests: pure transitie en idempotentie (subprocess/socket geblokkeerd),
PRE-stopcondities, partiële installatie zonder retry, onafhankelijke POST met
foutinjecties, twee-runvergelijking met behouden versieverschillen, ongeldige/OPEN
planwaarden. Geen installatie- of systeemcommando uitgevoerd.

`git diff --check` na verwijderen overtollige lege ignore-regel PASS.
Historische archieven, bestaande evidence en eerdere resultaatverslagen via
vooraf opgenomen SHA-256-manifest en bestandenset gecontroleerd: ongewijzigd.
Nieuwe documentlinks en whitespace rechtstreeks gecontroleerd, ook untracked files.

## Risico’s en GO-advies

**WARN**: swapcollector/live adapter, sudo-argv/aanmaakmethode/fstabwriteprocedure,
filesystem-/mountbewijs, echte onafhankelijke POST, actuele identity/provider/pin,
freshnessbeleid, releasefreeze, grootte/pad/reserve/backup-/rollbackbesluiten en
snapshotbewijs ontbreken nog. Python 3.10+ vereist voor nieuwe typed modules;
WP-001-preflight houdt zijn eigen compatibiliteitsgrens. Fixtureassertions en
GO-references zijn geen actorautorisatie. Evidence is lokaal herschrijfbaar.
Geen rebootpersistentie, swapbelasting, praktische rollback of praktische sudo
bewezen; semi-handmatige sudo blijft later een expliciete beperking.

**FAIL**: geen gefaalde definitieve test of genegeerde stopconditie. Fictieve
FAIL/STOP-scenario's zijn verwachte geslaagde controles. Ontbrekende operationele
evidence krijgt geen PASS. Een mislukte echte POST of onverwachte wijziging
betekent later FAIL en STOP, zonder automatische herstelactie.

**GO-advies: accepteer uitsluitend de offline voorbereiding voor review. Nog
geen GO-1**, omdat concrete identiteit/pin/provider, collectorrelease,
freshness-/WARN-review en evidencebeheer eerst moeten worden ingevuld.
GO-2 blijft apart na verse complete PRE en concrete sudo-/swap-/rollbackreview;
GO-3 apart na menselijke snapshotrestore en herverificatie. Twee echte
installaties met complete onafhankelijke POST zijn vereist voor operationele
swap-PASS; dat bewijst geen universele installer of productiegeschiktheid.

Toegevoegd: swap_step.py, swap_validation.py, test_swap_step.py, SWAP-CONTRACT.md
 en dit verslag. Gewijzigd: README, .gitignore, ARCHITECTURE en actuele aanvulling
in WP-003. Eerdere ongetrackte bestanden en SQL-correctie behouden. Geen SSH,
netwerk, TEST-O, sudo, installatie, swapwijziging, rollback/retry, commit of push.
