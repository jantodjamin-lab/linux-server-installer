> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# WP-001 — Afgeronde iteratie 3/3: lokale preflight en plancontract

WP-001 levert uitsluitend ontwerp, inventarisatie, beleidsevaluatie,
JSON-bewijs en fictieve tests. Er is geen installer die wijzigingen uitvoert.
Er zijn geen externe Python-afhankelijkheden. Python 3.9 of hoger is nodig.

## Uitvoeren op APP-O

Vanuit de repository:

```bash
python3 -B infrastructure/installer/preflight.py --profile APP
python3 -B infrastructure/installer/preflight.py --profile DB
python3 -B infrastructure/installer/preflight.py --profile APP-DB
python3 -B -m unittest discover -s tests -v
```

Zonder `--output` krijgt elke uitvoering een nieuw tijdgestempeld bestand onder
`docs/installer/evidence/`. Met `--output docs/installer/evidence/naam.json` kan
expliciet een nieuw bewijsbestand worden gekozen. Bestaande bestanden worden
nooit overschreven. `--disk-path` bepaalt welk lokaal bestandssysteem wordt
gecontroleerd; standaard is dat het bestandssysteem van deze repository.
Voer dit in iteratie 3 uitsluitend lokaal op APP-O uit. Er is geen remote modus.
De code controleert geen machine-identiteit: APP-O is een operationele grens,
geen door hostname of IP-adres bewezen beveiligingsgarantie.

Standaarduitvoer bevat uitsluitend JSON; stderr bevat de samenvatting en het
bewijsbestandpad. Exitcode 0 betekent PASS of WARN; exitcode 1 betekent FAIL,
inclusief het niet kunnen opslaan van bewijs. Ongeldige CLI-argumenten geven
exitcode 2 vóór inventarisatie en leveren geen controlerapport op.

## Architectuur

1. `collect` verzamelt onafhankelijke lokale waarnemingen. Een mislukte probe
   wordt als fout vastgelegd; de overige probes gaan door.
2. `evaluate` past het gekozen profiel toe op de waarnemingen, zonder I/O.
3. `save_evidence` bewaart de volledige uitslag, ook bij FAIL. Alleen een nieuw
   bestand binnen deze repository en buiten `.git`, `.agents`, `.codex`, `.aws` en `references` is toegestaan. Symlinks
   worden bij de padcontrole opgelost.
4. De CLI geeft hetzelfde bewijs als JSON terug. Als opslaan mislukt, bevat de
   JSON op stdout ook een FAIL voor bewijsopslag; persistente opslag kan bij een
   onbeschrijfbaar bestandssysteem niet worden gegarandeerd.

JSON schema versie 2 bevat UTC-tijd, profiel, scope, toegepast beleid,
aggregaatstatus, controles met status en reden, waarnemingen en probe-fouten. Queryfouten bevatten exitcode en stdout/stderr; timeouts
bevatten de timeout en eventuele gedeeltelijke uitvoer. Parserfouten behouden
de ontvangen ruwe inventaris onder `observations.*_raw`. Schema 2 maakt het
O/TEST-minimum en productieadvies afzonderlijk zichtbaar in `policy`.
PASS betekent dat een beschreven controle slaagt; WARN betekent een beperking,
onbekende uitkomst of aandachtspunt; FAIL betekent een resource onder het O/TEST-minimum,
een niet-Linux kernel of mislukte bewijsopslag. FAIL heeft voorrang op WARN.
Een probe-fout is WARN en dus nooit een stilzwijgende PASS. Een rapport is geen
installatietoestemming. Afgebroken processen of stroomuitval vallen buiten de
garantie dat afgeronde controles worden opgeslagen.

## O/TEST-beleid en productieadvies

Voor de afgesproken O/TEST-omgeving geldt voor **alle profielen** minimaal
1 vCPU en 843 MiB RAM. Deze capaciteit is toegestaan en geeft WARN zolang het
productieadvies niet wordt gehaald. Op of boven het productieadvies geeft de
resourcecontrole PASS; onder het O/TEST-minimum geeft zij FAIL. Dit is geen
verklaring dat productiebelasting op deze kleine omgeving past. Vrije schijf
blijft een afzonderlijke minimumcontrole met FAIL onder de profielgrens.

| Profiel | CPU productieadvies | RAM productieadvies (MiB) | Vrije schijf minimum (GiB) | Voorgestelde poorten |
| --- | ---: | ---: | ---: | --- |
| APP | 2 | 2048 | 10 | TCP 80, 443 |
| DB | 2 | 4096 | 20 | TCP 5432 |
| APP-DB | 4 | 6144 | 30 | TCP 80, 443, 5432 |

De productieadviezen zijn ontwerpkeuzes die vóór productie-installatie moeten
worden gevalideerd. Swap telt niet mee als RAM. Swap krijgt afzonderlijk PASS
bij een positieve waarneming en WARN bij nul of een ontbrekende waarneming.
Een ontbrekende RAM-waarneming verhindert de beoordeling van beschikbare swap
niet, en andersom. Onbekende resources geven WARN.

Ubuntu en Debian zijn ontwerpdoelen. Andere distributies krijgen WARN.
De kernelnaam en release worden vastgelegd; er is nog geen versiecompatibiliteit
bewezen. CPU komt uit `os.cpu_count`, RAM en swap uit `/proc/meminfo` en vrije
schijfruimte uit `shutil.disk_usage`. Geen swap geeft WARN.

Alle geladen systemd-services worden met `list-units --all` geïnventariseerd,
ook inactieve en gefaalde units, met unitnaam, load-, active- en substatus.
Gefaalde of onbruikbaar geladen services geven WARN. Dit is geen volledige
inventaris van geïnstalleerde unitbestanden. Service-logboeken en
omgevingsvariabelen worden niet gelezen. TCP- en UDP-listeners worden met `ss`
geïnventariseerd. Een voorgestelde profielpoort in gebruik geeft WARN, ook bij
UDP als conservatieve melding. Er wordt niets gestopt of gestart.

Een geladen, actieve en draaiende `ssh.service`/`sshd.service`, een geladen,
actieve en luisterende `ssh.socket`/`sshd.socket`, het lokale sshd-programma en
TCP 22 worden apart gecontroleerd. De service- en socketinventarissen zijn
onafhankelijk: socketactivatie kan PASS voor de socket geven naast WARN voor
een niet-draaiende service. Ontbrekende of onbekende signalen geven WARN.
Custom SSH-poorten en units, proceseigendom, firewalls, authenticatie en
effectieve configuratie zijn niet geverifieerd. TCP 22 en een actieve SSH-unit
bewijzen geen werkende SSH-toegang; `ssh_security` blijft WARN.

De aanwezigheid van sudo en de lokale UID, effectieve UID en numerieke groepen
worden afzonderlijk vastgelegd. `sudo_context` PASS betekent alleen dat de
gebruikerscontext is waargenomen. Ook UID 0, groepslidmaatschap en een gevonden
sudo-programma bewijzen geen sudo-autorisatie of wachtwoordloos gebruik.
`sudo_passwordless` blijft WARN. Er worden geen sudoersbestanden of credentials
gelezen en geen sudo-opdrachten uitgevoerd.

Alle waarnemingen gelden voor de zichtbare uitvoeromgeving. Containers,
sandboxing en namespaces kunnen resources, services en listeners anders tonen
dan de volledige host. Zonder beschikbare service-inventaris blijft die controle
WARN. De preflight probeert die beperking niet met extra rechten te omzeilen.

## Veiligheidsgrenzen

- Geen sudo-uitvoering, ook geen `sudo -n`. Alleen aanwezigheid van het programma
  wordt gecontroleerd. Wachtwoordloze beschikbaarheid blijft expliciet WARN,
  omdat verificatie zou botsen met het sudo-verbod in WP-001.
- Geen SSH-verbindingen; geen handelingen op TEST-O; geen netwerkprobes.
- Geen apt, pakketinstallaties, servicewijzigingen, firewallbeheer, swap-aanmaak
  of andere systeemwijzigingen.
- Geen lezen of wijzigen van bestaande SSH-configuratie, sleutels of credentials.
- Geen uitvoering of hergebruik van oude Ramin-code.
- Alleen vaste lokale subprocessqueries: `systemctl list-units` voor services en sockets en `ss -H -lntu`.
  Zonder shell, met stdin gesloten via DEVNULL en met timeout van vijf seconden.
- De enige bedoelde schrijfhandeling van de preflight is lokaal JSON-bewijs.
  `-B` voorkomt Python-bytecodebestanden tijdens de gedocumenteerde opdrachten.
- Geen live installatie, commit of push. Deze uitvoering is iteratie 3 van
  maximaal 3; WP-001 heeft geen resterende iteratie.

## Plancontract en vervolg

De pure functie `infrastructure.installer.plan.build_plan(evidence)` zet actueel
schema-2-preflightbewijs om naar een deterministisch JSON-reviewcontract voor
APP, DB of APP-DB. Zij voert geen probes, writes, netwerk of opdrachten uit.
Opslaan kan expliciet via de bestaande `save_evidence`; dezelfde padgrenzen en
weigering van overschrijven gelden. Er is geen plan-CLI of executor.
Zie [PLAN-CONTRACT](PLAN-CONTRACT.md) voor velden, open besluiten en de grens
naar live uitvoering en recovery. De zes bestanden met prefix `iteration-3-`
in `evidence/` zijn lokale preflight- en planbewijzen; geen targetacceptatie.
