> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# WP-003 — resultaat iteratie 1/3

2026-10-10 UTC. **PASS offline voorbereiding / WARN ontbrekende opdrachtbron en
operationele dekking / geen GO-1**. Maximaal twee WP-003-iteraties resteren.

## Gelezen grondslag

[PROJECT_BASELINE](../PROJECT_BASELINE.md),
[kennisbaseline](../knowledge/RAMIN_V2_KNOWLEDGE_BASELINE.md),
[WP-001](../workpackages/WP-001.md), [WP-002](../workpackages/WP-002.md),
WP-001-rapporten [1](ITERATION-1-RESULTS.md), [2](ITERATION-2-RESULTS.md),
[3](ITERATION-3-RESULTS.md), WP-002-rapporten
[1](WP-002-ITERATION-1-RESULTS.md), [2](WP-002-ITERATION-2-RESULTS.md),
[3](WP-002-ITERATION-3-RESULTS.md), plancontract, provisioninglog en actuele
preflight-/plan-/dry-runbroncode en tests. Eindrapporten bevatten technische
acceptatieadviezen; geen afzonderlijke gebruikersacceptatie afgeleid.

## PASS

- [WP-003](../workpackages/WP-003.md) aangemaakt met voorlopige fasen A–D,
  afzonderlijke GO-1/GO-2/GO-3, stopcondities, sudo-beleid en OPEN swapkeuzes.
- Nieuwe [remote voorbereiding](../../infrastructure/installer/remote_preflight.py):
  geen SSH-executor; uitsluitend voorstel met vaste argv en stdin, exacte
  ED25519-pincontrole, vereist onafhankelijk verificatierecord, niet-root target,
  nonce/identity/freshnesschecks en hergebruik van bestaande semantische
  preflightvalidatie. Ook fout-/FAIL-evidence blijft beschikbaar en opslaanbaar.
- Bewijsopslag uitsluitend in een nieuwe eigen directory onder `logs/wp003/`
  op APP-O; exclusieve creatie, symlinkweigering, 0700/0600 en file-fsync.
- `dry_run.py`: uitsluitend één SQL-quote-correctie, stringwaarden RUNNING,
  INTERRUPTED en FAILED nu met SQL-enkele quotes. Geen architectuuruitbreiding.
- Definitieve suite: `python3 -B -W error::ResourceWarning -m unittest discover -s tests`:
  **54/54 PASS**, exit 0, 0 fouten, 0 mislukkingen, 0 skips (4,829 s).
  49 bestaande en 5 nieuwe unieke testmethoden; subscenario's niet dubbel geteld.
- Nieuwe [offline tests](../../tests/test_remote_preflight.py): pure proposal
  onder geblokkeerde subprocess/netwerksocket, payloadsyntax zonder uitvoering,
  pin/onafhankelijke verificatie, target-/nonce-/root-/profielafwijzing,
  timestamp/freshness/exitfouten, sorted-JSON probe-errorroundtrip, preflight-FAIL,
  raw failure retention, private opslag, overschrijven/escape/symlinkweigering.
  Alleen fictieve hostname/key/identiteiten/waarnemingen, geen live collector-run.
- `git diff --check` PASS; nieuwe bestanden daarnaast rechtstreeks op whitespace
  en documentlinks gecontroleerd. Bestaande baselines, referencecode/evidence,
  eerdere rapporten, preflight.py en plan.py niet gewijzigd.

## WARN en technische verbeterpunten

**Het aangeleverde leidende WP-003-werkplan en de zes genoemde technische
verbeterpunten ontbreken in de beschikbare context en repository.** De gebruiker
is om beide teksten gevraagd. Afstemming/controle van exact die zes punten is
OPEN; deze oplevering claimt geen zes-op-zes-verificatie. Het faseplan is
voorlopig en moet tegen die bron worden gecontroleerd voordat GO-1 wordt geadviseerd.

Wel gecontroleerde actuele bronfeiten, zonder deze als vervangende lijst van
zes gevraagde punten te presenteren:

| Bronfeit | Uitkomst / actie |
| --- | --- |
| dry_run.start SQL gebruikt dubbele quotes voor stringwaarden | Kleine toegestane afwijking hersteld met enkele quotes; bestaande targetclaimregressies PASS. |
| preflight.query gebruikt vaste argv, DEVNULL, vijf seconden timeout en geen shell | Aanwezig; behouden. Geen sudo-/SSH-query toegevoegd. |
| preflight bewaart query-/timeoutdetails en parser-raw | Aanwezig; behouden en remote stdout/stderr-retentie toegevoegd in eigen module. |
| plan.build_plan valideert schema/status/policy en vergelijkt errors semantisch | Aanwezig; hergebruikt om foutdictvolgorde na sorted JSON niet als drift te behandelen. |
| dry_run blokkeert RUNNING/INTERRUPTED/FAILED-targets tot duurzame review | Aanwezig; niet uitgebreid. |
| dry_run constructor sluit verbinding bij fouten; journalpaden weigeren symlinks | Aanwezig; niet gewijzigd. |

Geen echte transport-/timeout-/agenttest, providerattestatie, onafhankelijke
fingerprintbron, operationele actorautorisatie of volledige fysieke inventory.
De verificatierecordvelden zijn menselijke assertions. De transportadapter
ontbreekt bewust: geen verbinding mogelijk vanuit deze module. Latere adapter
moet exact voorstel bevriezen, pinbestand in private werkdirectory klaarzetten,
APP-O start/receipt vastleggen, 90 s outer timeout afdwingen, partial output bewaren
en nooit automatisch retryen. Strikte hostkeyopties vervangen geen onafhankelijke
fingerprintcontrole. SSH-client/Ubuntu26.04-compatibiliteit niet live bewezen.

Bewijs is lokaal herschrijfbaar, zonder WORM of externe trustanchor. Geen
crashcomplete opslaggarantie/directory-fsync of kwaadwillige parent-racebescherming.
Freshness op basis van aangeleverde APP-O-wall-clocktijden is offline getest;
latere monotone duurcontrole en betrouwbare transporttijdregistratie vereist.
Na restore/reboot/identitydrift nieuwe verificatie en PRE. Geen twee installaties,
POST of echte restore bewezen. Read-only SSH kan OS-authenticatielogs schrijven.

## Exact voorgestelde read-only handelingen — niet uitgevoerd

Alleen na afzonderlijke GO-1, via vaste remote invocation
`env LC_ALL=C PYTHONDONTWRITEBYTECODE=1 python3 -B -`, code via SSH-stdin:

1. Lezen `/etc/os-release`, `/proc/meminfo`, `/etc/machine-id`,
   `/proc/sys/kernel/random/boot_id`.
2. Python OS/platform/socket/pwd-inventaris: kernel, CPU-count, vrije ruimte van
   `/`, hostname, account, UID/eUID, groepen; aanwezigheid van sshd/sudo via
   PATH en read-only executablechecks `/usr/sbin/sshd`, `/sbin/sshd`.
3. `systemctl list-units --type=service --all --no-pager --no-legend --plain`.
4. `systemctl list-units --type=socket --all --no-pager --no-legend --plain`.
5. `ss -H -lntu`.
6. Bestaande evaluator en één JSON-stdoutenvelop; op APP-O raw stdout/stderr,
   exitcode, target/verificatie/nonce, start-/receipt en beoordeeld rapport opslaan.

Geen sudo-opdracht, upload, packageactie, swapmutatie, fstabwrite, firewallactie,
reboot of remote bewijsbestand. Geladen services zijn geen volledige inventory;
`disk_usage('/')` vervangt geen swappad-/filesystemcompatibiliteitscontrole.

## OPEN besluiten en GO-1-advies

OPEN: leidend werkplan en zes punten; concrete providerinstance/generatie,
hostname/machine-id/boot-id en onafhankelijke fingerprintbron/reviewer;
SSH-agentselectie; vaste installer/payloadrelease; expliciet freshnessinterval en
clockbeleid; compleetkritische inventory en review van WARNs; pin-/evidencebeheer.

Voor GO-2 ook OPEN: swaptype/grootte/pad, mount/filesystemcompatibiliteit,
reservevrije ruimte, rechten, collisionbeleid, persistentie, activatie,
swappiness, interactief sudo-kanaal en begrensde handelingen, rollback en POST.
Historische 4 GiB is geen nieuw besluit. Geen passwordless-sudo-workaround.
Snapshot-ID/herstelbaarheid en twee-run-acceptatiecriteria blijven eveneens OPEN.

**GO-1-advies: nog geen GO.** Offline technische oplevering kan worden gereviewd;
inhoudelijke opdrachtdekking en concrete remote prerequisites eerst sluiten.
GO-1 mag later uitsluitend read-only PRE autoriseren. GO-2 is aparte toestemming
voor eerste echte installatiehandeling (swap). GO-3 is aparte toestemming voor
de tweede run na gebruikersrestore. Geen GO namens de gebruiker geregistreerd.

## FAIL en gewijzigde bestanden

Geen gefaalde test of aangetoonde fout in de definitieve controles. Opdrachtdekking
voor ontbrekend werkplan/zes punten is **niet beoordeeld**, geen PASS; invalid-
evidence/transport-FAILs in fictieve tests zijn verwachte veiligheidsuitkomsten.

Toegevoegd: WP-003.md, remote_preflight.py, test_remote_preflight.py en dit verslag.
Gewijzigd: uitsluitend de SQL-quote in dry_run.py. Geen SSH-verbinding, netwerkactie,
sudo, installatie, TEST-O-wijziging, commit, push of staging. Testwrites uitsluitend
lokale tijdelijke fixtures, na afloop verwijderd. Iteratie 2/3 niet gestart.
