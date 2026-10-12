# Universal Linux Installer — install-now

Distributie van **1.0.0-bash.4**. Ontwikkeling vindt uitsluitend plaats in de private repository `jantodjamin-lab/ramin-control-panel-v2`.

Voer dit eenmalig zelf uit in een interactieve SSH/PuTTY-terminal op de bedoelde doelserver (Ubuntu 26.04). Controleer het registratieplan en bevestig alleen met `ja` als u de launcher wilt registreren. Registratie installeert geen serverprofiel.

```bash
bash -c set\ -Eeuo\ pipefail\;\ trap\ \'printf\ \"FAIL\ bootstrapdownload\ of\ validatie\\n\"\ \>\&2\'\ ERR\;\ umask\ 077\;\ command\ -v\ curl\ \>/dev/null\;\ command\ -v\ sha256sum\ \>/dev/null\;\ exec\ 3\<\>/dev/tty\;\ w=\$\(mktemp\ -d\ \"\$\{TMPDIR:-/tmp\}/uli-loader.XXXXXXXX\"\)\;\ trap\ \'rm\ -rf\ --\ \"\$w\"\'\ EXIT\;\ curl\ -q\ --fail\ --location\ --proto\ =https\ --proto-redir\ =https\ --connect-timeout\ 30\ --max-time\ 300\ --max-filesize\ 262144\ \"https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-bash.4/bootstrap.sh\"\ --output\ \"\$w/bootstrap.sh\"\;\ \[\[\ -f\ \$w/bootstrap.sh\ \&\&\ \!\ -L\ \$w/bootstrap.sh\ \&\&\ \$\(wc\ -c\ \<\ \"\$w/bootstrap.sh\"\)\ -le\ 262144\ \]\]\;\ printf\ \'51f6681f01ffc7c2c007266f7c98ba354972ed4139fc50034b1fc46d349c109d\ \ %s\\n\'\ \"\$w/bootstrap.sh\"\ \|\ sha256sum\ --check\ --status\;\ bash\ -n\ \"\$w/bootstrap.sh\"\;\ bash\ \"\$w/bootstrap.sh\"\ \"\$@\"\ \<\&3\ \>\&3\ 2\>\&3 install-now --register-install-now
```

Start daarna handmatig:

```bash
install-now
```

Iedere start downloadt dezelfde vastgepinde release via HTTPS en verifieert SHA256 vóór uitvoering. Kies in het bestaande menu APP, DATABASE, gecombineerd, status of afsluiten. Een installatie vereist afzonderlijk `ja` na het installatieplan; root/sudo is pas nodig voor registratie of een gekozen installatie. Conflicterende bestaande launcherbestanden worden niet overschreven.

- [Bash.4-release](https://github.com/jantodjamin-lab/linux-server-installer/releases/tag/v1.0.0-bash.4)
- [Releasearchief](https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-bash.4/universal-linux-installer-1.0.0-bash.4.tar.gz) — SHA256 `3e86da621994748b5687dd5edd35948328e9e2eb6a712185a150402a46baa931`
- [Bootstrap](https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-bash.4/bootstrap.sh) — SHA256 `51f6681f01ffc7c2c007266f7c98ba354972ed4139fc50034b1fc46d349c109d`
- [Checksums](https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-bash.4/SHA256SUMS)

Een exacte herregistratie is idempotent. De launcher houdt deze release vast; nieuwe releases worden niet automatisch geselecteerd. Deze publicatie wijzigt de bestaande installermotor niet. Historische releaselinks blijven beschikbaar; losse ontwikkelbestanden zijn uit de actuele publieke branch verwijderd en blijven in Git-geschiedenis en de private repository bewaard.
