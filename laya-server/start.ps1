param(
    [string]$Models = "multilingual",
    [string]$Device = "cpu",
    [int]$Port = 8000
)

$env:LAYA_MODELS = $Models
$env:LAYA_DEVICE = $Device
$env:LAYA_PRELOAD = "1"
$env:LAYA_LOG_LEVEL = "info"
$env:LAYA_PORT = $Port

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\laya-serve.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error "Khong tim thay $venvPython. Chay cai dat theo README.md truoc."
    exit 1
}

Write-Output "Khoi dong laya-serve: models=$Models device=$Device port=$Port"
& $venvPython
