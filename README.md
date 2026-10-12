# Universal Linux Installer — install-now

Korte registratieopdracht **v1.0.0-install-now.1** voor de bestaande installer **1.0.0-bash.4**. Ontwikkeling gebeurt uitsluitend in de private repository `jantodjamin-lab/ramin-control-panel-v2`.

Voer dit eenmalig zelf uit in een interactieve SSH/PuTTY-terminal op de bedoelde doelserver (Ubuntu 26.04):

```bash
(umask 077; d=$(mktemp -d) && trap 'rm -rf -- "$d"' EXIT && curl -qfsSL --proto =https --proto-redir =https https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-install-now.1/install-now.sh -o "$d/install-now.sh" && bash "$d/install-now.sh")
```

De opdracht gebruikt een nieuwe afgeschermde tijdelijke map; een bestaand lokaal `install-now.sh` wordt niet overschreven. Het downloadbestand wordt na afloop verwijderd. Geen download wordt rechtstreeks naar Bash gepiped; downloads en redirects zijn uitsluitend HTTPS.

**Vertrouwensgrens:** het eerste `install-now.sh` wordt met deze korte methode via HTTPS gedownload en uitgevoerd zonder onafhankelijke checksumcontrole. HTTPS is hier de eerste vertrouwensbasis. Het script controleert daarna de bestaande Bash.4-bootstrap wél met een vastgepinde SHA256 vóór uitvoering. Gebruik het beveiligingsalternatief hieronder als u vanaf de eerste uitvoeringsstap een checksum-pin wilt.

Het script controleert vereisten, download en checksum. De bestaande bootstrap vraagt `ja` vóór registratie van de persistente launcher. Dit installeert geen serverprofiel. Start na succesvolle registratie zelf:

```bash
install-now
```

## Beveiligingsalternatief: bestaande vastgepinde opdracht

Deze opdracht controleert de Bash.4-bootstrap vóór uitvoering en gebruikt dezelfde registratieketen:

```bash
bash -c set\ -Eeuo\ pipefail\;\ trap\ \'printf\ \"FAIL\ bootstrapdownload\ of\ validatie\\n\"\ \>\&2\'\ ERR\;\ umask\ 077\;\ command\ -v\ curl\ \>/dev/null\;\ command\ -v\ sha256sum\ \>/dev/null\;\ exec\ 3\<\>/dev/tty\;\ w=\$\(mktemp\ -d\ \"\$\{TMPDIR:-/tmp\}/uli-loader.XXXXXXXX\"\)\;\ trap\ \'rm\ -rf\ --\ \"\$w\"\'\ EXIT\;\ curl\ -q\ --fail\ --location\ --proto\ =https\ --proto-redir\ =https\ --connect-timeout\ 30\ --max-time\ 300\ --max-filesize\ 262144\ \"https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-bash.4/bootstrap.sh\"\ --output\ \"\$w/bootstrap.sh\"\;\ \[\[\ -f\ \$w/bootstrap.sh\ \&\&\ \!\ -L\ \$w/bootstrap.sh\ \&\&\ \$\(wc\ -c\ \<\ \"\$w/bootstrap.sh\"\)\ -le\ 262144\ \]\]\;\ printf\ \'51f6681f01ffc7c2c007266f7c98ba354972ed4139fc50034b1fc46d349c109d\ \ %s\\n\'\ \"\$w/bootstrap.sh\"\ \|\ sha256sum\ --check\ --status\;\ bash\ -n\ \"\$w/bootstrap.sh\"\;\ bash\ \"\$w/bootstrap.sh\"\ \"\$@\"\ \<\&3\ \>\&3\ 2\>\&3 install-now --register-install-now
```

De launcher downloadt steeds dezelfde Bash.4-release en controleert de archiefhash vóór uitvoering. Het bestaande menu biedt APP, DATABASE, gecombineerd, status en afsluiten; installatie vereist afzonderlijke bevestiging van het installatieplan. Afwijkende bestaande launcherbestanden worden niet overschreven.

- [Nieuw registratiescript](https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-install-now.1/install-now.sh) — SHA256 `9a975f55b0d9a43be705a2233c3183ae8862b7c2981697cbceb3d64bdf281a5d`
- [Checksums van het registratiescript](https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-install-now.1/SHA256SUMS)
- [Bash.4-bootstrap](https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-bash.4/bootstrap.sh) — SHA256 `51f6681f01ffc7c2c007266f7c98ba354972ed4139fc50034b1fc46d349c109d`
- [Bash.4-releasearchief](https://github.com/jantodjamin-lab/linux-server-installer/releases/download/v1.0.0-bash.4/universal-linux-installer-1.0.0-bash.4.tar.gz) — SHA256 `3e86da621994748b5687dd5edd35948328e9e2eb6a712185a150402a46baa931`

De oorspronkelijke Bash.4-assets en installermotor blijven ongewijzigd. Een exacte herregistratie is idempotent; bestaande afwijkende registraties worden veilig geweigerd. Nieuwe releaseversies worden niet automatisch geselecteerd.
