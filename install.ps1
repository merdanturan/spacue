# spacue installer for Windows -- https://github.com/merdanturan/spacue
#
# spacue is a zsh plugin; on Windows it runs inside WSL. From PowerShell:
#   irm https://raw.githubusercontent.com/merdanturan/spacue/main/install.ps1 | iex
#
# One-time prerequisites if WSL is missing:
#   wsl --install          (then reboot)
#   wsl sh -c "sudo apt update && sudo apt install -y zsh"
$ErrorActionPreference = "Stop"
$repo = "https://raw.githubusercontent.com/merdanturan/spacue/main"

if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
    Write-Host "spacue needs WSL on Windows. Install it first:" -ForegroundColor Yellow
    Write-Host "  wsl --install"
    Write-Host "Then reboot, install zsh inside WSL (wsl sh -c 'sudo apt install -y zsh'),"
    Write-Host "and run this command again."
    exit 1
}

Write-Host "Installing spacue inside WSL..."
wsl sh -c "if command -v curl >/dev/null 2>&1; then curl -fsSL $repo/install.sh | sh; else wget -qO- $repo/install.sh | sh; fi"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installer failed inside WSL. Check that zsh is installed: wsl sh -c 'zsh --version'" -ForegroundColor Red
    exit 1
}
Write-Host "Done. Open a new WSL terminal (or run: wsl zsh) and try:  cd <space>"
