<#
.SYNOPSIS
    Goi thu POST /api/v1/condition-relation/decide (P1 Condition Relation) voi du lieu mau.

.DESCRIPTION
    Doc payload tu examples/p1_request.json (service_platform: laya) va gui toi API PoC
    dang chay tai BaseUrl. In ket qua JSON tra ve.

.PARAMETER BaseUrl
    Dia chi goc cua API PoC. Mac dinh http://127.0.0.1:8010.

.EXAMPLE
    .\test_p1_endpoint.ps1
    .\test_p1_endpoint.ps1 -BaseUrl http://127.0.0.1:8010
#>
param(
    [string]$BaseUrl = "http://127.0.0.1:8010"
)

$ErrorActionPreference = "Stop"
$payloadPath = Join-Path $PSScriptRoot "..\examples\p1_request.json"
$url = "$BaseUrl/api/v1/condition-relation/decide"

if (-not (Test-Path $payloadPath)) {
    Write-Error "Khong tim thay file mau: $payloadPath"
    exit 1
}

$body = Get-Content -Raw -Encoding UTF8 -Path $payloadPath
$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($body)

Write-Output "POST $url"
Write-Output "--- request (examples/p1_request.json) ---"
Write-Output $body
Write-Output ""

try {
    $response = Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json; charset=utf-8" -Body $bodyBytes
    Write-Output "--- response ---"
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Output "--- loi ---"
    Write-Output $_.Exception.Message
    if ($_.ErrorDetails.Message) {
        Write-Output $_.ErrorDetails.Message
    }
    exit 1
}
