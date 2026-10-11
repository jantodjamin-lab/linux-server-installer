> **CLOSED – SUPERSEDED BY BASH V1.** Historical evidence only; commands below must not be used for active installation.

# TEST-O — Geverifieerde identiteit

Status: VERIFIED FOR GO-1 REVIEW
Datum: 2026-10-10

## Provider

- Provider: TransIP
- VPS-naam: widjamin-vps6
- IP-adres: 149.210.166.239
- SSH-account: o2-admin
- Schone snapshot: Pre-install20261007
- Gebruiker bevestigt: dit is de bedoelde test-VPS

## Onafhankelijke consolecontrole

- Hostname: cloud.example.com
- Machine-ID: 21f6df03264056c90382000028c88d41
- Hostkeytype: ED25519
- Fingerprint: SHA256:IwugsqszZLcsMjve5+ZLja/HaSe7ORMbc9ciWb354tg
- Pinbestand: infrastructure/ssh/test-o_known_hosts

De hostkey is via de TransIP-console vastgesteld
en lokaal op APP-O gecontroleerd.

## Veiligheidsgrenzen

- GO-1: uitsluitend read-only preflight.
- GO-2: afzonderlijke toestemming voor swapinstallatie.
- GO-3: afzonderlijke toestemming voor tweede installatietest.
- Geen automatische snapshotrestore.
- Na restore opnieuw identiteit en hostkey controleren.
- Geen sudo, installatie of configuratiewijziging onder GO-1.

## Nog niet bewezen

- Live SSH-verbinding via de nieuwe preflight.
- Volledige remote systeeminventarisatie.
- Snapshotgeneratie na herstel.
- Werkelijke installatie en reproduceerbaarheid.
