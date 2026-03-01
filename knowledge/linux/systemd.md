# Linux – Zarządzanie usługami (systemd)

## Podstawowe komendy systemctl

```bash
systemctl start nginx           # uruchom usługę
systemctl stop nginx            # zatrzymaj usługę
systemctl restart nginx         # zrestartuj usługę
systemctl reload nginx          # przeładuj konfigurację (bez restartu)
systemctl status nginx          # sprawdź status usługi
systemctl enable nginx          # włącz autostart przy starcie systemu
systemctl disable nginx         # wyłącz autostart
systemctl is-active nginx       # czy usługa jest uruchomiona?
systemctl is-enabled nginx      # czy autostart jest włączony?
```

## Lista usług

```bash
systemctl list-units --type=service          # wszystkie załadowane usługi
systemctl list-units --type=service --state=running  # tylko uruchomione
systemctl list-unit-files --type=service     # wszystkie pliki unit
```

## Tworzenie własnej usługi systemd

Plik: `/etc/systemd/system/moja-aplikacja.service`

```ini
[Unit]
Description=Moja Aplikacja
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/moja-aplikacja
ExecStart=/opt/moja-aplikacja/run.sh
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Po stworzeniu pliku:
```bash
systemctl daemon-reload         # przeładuj daemon
systemctl enable moja-aplikacja # włącz autostart
systemctl start moja-aplikacja  # uruchom
```

## Timery systemd (alternatywa dla crona)

Plik: `/etc/systemd/system/moj-timer.timer`

```ini
[Unit]
Description=Mój timer

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl list-timers           # lista aktywnych timerów
```
