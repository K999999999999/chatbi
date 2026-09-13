[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot ".env"

function Test-ListeningPort {
    param(
        [Parameter(Mandatory)]
        [int]$Port
    )

    $listener = Get-NetTCPConnection `
        -State Listen `
        -LocalPort $Port `
        -ErrorAction SilentlyContinue `
        | Select-Object -First 1
    return $null -ne $listener
}

function Get-PowerShellExecutable {
    $pwsh = Get-Command "pwsh.exe" -ErrorAction SilentlyContinue
    if ($null -ne $pwsh) {
        return $pwsh.Source
    }

    $windowsPowerShell = Get-Command "powershell.exe" -ErrorAction Stop
    return $windowsPowerShell.Source
}

function Start-DevTerminal {
    param(
        [Parameter(Mandatory)]
        [string]$Title,

        [Parameter(Mandatory)]
        [string]$Command
    )

    $escapedProjectRoot = $projectRoot.Replace("'", "''")
    $escapedTitle = $Title.Replace("'", "''")
    $terminalCommand = @"
Set-Location -LiteralPath '$escapedProjectRoot'
try { `$Host.UI.RawUI.WindowTitle = '$escapedTitle' } catch {}
$Command
"@
    $encodedCommand = [Convert]::ToBase64String(
        [Text.Encoding]::Unicode.GetBytes($terminalCommand)
    )

    Start-Process `
        -FilePath (Get-PowerShellExecutable) `
        -ArgumentList @("-NoProfile", "-NoExit", "-EncodedCommand", $encodedCommand) `
        -WorkingDirectory $projectRoot `
        -WindowStyle Normal | Out-Null
}

function Test-HttpReady {
    param(
        [Parameter(Mandatory)]
        [string]$Uri
    )

    try {
        $response = Invoke-WebRequest `
            -Uri $Uri `
            -UseBasicParsing `
            -TimeoutSec 2 `
            -ErrorAction Stop
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot "pyproject.toml"))) {
    throw "无法定位 ChatBI 项目根目录。"
}
if (-not (Test-Path -LiteralPath $envFile)) {
    throw "缺少项目根目录 .env，请先根据 .env.example 创建本地配置。"
}
if ($null -eq (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    throw "未找到 uv，请先安装或加入 PATH。"
}
if ($null -eq (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    throw "未找到 Docker，请先启动 Docker Desktop。"
}

Push-Location $projectRoot
try {
    Write-Host "正在确认 PostgreSQL 和 Qdrant..."
    & docker compose --env-file $envFile up -d postgres qdrant
    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL/Qdrant 启动失败，请查看 Docker 输出。"
    }
}
finally {
    Pop-Location
}

$apiPortInUse = Test-ListeningPort -Port 8000
$uiPortInUse = Test-ListeningPort -Port 8501

if ($apiPortInUse) {
    Write-Warning "端口 8000 已被占用，跳过启动 FastAPI；不会终止现有进程。"
}
else {
    Write-Host "正在打开 FastAPI 终端..."
    Start-DevTerminal `
        -Title "ChatBI FastAPI" `
        -Command "uv run --env-file .env uvicorn src.query_api.main:app --host 127.0.0.1 --port 8000"
}

if ($uiPortInUse) {
    Write-Warning "端口 8501 已被占用，跳过启动 Streamlit；不会终止现有进程。"
}
else {
    Write-Host "正在打开 Streamlit 终端..."
    Start-DevTerminal `
        -Title "ChatBI Streamlit" `
        -Command "uv run --env-file .env streamlit run src/streamlit_app.py --server.address 127.0.0.1 --server.port 8501"
}

$checks = @(
    [pscustomobject]@{
        Name = "FastAPI"
        Uri = "http://127.0.0.1:8000/health"
        Ready = $false
    },
    [pscustomobject]@{
        Name = "Streamlit"
        Uri = "http://127.0.0.1:8501/_stcore/health"
        Ready = $false
    }
)
$deadline = [DateTime]::UtcNow.AddSeconds(30)

while ([DateTime]::UtcNow -lt $deadline) {
    foreach ($check in $checks) {
        if (-not $check.Ready) {
            $check.Ready = Test-HttpReady -Uri $check.Uri
        }
    }
    if (@($checks | Where-Object { -not $_.Ready }).Count -eq 0) {
        break
    }
    Start-Sleep -Seconds 1
}

foreach ($check in $checks) {
    if ($check.Ready) {
        Write-Host "[OK] $($check.Name): $($check.Uri)"
    }
    else {
        Write-Warning "$($check.Name) 未在 30 秒内就绪，请查看对应终端输出。"
    }
}

if (@($checks | Where-Object { -not $_.Ready }).Count -gt 0) {
    exit 1
}

Write-Host "ChatBI 本地开发服务已启动。"
Write-Host "页面地址：http://127.0.0.1:8501"
Write-Host "停止服务：在两个服务终端中分别按 Ctrl+C。"
