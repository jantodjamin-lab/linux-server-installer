> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# WP-001 — Read-only installatieplancontract

Iteratie 3/3, schema 1, status **DRAFT FOR REVIEW / WARN volledigheid**.
Dit contract beschrijft toekomstige gewenste wijzigingen; het voert ze niet uit.
Bronnen: [V2-baseline](../PROJECT_BASELINE.md), [WP-001](../workpackages/WP-001.md),
[kennisbaseline](../knowledge/RAMIN_V2_KNOWLEDGE_BASELINE.md) en
[bronregister](../knowledge/SOURCE_REGISTER.md). Historische stackkeuzes zijn
niet overgenomen. Paden, packages en versies worden niet willekeurig ingevuld.

| Fase | Doel en grens | Bewijs / toestemming |
| --- | --- | --- |
| Preflight | Lokale inventory en beleidsevaluatie, alleen nieuwe evidencewrite | Schema 2 PASS/WARN/FAIL; geen hostidentiteit, SSH-auth of sudo-autorisatie bewezen |
| Plan | Pure omzetting naar componenten, afhankelijkheden, rechten, PRE/POST en stops | Schema 1, deterministisch, SHA-256-binding, OPEN besluiten; altijd `installation_authorized=false`, `executable=false` |
| Live uitvoering | Toekomstige mutaties op een geverifieerde target via beperkte privileges | Niet geïmplementeerd; vereist afzonderlijke menselijke GO voor exacte target, releases en plan plus herstelvoorbereiding |
| Recovery | Werkelijke effecten beoordelen en gecontroleerd herstellen | Niet geïmplementeerd/bewezen; geen automatische retry, rollback of snapshotrestore |

## Contractvelden en validatie

`build_plan` accepteert alleen lokaal schema-2-bewijs dat overeenkomt met de
huidige evaluator: profiel, policy, status en controles. Checks worden als
ongeordende verzameling vergeleken, met behoud van duplicaatdetectie. Voor
probe-fouten worden naam/status vergeleken: de dictrepr in een foutmelding kan
na JSON-sortering een andere sleutelvolgorde hebben. Volledige errors blijven
via de inhoudshash gebonden. Malformed/inconsistent bewijs geeft `ValueError`;
het levert geen geldig plan op. Historisch schema 1 wordt niet gemigreerd.

Canonical JSON (gesorteerde keys, compacte separators, geen NaN/Infinity) bepaalt
de SHA-256 van het volledige invoerbewijs. Dezelfde input levert hetzelfde plan;
geen actuele tijd wordt toegevoegd. Een hash bewijst inhoudbinding, geen
publisherauthenticiteit, targetidentiteit of actualiteit. De inputtijd wordt
ongewijzigd doorgegeven; freshnessbeleid blijft OPEN. Het contract kopieert
inputdata zodat wijzigingen aan het resultaat de input niet wijzigen.

| Veld | Betekenis |
| --- | --- |
| `preflight_status` | Status van de gevalideerde invoer; FAIL blijft FAIL |
| `status` | FAIL bij preflight-FAIL, anders WARN wegens open besluiten; document-/test-PASS is afzonderlijk |
| `completeness`, `missing_observations` | Altijd OPEN; ontbrekende hoofdprobes zichtbaar. Dit is geen volledige readiness-validator |
| `target`, `releases` | Identity/generation/hostkey, installer- en applicatierelease zijn null/onbewezen |
| `components` | APP: runtime/HTTPS, TCP 80/443; DB: engine/geïsoleerde appdatabase, TCP 5432; APP-DB: beide. Poorten zijn voorstellen, geen goedkeuring of firewallactie |
| Componentvelden | Bron/versies/paden/account/unit/bindadres OPEN (`null`), afhankelijkheden, vereiste scoped rechten, preconditions en onafhankelijke postconditions |
| `open_decisions` | Target, OS/kernel, releases, trust/versies, mounts/paden, accounts/ports, privileges, swap, backup/rollback en validator/freshness |
| `stop_conditions` | FAIL, kritische unknowns, drift/stale evidence, onverwachte conflicts, mislukte validatie of onzekere effecten |
| `operator_steps` | Besluiten oplossen, target/PRE verifiëren, herstelbare snapshot en externe evidenceopslag bevestigen, afzonderlijke GO verkrijgen |
| `recovery` | Geen automatische retry/restore; bewaar sanitized evidence en laat effecten/recovery beoordelen |

Er zijn geen shellhooks, commandpayloads of uitvoerbare pakketacties. Benodigde
rechten zijn reviewcategorieën, geen sudoersconfiguratie of granted privileges.
Een poortconflict blijft preflight-WARN; een toekomstige executor moet dit vóór
mutatie oplossen en mag geen bestaande service automatisch overnemen.
1 vCPU/843 MiB blijft toegestaan met WARN; swap nul/onbekend blijft afzonderlijk
WARN. De planlaag maakt hiervan geen FAIL en kiest geen swapgrootte.

## Gebruik zonder probes

Vanuit de repositoryroot, uitsluitend met nieuw gekozen outputpad:

```python
import json
from pathlib import Path
from infrastructure.installer.plan import build_plan
from infrastructure.installer.preflight import save_evidence

evidence = json.loads(Path('docs/installer/evidence/iteration-3-app.json').read_text())
contract = build_plan(evidence)
save_evidence(contract, Path('docs/installer/evidence/review-app-new.json'))
```

De pure builder schrijft niets. `save_evidence` weigert bestaande bestanden;
opslagfouten worden aan de aanroeper gemeld. Alleen de preflight-CLI heeft de
bestaande JSON-stdoutfallback. Dit voorbeeld autoriseert geen live uitvoering.

## Menselijk runbook voor latere acceptatie

1. Besluit een apart uitvoerwerkpakket, stack/versies/trust, exact plan, beperkt
   privilegepad, onafhankelijke validatie en backup/rollback. Beoordeel alle WARNs.
2. Verifieer target/provider/generatie/hostkey onafhankelijk, neem verse PRE1,
   bevestig een herstelbare snapshot en verkrijg afzonderlijke installatie-GO.
3. Voer installatie 1 uit en verzamel onafhankelijke POST1 met versies, config,
   rechten, health en listenerbinding. Bewaar sanitized bewijs op APP-O buiten target.
4. Bij fout/onzekere effecten: stop, bewaar fout/checkpointevidence, onderzoek
   werkelijke toestand en laat herstel/retry expliciet beoordelen. Geen blind retry.
5. De gebruiker herstelt de snapshot via TransIP. Verifieer daarna opnieuw
   identiteit/generatie/hostkey; oude bereikbaarheid is geen nieuwe identitycheck.
6. Verzamel PRE2, verkrijg passende afzonderlijke GO en voer installatie 2 plus
   onafhankelijke POST2 uit. Vergelijk beide runs op APP-O. Alleen expliciet
   gekozen vluchtige velden normaliseren; security/config/versies/rechten behouden.

Twee succesvolle installaties met gebruikersrestore zijn nog vereist en hier
NOT TESTED. Een fixture-reset, idempotentierun, source rebuild en databasebackup-
restore zijn verschillende proeven. RPO/RTO, backupencryptie en app/DB-rollback
blijven open besluiten; dit contract claimt geen recoveryacceptatie.
