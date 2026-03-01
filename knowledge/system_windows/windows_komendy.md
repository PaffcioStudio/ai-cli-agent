# Windows – Przydatne komendy i narzędzia

## PowerShell – podstawowe komendy

```powershell
# Nawigacja
Get-Location                        # gdzie jestem? (pwd)
Set-Location C:\Users               # cd
Get-ChildItem                       # ls / dir
Get-ChildItem -Hidden               # pokaż ukryte pliki
Get-ChildItem -Recurse *.log        # rekurencyjnie szukaj plików

# Pliki
Copy-Item plik.txt kopia.txt        # cp
Move-Item stary.txt nowy.txt        # mv
Remove-Item plik.txt                # rm
Remove-Item folder -Recurse -Force  # rm -rf
New-Item -ItemType File plik.txt    # touch
New-Item -ItemType Directory folder # mkdir
Get-Content plik.txt                # cat
Add-Content plik.txt "dopisz"       # >> echo
Set-Content plik.txt "nadpisz"      # > echo

# Procesy
Get-Process                         # lista procesów
Get-Process notepad                 # konkretny proces
Stop-Process -Name notepad          # kill po nazwie
Stop-Process -Id 1234               # kill po PID

# Usługi
Get-Service                         # lista usług
Start-Service "nazwa"               # uruchom usługę
Stop-Service "nazwa"                # zatrzymaj
Restart-Service "nazwa"             # restart
Set-Service "nazwa" -StartupType Automatic  # autostart
```

## CMD – klasyczne komendy

```cmd
dir                             # lista plików
dir /a                          # z ukrytymi
cd C:\Users                     # zmień katalog
cls                             # wyczyść ekran
copy plik.txt kopia.txt         # kopiuj
move stary.txt nowy.txt         # przenieś
del plik.txt                    # usuń plik
rmdir /s /q folder              # usuń katalog z zawartością
mkdir nowy_folder               # utwórz katalog
type plik.txt                   # wyświetl plik
ipconfig                        # konfiguracja sieci
ipconfig /all                   # szczegóły sieci
ipconfig /flushdns              # wyczyść cache DNS
ping google.com                 # ping
tracert google.com              # traceroute
netstat -an                     # otwarte porty
tasklist                        # lista procesów
taskkill /PID 1234 /F           # zakończ proces
sfc /scannow                    # sprawdź pliki systemowe
```

## Menedżer pakietów – winget (Windows 10/11)

```powershell
winget search aplikacja             # szukaj aplikacji
winget install Git.Git              # zainstaluj Git
winget install Python.Python.3.12   # zainstaluj Python
winget install Docker.DockerDesktop # Docker
winget install Microsoft.VisualStudioCode  # VS Code
winget upgrade --all                # zaktualizuj wszystko
winget list                         # zainstalowane aplikacje
winget uninstall Git.Git            # odinstaluj
```

## Zmienne środowiskowe

```powershell
# Bieżąca sesja
$env:MOJA_ZMIENNA = "wartość"
echo $env:MOJA_ZMIENNA

# Trwałe (dla użytkownika)
[System.Environment]::SetEnvironmentVariable("KLUCZ", "wartość", "User")

# Trwałe (systemowe – wymaga admina)
[System.Environment]::SetEnvironmentVariable("KLUCZ", "wartość", "Machine")

# Odczyt
[System.Environment]::GetEnvironmentVariable("PATH", "User")
```

## Sieć – diagnostyka

```powershell
# Konfiguracja IP
Get-NetIPAddress                    # wszystkie adresy IP
Get-NetIPAddress -AddressFamily IPv4 # tylko IPv4
Get-NetAdapter                      # karty sieciowe
Get-NetRoute                        # tablica routingu

# Firewall
Get-NetFirewallRule | Where-Object {$_.Enabled -eq "True"}
New-NetFirewallRule -DisplayName "Moja reguła" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
Remove-NetFirewallRule -DisplayName "Moja reguła"
```

## Zadania harmonogramu (Task Scheduler)

```powershell
# Utwórz zaplanowane zadanie
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\skrypt.py"
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00AM"
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "MojSkrypt"

# Zarządzanie
Get-ScheduledTask -TaskName "MojSkrypt"
Start-ScheduledTask -TaskName "MojSkrypt"
Unregister-ScheduledTask -TaskName "MojSkrypt" -Confirm:$false
```

## Przydatne skróty klawiszowe Windows

| Skrót | Działanie |
|-------|-----------|
| Win + E | Eksplorator plików |
| Win + R | Uruchom (Run) |
| Win + X | Menu Power User |
| Win + I | Ustawienia |
| Win + L | Zablokuj ekran |
| Ctrl + Shift + Esc | Menedżer zadań |
| Alt + F4 | Zamknij aplikację |
| Win + D | Pokaż pulpit |
| Win + Tab | Virtual Desktops |
| Win + Shift + S | Zrzut ekranu (Snipping Tool) |
