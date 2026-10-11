> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# RC5 — voorlopig technisch validatie- en publicatierapport

Dit is een privé werkrapport. Definitieve VM-resultaten, private commit en eventuele
release-publicatie worden uitsluitend door de hoofdagent toegevoegd nadat het
bijbehorende bewijs beschikbaar is. Dit document behoort niet tot de publieke
release-allowlist.

## Status en grenzen

**Voorlopig NO-GO voor installatie op TEST-O: de eerdere verplichte VM-run
faalde door de koude-bootvolgorde van het testharnas; herstel is gepusht en de
nieuwe volledige verplichte validatie loopt nog.**
**NIET LIVE GEVALIDEERD.** Er is geen installatie op TEST-O uitgevoerd en geen
productieactie geautoriseerd. Ontwikkeling en offline tests gebeurden op APP-O;
systeemwijzigende tests uitsluitend in geïsoleerde GitHub-containers en
wegwerp-QEMU-VM's. De historische repository en main blijven onaangeroerd.

- Private branch: `feature/universal-linux-installer-v1`.
- Private HEAD vóór RC5-commit: `beb51031adbd2b93b6c15423e933cd8a0f019754`.
- Actuele publieke ontwikkelcommit: `80459fbe65ec4b91a1218a3833c01832a5451593`.
- Eerder gevalideerde candidate: `17800c77b7fbd4b014e48d7818f7536beef1723a`.
- Publieke branch: `release-candidate`.
- [Actuele volledige validatierun](https://github.com/jantodjamin-lab/linux-server-installer/actions/runs/38126298303): `publish=false`, security/faultmatrix aan, arm64 uit.
- [Historische candidate-run](https://github.com/jantodjamin-lab/linux-server-installer/actions/runs/38097739789).
- Duplicaat-pushrun `38126294431` is geannuleerd om runners voor de volledige run vrij te maken.
- RC5-prerelease: **nog niet gepubliceerd**.
- Private RC5-commit/push: **nog niet uitgevoerd**.

## Harde acceptatiecriteria

| Criterium | Voorlopige status | Bewijs en beperking |
|---|---|---|
| Unit-, syntax- en lintchecks | PASS lokaal / actuele CI PENDING | Actueel lokaal 155 tests, één fixture-SKIP; historische CI 153 tests, één SKIP |
| Echte signed APT-closure, alle profielen | Historisch PASS / actuele CI PENDING | Candidate 178: amd64 Ubuntu 26.04 Canonical en TransIP × APP/DB/APP+DB, zes resolver/preflight-routes |
| Node/npm en echte npm-locks | PASS | Echte Ubuntu nodejs/npm; Angular/Codex `npm ci --ignore-scripts`; SRI/pins behouden |
| Volledige URI TransIP | PASS | Opgegeven URI expliciet toegestaan; zonder opt-in geweigerd; echte feed in container gecontroleerd |
| Exact oorspronkelijk providerbestand | WARN | Eigenaar leverde velden, niet het captured bestand; één benoemde fixture-SKIP |
| Niet-cascaderende audit en indexleeftijd | PASS | Offline onafhankelijke bron/key/signature/candidate-tests en stale-index-WARN |
| Audit zonder installerwijzigingen | PASS | Offline en alle drie eerste-boot-VM-snapshots PASS |
| APP-, DB-, APP+DB-installatie met systemd | PASS beperkt / VM-job FAIL | Alle drie installation_status PASS en repeatasserties geslaagd; koude-bootfase van harnas faalt |
| Swap 0 → 4 GiB, eerste boot | PASS | Werkelijke actieve swap op alle drie profielen, vóór koude reboot |
| Swap 2/4+ GiB en persistentie na koude boot | FAIL/SKIPPED | Coldbootbewijs ontbreekt door ordering cycle; aanvullende matrix dependency-SKIP |
| Echte sudo met/zonder wachtwoord | PASS | NOPASSWD en echte password-authenticatie op alle drie disposable-VM-profielen; approval geweigerd vóór effecten |
| Recovery na elk journal-event | SKIPPED | Offline classificaties PASS; echte faultmatrix geblokkeerd door smoketestdependency |
| Dpkg-lock en unattended-upgrade-dry-run | SKIPPED | Begrensde locktimeout in code; echte contentionmatrix dependency-SKIP |
| 843 MiB en laag geheugen | SKIPPED | Exacte minimumgrens offline; aanvullende VM-matrix dependency-SKIP |
| Arm64 best effort | WARN — timeout | Job `114347151207` eindigde na precies 55 minuten met exit 137 door de buitenste timeout; geen volledige ARM-PASS |
| Geheimvrije diagnostiek | PASS | Credentialredactie, bounded stdout/JSON en private logs getest |
| Reproduceerbare build/allowlist/checksums | PASS | CI-bytevergelijking, manifest en uitgepakte testset groen |
| Private/public overeenkomst en schone Git | PENDING | Definitieve commit/synchronisatiecontrole volgt na acceptatie |
| Onafhankelijk publiek downloaden RC5 | PENDING | Kan pas na publicatie; niet als geslaagd geclaimd |

De tabel hierboven onderscheidt historisch bewijs van volledige actuele
acceptatie. Voor commit `80459f…` zijn **155 lokale tests met één fixture-SKIP
PASS**. Alle verplichte checks in de nieuwe volledige CI-run staan nog PENDING;
eerder geslaagde echte-tool-/eerste-bootresultaten gelden niet automatisch als
een herhaalde PASS voor de gewijzigde build.

## Wat technisch is hersteld

Mirror-opt-in bindt de volledige URI exact aan de autorisatie en het plan.
Canonical-fingerprints en iedere InRelease-signatuur blijven verplicht. deb822,
`Signed-By`, cloud-init-bronnen en optionele uitbreiding van universe volgen één
bronpad; bronbeleid, keyring, cached signatures en kandidaatbeschikbaarheid zijn
afzonderlijk zichtbaar. Een oude index geeft WARN, zonder tijdens audit te
verversen. Een ontbrekende kandidaat na refresh stopt veilig.

`--apply` bindt expliciete INSTALL-autorisatie aan profiel, doelidentiteit,
bronbeleid, mirrors, opties en limieten. Pas daarna worden metadata ververst,
echte versies en closure opgelost, lock/plan geschreven en exacte pins toegepast.
`--resolve --out DIR` vereist aparte `--refresh-metadata`-autorisatie. Schema 4
wordt geweigerd; schema 5 heeft UTC-tijd en een twee-uurs geldigheidsgrens.

Bronnen blijven ondertekend; removals, downgrades, ongepinde closure-uitbreiding en
impliciete updates blijven verboden. Dpkg-locks wachten maximaal 600 seconden.
Proxyvariabelen worden uitsluitend expliciet doorgegeven en credentials niet
gelogd. Npm gebruikt reviewed shipped locks, SRI en `--ignore-scripts`.

Fouten bewaren bounded stap/code/exitstatus; geredacteerde stderr staat alleen in
private diagnostiek. Readonly/idempotente pending stappen kunnen veilig hervat
worden; effectful stappen blijven reviewplichtig. Swap gebruikt echte
util-linux-kolomselectie, deficit-only capaciteit, exclusieve eigendom, inode- en
permissiecontrole, checkpoints en persistente fstab zonder bestaande swap te
verwijderen. Managed servicepoorten worden daadwerkelijk op loopback gecontroleerd.

Installatie weigert unmanaged bestaande serviceconfiguratie/data. Dit is veilige
weigering, geen automatische adoptie. Bestaande basispakketten en held installed
pakketten worden juist herkend; APT-holdbescherming wordt niet versoepeld. Bulk
dpkg-snapshots behouden exacte controles en vermijden duizenden subprocessen.

## Tests en exacte opdrachten

Laag 1 — uitgevoerd, PASS met één benoemde SKIP:

```sh
python3 -B -W error::ResourceWarning -m unittest discover -s tests
python3 -B tools/check-syntax.py
sh -n install.sh
python3 -B -m pyflakes lib tools
python3 -B release/build.py
```

De ontbrekende originele TransIP-capture is de fixture-SKIP. Het bestaande
RC4-baselinebewijs (81 tests) blijft historisch onderscheiden van de huidige,
uitgebreide testset en het bewust verwijderde dode engine-model.

Laag 2 — uitgevoerd, PASS:

```sh
sh tools/container-test.sh
```

Dit script weigert uitvoering buiten een Ubuntu 26.04-container. Artifact
`11686532785` bevat de echte kandidaat-, closure-, key-, signature-, runtime- en
npm-resultaten. Dit is geen bewijs voor systemd-services of actieve swap.

Laag 2 arm64 — best effort, **afgebroken door begrensde buitenste timeout**:

- Job `114347151207` gebruikte Docker/QEMU-user en eindigde na precies
  55 minuten met exit 137. Dit is geen aangetoonde pakket- of bronfout.
- Artifact `11687697149` bevat een volledig geslaagde Canonical APP-closure:
  387 nieuwe pakketten, kandidaat Node `22.22.1` en npm `9.2`.
- Canonical APP+DB-preflight was PASS; resolutie stond nog op RUNNING toen
  de timeout het proces beëindigde.
- Er is **geen volledige arm64-PASS** en geen afgerond bewijs voor TransIP
  op arm64 of de npm-installatiestap op arm64.
- Lokaal bewaard bewijs: `/tmp/rc5-arm64-178.log` en
  `/tmp/rc5-arm64-178.zip`. amd64 blijft de verplichte, geslaagde laag-2-route.

Laag 3 — geïsoleerde eerste installatie geslaagd; **volledige jobs FAIL**:

Alle drie profielen draaiden daadwerkelijk op Ubuntu **26.04.1** met systemd,
de expliciete TransIP-mirror en nul beginswap. Hun artifacts bevatten
`installation_status=PASS`, geslaagde herhaalasserties en echte NOPASSWD- en
password-sudo-authenticatie. Actieve swap bereikte 4 GiB. Het eerste-run aantal
journal-events was DB **20**, APP **26**, APP+DB **28**.

De koude-bootfase mislukte door een **ordering cycle in het testharnas**:
`rc5-e2e.service` stond `After=cloud-final.service` én werd aan
`multi-user.target` gekoppeld. De seriële tweede-bootlogs melden letterlijk
`Ordering cycle` en het overslaan van `rc5-e2e.service`. De eerste-bootresultaten
bleven `status=REBOOT_REQUIRED`, `coldboot=false`; daarom zijn de volledige
VM-jobs terecht FAIL. Er is **geen coldboot-PASS** en geen overall VM-PASS.

Bewijs:

| Profiel | Artifact | Lokaal bestand |
|---|---|---|
| DB | `11690379020` | `/tmp/rc5-vm-db-178.zip` |
| APP | `11691087495` | `/tmp/rc5-vm-app-178.zip` |
| APP+DB | `11690393758` | `/tmp/rc5-vm-appdb-178.zip` |

De security- en faultjobs zijn **SKIPPED door de dependencygate**, niet geslaagd.
Het publieke harnas is hersteld in commit `80459f…`: de unit wordt nu aan
`cloud-final.service` gekoppeld (`WantedBy=cloud-final.service`), terwijl
`After=cloud-final.service` behouden blijft. Een regressie controleert de
daadwerkelijke unit-dependencygraph. De eerste host-boot heeft maximaal
150 minuten, de tweede maximaal 20 minuten; een mislukt coldbootbewijs kan dus
niet opnieuw onbegrensd op de volledige eerste-bootlimiet wachten. De nieuwe
echte run is verplicht vóór acceptatie of publicatie en loopt nog. De huidige
candidate blijft ongepubliceerd.

Exact harnascommando voor de volgende afzonderlijk geïsoleerde run:

```sh
RC5_E2E_IMAGE=/pad/naar/geverifieerd-ubuntu-26.04-cloudimage.img \
RC5_E2E_IMAGE_SHA256=<onafhankelijk-geverifieerde-sha256> \
RC5_E2E_REBOOT=1 sh tools/e2e-vm.sh APP
```

Herhaal voor `DB` en `APP+DB`. CI stelt het exacte image en de hash vast via
geverifieerde Canonical-cloudmetadata; het harnas gebruikt lokale QEMU-overlays,
NoCloud en seriële/artifactuitvoer, nooit SSH. De uitgebreide securitymatrix
omvat swap2/swap4/minimum/low-memory/contention. Faultjobs worden uitsluitend
afgeleid van het werkelijke eerste-run eventaantal per profiel.

## Bewijsgrenzen en resterende risico's

- De mirrorfixture reconstrueert de door de eigenaar opgegeven publieke velden;
  zij bewijst niet alle extra velden/rechten van het oorspronkelijke bestand.
- Journal-event-killtests bewijzen de durable grenzen vóór effecten en na
  postcondities; zij bewijzen geen willekeurige kill midden in elke dpkg-write.
- Een gedeeltelijk uitgevoerd plan ouder dan twee uur blijft geweigerd: alleen
  een veilig, exact gebonden en volledig afgerond journal staat effectvrije
  revalidatie van een verlopen plan toe. Geen automatische rollback/adoptie.
- Old exact pins kunnen later uit het archive verdwijnen. Zelfs completed-plan
  revalidatie kan dan veilig stoppen; er worden geen versies geraden.
- Een QEMU-VM met toegewezen 843 MiB kan door kernelreserveringen minder dan
  843 MiB MemTotal tonen; dan moet admissie stoppen. Swap vervangt fysieke RAM
  niet. APP+DB bij dit minimum blijft een nadrukkelijke operationele WARN.
- Echte TEST-O-installatie blijft afzonderlijk te autoriseren. Deze iteratie
  verandert `live_validated` niet naar true; eigenaaracceptatie blijft vereist.

## Candidate-integriteit en latere operatorroute

Huidige candidate-SHA256; uitsluitend gebruiken als definitieve build identiek
blijft:

```text
59925fa7926766593114cfb2dd7fdb83f980bc23c12df8a839dcd4a81360b9c4
```

Beoogde release-URL, **nog niet gepubliceerd**:
`https://github.com/jantodjamin-lab/linux-server-installer/releases/tag/v1.0.0-rc.5`.

Read-only audit vanuit de geverifieerde, uitgepakte RC5-directory op TEST-O:

```sh
sh install.sh --profile APP+DB --audit \
  --allow-mirror https://mirror.transip.net/ubuntu/ubuntu/ --json
```

Installatie voor later afzonderlijk geautoriseerd gebruik, na werkelijke
snapshotbevestiging en beoordeling van warnings:

```sh
sh install.sh --profile APP+DB --apply --sudo --development --system-updates \
  --allow-mirror https://mirror.transip.net/ubuntu/ubuntu/ \
  --snapshot-confirmed --allow-unvalidated --show-diagnostics
```

Typ de getoonde `INSTALL <eerste 12 tekens van autorisatiehash>`. De autorisatie
dekt refresh, resolver en de bounded installatie. `--system-updates` is een
expliciete opt-in, geen algemene upgrade. `--development` voegt Codex toe.
`--allow-unvalidated` verandert de validatiestatus niet.

De hoofdagent moet na afgeronde tests definitieve VM-/matrixresultaten,
private/public SHA's, release/downloadcheck en GO/NO-GO toevoegen. Tot die tijd
is deze rapportage bewust voorlopig.

## Bestandsinventaris vóór commit

Deze lijst is rechtstreeks afgeleid van `git status --short --untracked-files=all -- installer`.

### Gewijzigd

- `installer/README.md`
- `installer/SECURITY.md`
- `installer/docs/GUIDE.md`
- `installer/docs/SOURCES.md`
- `installer/lib/cli.py`
- `installer/lib/core.py`
- `installer/lib/journal.py`
- `installer/lib/local.py`
- `installer/lib/node.py`
- `installer/lib/privilege.py`
- `installer/lib/sources.py`
- `installer/lib/swap.py`
- `installer/lib/workflow.py`
- `installer/release/AUDIT.txt`
- `installer/release/SHA256SUMS`
- `installer/release/build.py`
- `installer/release/manifest.json`
- `installer/tests/test_integration.py`
- `installer/tests/test_local.py`
- `installer/tests/test_rc3.py`
- `installer/tests/test_rc4.py`

### Nieuw

- `installer/.github/workflows/refresh-npm-lock.yml`
- `installer/.github/workflows/release.yml`
- `installer/.gitignore`
- `installer/CHANGELOG.md`
- `installer/bundle/angular/package-lock.json`
- `installer/bundle/angular/package.json`
- `installer/bundle/codex/package-lock.json`
- `installer/bundle/codex/package.json`
- `installer/docs/ARCHITECTURE.md`
- `installer/docs/CI_VALIDATION.md`
- `installer/docs/FOLLOWUP_RC5.md`
- `installer/lib/apply.py`
- `installer/lib/errors.py`
- `installer/lib/index_age.py`
- `installer/lib/resolve.py`
- `installer/profiles/npm-pins.json`
- `installer/tests/fixtures/transip-26.04/README.md`
- `installer/tests/test_ci_harness.py`
- `installer/tests/test_cli_sudo_order.py`
- `installer/tests/test_container_diagnostics.py`
- `installer/tests/test_e2e_harness.py`
- `installer/tests/test_package_snapshot.py`
- `installer/tests/test_preflight_diagnostics.py`
- `installer/tests/test_rc5.py`
- `installer/tests/test_recovery_acceptance.py`
- `installer/tests/test_resolve_authorization.py`
- `installer/tests/test_transip_supplied.py`
- `installer/tools/check-syntax.py`
- `installer/tools/ci-vm.sh`
- `installer/tools/container-test.py`
- `installer/tools/container-test.sh`
- `installer/tools/e2e-guest.py`
- `installer/tools/e2e-seed.py`
- `installer/tools/e2e-vm.sh`
- `installer/tools/make-fault-matrix.py`
- `installer/tools/make-npm-bundle.py`

### Verwijderd

- `installer/docs/ACCEPTANCE.md`
- `installer/docs/COMPATIBILITY.md`
- `installer/docs/INVENTORY.md`
- `installer/docs/RC3.md`
- `installer/docs/RC4.md`
- `installer/docs/RUNBOOK.md`
- `installer/docs/VALIDATION.md`
- `installer/lib/engine.py`
- `installer/release/rc3-release.yml`
- `installer/release/rc3-verify.yml`
- `installer/release/rc4-release.yml`
- `installer/release/universal-linux-installer-1.0.0-rc.1.tar.gz`
- `installer/release/universal-linux-installer-1.0.0-rc.2.tar.gz`
- `installer/release/universal-linux-installer-1.0.0-rc.3.tar.gz`
- `installer/release/universal-linux-installer-1.0.0-rc.4.tar.gz`
- `installer/tests/test_engine.py`
