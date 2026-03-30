# windows-generic
version: any
os: windows
loaded_when: Windows detectat

## Detectie
```powershell
systeminfo | findstr /B /C:"OS Name" /C:"OS Version"
winver
```

## Remote execution
```bash
# WinRM din Linux
evil-winrm -i <ip> -u <user> -p <parola>
# sau
python3 -m impacket.wmiexec <user>:<parola>@<ip>
```

## Comenzi de baza remote
```powershell
Get-Service | Where-Object {$_.Status -eq "Running"}
Get-Process | Sort-Object CPU -Descending | Select -First 10
Get-EventLog -LogName System -Newest 20
ipconfig /all
netstat -ano
```

## Gotchas
- WinRM trebuie activat: `Enable-PSRemoting -Force`
- Firewall poate bloca port 5985/5986
- Credentiale domain: user@domain sau DOMAIN\user
- Mai mult se adauga pe masura ce lucram cu masini Windows reale
