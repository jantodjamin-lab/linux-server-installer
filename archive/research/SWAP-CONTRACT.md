> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# WP-003 — getypeerde offline swapstap en menselijke review

Iteratie 2/3. [Leidende bron](../workpackages/WP-003-ORIGINAL-REQUIREMENTS.md).
Geen uitvoerende adapter, CLI, shellhooks, transport of privilegepad.
[swap_step.py](../../infrastructure/installer/swap_step.py) beschrijft met frozen
dataclasses Plan, Observation, Context en Action-enum zes vaste handelingen.
`simulate` verandert uitsluitend fictieve immutable gegevens; dit is geen echte
installatie. [swap_validation.py](../../infrastructure/installer/swap_validation.py)
beoordeelt apart aangeleverde POST-waarnemingen, zonder uitvoeringsstatus.

## PRE, uitvoering, POST

PRE vereist expliciet ingevulde grootte, bruikbare actieve grootte (bestand
minus swapheader), reserve, pad, fstab-baseline en release. Geen defaults.
Filesystem/mount, reguliere file, afwezigheid van symlinks/hardlinks, non-swap
configuratie, services/sockets/poorten en versies moeten onafhankelijk worden
onderzocht en opgenomen in de reviewbaseline. `compatible`, `complete`,
`preflight` en `unchanged` zijn fixtureassertions; er is geen live collector voor
swap en geen authenticatiebewijs. Identity bevat host, pin, provider, generatie,
machine-id, boot-id. Binnen iedere run exact vergelijken. Freshness direct vóór
mutatie opnieuw beoordelen. GO-reference in fixtures is geen autorisatie.

Schone PRE: geen bestand, actieve swap, swapentry, eerdere backup of drift;
vrije ruimte >= bestandsgrootte + expliciet gekozen reserve. Compleet PASS,
compatibiliteit en menselijke aanwezigheid vereist; WARN/FAIL stopt.
Vaste volgorde: backup → exclusieve aanmaak → root:root/0600 → formatteren →
fstabregistratie → activeren. Geen bestaande swap vervangen. Exact geïnstalleerde
toestand inclusief backup geeft lege actielijst: idempotentie. Iedere andere
partiële toestand stopt. Geen retry of rollback.

POST: vers onafhankelijk gelezen bewijs; identiteit, actieve bruikbare grootte,
filegrootte, eigenaar/modus, exacte fstabbytes, backup van PRE-fstab en
non-swap-baseline moeten overeenkomen. Vrije ruimte blijft boven reserve.
Mislukte POST: FAIL en STOP, raw evidence behouden en menselijke review.
De onafhankelijke validator heeft eigen controles; live waarneming moet later
via een afzonderlijke read-only run komen. Geen echte reboot-/loadtest bewezen.

## Voorgestelde sudo-handelingen — uitsluitend review, niet uitgevoerd

Alleen een aanwezige mens mag later interactief sudo gebruiken. Codex ontvangt
geen wachtwoord. Geen sudo -S/-n, NOPASSWD, rootlogin of sudoerswijziging.
De volgende begrensde operaties moeten vóór GO-2 worden ingevuld en afzonderlijk
beoordeeld; dit is geen uitvoerbaar commando of reeds goedgekeurde lijst:

| Volgorde | Privileged operatie | Reviewgrens / controle |
| --- | --- | --- |
| 1 | `/etc/fstab` naar exclusief nieuw backupbestand kopiëren | Backuppad OPEN; bytes en rechten vastleggen, geen overwrite |
| 2 | Exclusief nieuw swapbestand aanmaken op goedgekeurd pad met exact besloten bytes | Pad/grootte/aanmaakmethode OPEN; filesystemcontrole en reserve vereist |
| 3 | Alleen dat bestand eigenaar root:root en modus 0600 geven | Regulier bestand, geen link; metadata teruglezen |
| 4 | Alleen dat bestand als swap formatteren | Exacte mkswap-versie/argv en bruikbare grootte OPEN; geen device/ander pad |
| 5 | Precies één `<pad> none swap sw 0 0`-regel aan fstab toevoegen | PRE-bytes en backup opnieuw controleren; behoud overige bytes; writeprocedure OPEN |
| 6 | Alleen dat swapbestand activeren | Exacte swapon-versie/argv OPEN; onafhankelijke POST verplicht |

Grootte/pad/backup-/write-/allocatiemethode zijn nog niet onderbouwd; daarom
geen schijnbaar exacte sudo-commandoreeks genereren. De concrete argv, timeout,
menselijke interactie, collisioncontrole en fail-stop moeten vóór GO-2 bevroren
worden. Installatie van tools valt buiten scope. Terugdraaiprocedure OPEN:
menselijk te beoordelen swapoff, exacte fstabrestore en eventuele verwijdering
vereisen eigen risicoanalyse/toestemming; nooit automatisch uitvoeren.

## Twee runs na snapshotrestore

Bewaar op APP-O per run raw PRE, uitvoeringstranscript en aparte raw POST,
identiteits-/hostkeyverificatie, provider/snapshot/generatierecord, reviewactor,
UTC-tijden, GO-record, plan/release en alle controles (ook FAIL). Gebruik nieuwe
private evidence-directory per onderdeel; bestaande bestanden niet overschrijven.
Bestaande `remote_preflight.save` kan JSON-artifacts opslaan; hashes bewijzen
inhoudsgelijkheid, geen authenticiteit. Bewijscompleetheid menselijk controleren.

PRE1 → GO-2 → installatie1 → onafhankelijke POST1 → menselijke review →
handmatige TransIP-snapshotrestore → herverifieerde hostkey/provider/identiteit →
nieuwe generatie + PRE2 → GO-3 → installatie2 → onafhankelijke POST2 → vergelijking.
Geen restore, reboot of herinstallatie door deze ontwikkelcode.

`compare_runs` bereidt de inhoudsvergelijking voor. Vooraf benoemde allowlist:
`observed_at`, gereviewde generatie en boot-id. Generatie moet veranderen;
host/pin/provider/machine-id blijven gelijk, anders STOP en nieuwe review.
Ruwe identity blijft behouden. UTC/runnonce/GO-/snapshotrecords blijven buiten
dit typed toestandsmodel, worden apart bewaard en menselijk gecontroleerd;
ze worden niet uit raw evidence verwijderd. Geen PID-normalisatie gebruikt.
Geen normalisatie van fstab, grootte, rechten, versies, baseline of vrije ruimte.
Beide POSTs moeten PASS zijn en beide PREs schoon. Idempotentie op geïnstalleerde
host is een afzonderlijke proef en geen vervanging van twee installaties.
