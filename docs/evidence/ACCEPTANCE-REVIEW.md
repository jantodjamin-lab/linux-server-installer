# Definitieve onafhankelijke bewijsbeoordeling — PASS

Read-only beoordeling op 2026-10-11 van alle acht gedownloade VM-artifacts in `/tmp/bash-v1-evidence/accepted/`. `run.json` en `jobs.json` bevestigen run **38135968474**, commit **1fe418f7ada859562bf80927d1a055d6e7fed51b**, en **9/9 jobs SUCCESS**, waaronder offline-validatie. Geen bronbestanden of hosts gewijzigd.

Elk VM-artifact is volledig gelezen, bevat eindresultaat **PASS**, identificeert **Ubuntu 26.04.1 LTS**, en bevat afzonderlijke seriële eerste en tweede boots: eerste boot eindigt met echte `reboot: Restarting system`, tweede start de kernel opnieuw. De zeven positieve scenario's bewaren succesvolle resume-servicevelden vóór de handmatige herhaalinstallatie; het negatieve scenario bewaart de verwachte veilige fout.

| Scenario | Beoordeling | Resume Result / exit | Starttimestamp monotonic | Actieve swap na reboot |
| --- | --- | --- | --- | --- |
| APP, swap0 | PASS | success / 0 | 49977435 | 4296011776 bytes |
| DB, swap0 | PASS | success / 0 | 67880018 | 4296011776 bytes |
| APP+DB, swap0 | PASS | success / 0 | 111696941 | 4296011776 bytes |
| DB, swap2 | PASS | success / 0 | 77774256 | 4296007680 bytes, oorspronkelijke swap behouden |
| DB, swap4 | PASS | success / 0 | 143237737 | 4296011776 bytes, alleen oorspronkelijke swap |
| DB, TransIP | PASS | success / 0 | 93972081 | 4296011776 bytes |
| DB, pakketonderbreking | PASS | success / 0 | 81387352 | 4296011776 bytes |
| DB, swaponderbreking | PASS veilige stop | exit-code / 1 | 79580493 | 0 bytes; gedeeltelijke file niet geactiveerd |

APP en APP+DB voeren na reboot de echte binaries uit: Git **2.53.0**, .NET SDK **10.0.112**, Node **v22.22.1**, npm **9.2.0**, Codex CLI **0.128.0**. Nginx is actief en de configuratietest slaagt. Alle positieve DB-scenario's voeren PostgreSQL uit met versie **18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)** en actieve service. APP+DB logt beide afgeronde profielstappen en daarna een afgeronde herhaalcontrole zonder nieuwe installatie.

DB/swap0 bevat aanvullend werkelijk sudo-bewijs: de eerste entry draait als **uid=1000(ubuntu)** met sudo-groep; de echte sudo-escalatie voltooit het DB-profiel. De dubbele eerste installatieplanweergave correspondeert met entry en geautoriseerde root-reexec.

De pakketonderbreking bewaart vóór reboot `profile=database`, `current=database`, `status=running`, zonder voltooide profielstap. Het tweede-bootjournal laat de oorspronkelijke systemd-resume-service de installatie voltooien. Het onderbrekingspunt bevindt zich bewust vóór daadwerkelijke APT-installatie, zodat geen onzekere dpkg-transactie wordt gerepareerd.

De swaponderbreking bewaart vóór reboot `current=swap`, `status=running` en een daadwerkelijk gedeeltelijk geschreven bestand van **1048576 bytes**. De SHA256 **30e14955ebf1352266dc2ff8067e68104607e750abb9d3b36582b8af909fcb58** komt overeen met 1 MiB nulbytes. Na reboot slagen beide controles van dezelfde hash; het servicejournal weigert het onbekende bestand te overschrijven. Eindstatus is **failed/current=swap**, service-exit **1**, audit meldt **0 actieve swapbytes**. Het harnas controleert ongewijzigde fstab/state en afwezigheid van ownership-marker en actieve swapfile. Dit PASS-resultaat betekent correcte veilige blokkering, niet dat de negatieve DB-installatie voltooid is.

De positieve herhaaltests vergelijken fstab vóór en na herhaling en controleren reeds voltooide componenten. De daadwerkelijke swapinventaris overschrijdt in elk positief scenario de vereiste **4294967296 bytes**. De swap4-test activeert na reboot uitsluitend `/existing-swap`, zonder nieuwe beheerde swapfile.

## Grenzen

Deze bewijscontrole valideert de genoemde commit en de geteste geïsoleerde **amd64 Ubuntu 26.04.1**-omgeving. De TransIP-scenario-identiteit en succesvolle pakketinstallatie zijn vastgesteld; de exacte ingestelde mirror-URI is niet als afzonderlijk APT-bronbestand in het artifact bewaard. Willekeurige storingen tijdens dpkg, andere architecturen en afwijkende bestaande PostgreSQL-configuraties zijn hiermee niet algemeen gegarandeerd. Onzekere hersteltoestanden moeten veilig blijven blokkeren.

Alle bestanden zijn bewijsmetadata/logs; geen VM-schijf, raw swapinhoud of private sleutel is in deze geaccepteerde artifacts aangetroffen. Publieke release-integriteit en de definitieve koppeling van publicatie aan deze geteste bron blijven afzonderlijke oplevercontroles.
