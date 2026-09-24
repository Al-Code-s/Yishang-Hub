# 意尚智造集成平台 · Docker 部署的端口与局域网访问配置
#
# 把根目录 .env 里的 4 项按本机实际情况改好，解决两件事：
#   1) 端口冲突：本机 Docker 已跑别的服务时，自动挑一个空闲端口（或用 -Port 指定）；
#   2) 局域网访问：把本机局域网 IP 写进 ALLOWED_HOSTS / CSRF 来源，
#      否则局域网内其他电脑打开会 400，或登录时报 CSRF 失败。
#
# 用法（在仓库根目录执行）：
#   powershell -ExecutionPolicy Bypass -File scripts\docker_network.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\docker_network.ps1 -Port 18080
#   powershell -ExecutionPolicy Bypass -File scripts\docker_network.ps1 -Ip 192.168.1.50 -Port 8080
#   powershell -ExecutionPolicy Bypass -File scripts\docker_network.ps1 -KeepPort   # 平台已在运行，只更新 IP / 白名单
#
# 改完必须重建容器才生效：docker compose up -d

[CmdletBinding()]
param(
    [int]$Port = 0,
    [string]$Ip = '',
    # 不改端口：只刷新 IP 与白名单（平台自己的 nginx 已占着该端口时用这个）
    [switch]$KeepPort
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root '.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    throw "找不到 $envPath；请确认在仓库根目录执行，且根目录 .env 存在。"
}

function Get-LanIp {
    try {
        $udp = New-Object System.Net.Sockets.UdpClient
        $udp.Connect('8.8.8.8', 53)
        $candidate = $udp.Client.LocalEndPoint.Address.ToString()
        $udp.Close()
        if ($candidate -and $candidate -notlike '127.*') { return $candidate }
    } catch {
        # 没有默认路由时用 DNS 兜底
    }
    try {
        $addresses = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
            Where-Object {
                $_.AddressFamily -eq 'InterNetwork' -and
                $_.ToString() -notlike '127.*' -and
                $_.ToString() -notlike '169.254.*'
            }
        if ($addresses) { return $addresses[0].ToString() }
    } catch { }
    return ''
}

function Test-PortFree([int]$Candidate) {
    if (Get-NetTCPConnection -State Listen -LocalPort $Candidate -ErrorAction SilentlyContinue) {
        return $false
    }
    # PS 5.1 在 ErrorActionPreference=Stop 时会把外部命令的 stderr 警告当终止错误，这里临时放开
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $hits = netstat -ano 2>$null | Select-String -Pattern (':{0}\s' -f $Candidate)
    }
    finally {
        $ErrorActionPreference = $previous
    }
    return -not $hits
}

if (-not $Ip) { $Ip = Get-LanIp }
if (-not $Ip) {
    throw '没能自动识别本机局域网 IP；请用 -Ip 192.168.1.50 这样的参数手动指定。'
}
if ($Ip -notmatch '^\d{1,3}(\.\d{1,3}){3}$') {
    throw "IP 格式不对：$Ip"
}

$text = [System.IO.File]::ReadAllText($envPath, [System.Text.Encoding]::UTF8)
$current = ''
if ($text -match '(?m)^HTTP_PORT=(\d+)') { $current = $Matches[1] }

$candidates = @()
if ($Port -gt 0) {
    $candidates = @($Port)
} else {
    if ($current) { $candidates += [int]$current }
    $candidates += @(8080, 8081, 8088, 9080, 18080, 28080, 80)
    $candidates = $candidates | Select-Object -Unique
}

$chosen = 0
if ($KeepPort) {
    if (-not $current) { throw '-KeepPort 需要 .env 里已经有 HTTP_PORT；请先不带该参数跑一次。' }
    $chosen = [int]$current
} else {
    foreach ($candidate in $candidates) {
        if (Test-PortFree $candidate) { $chosen = $candidate; break }
    }
}

if ($chosen -eq 0) {
    if ($Port -gt 0) {
        throw "端口 $Port 已被占用。可以这样查占用：Get-NetTCPConnection -State Listen -LocalPort $Port"
    }
    throw '候选端口都被占用了，请用 -Port 指定一个空闲端口。'
}

$hosts = "localhost,127.0.0.1,$Ip"
$origins = @('http://localhost:5173', 'http://127.0.0.1:5173')
if ($chosen -eq 80) {
    $origins += @('http://localhost', 'http://127.0.0.1', "http://$Ip")
} else {
    $origins += @("http://localhost`:$chosen", "http://127.0.0.1`:$chosen", "http://$Ip`:$chosen")
}
$origins = $origins -join ','

$lines = $text -split "\r?\n"
$hasSection = @($lines | Where-Object { $_ -match '^# ---------- 对外访问' }).Count -gt 0
if (-not $hasSection) {
    $lines += @(
        '',
        '# ---------- 对外访问（端口 / 局域网，由 scripts/docker_network.ps1 维护）----------',
        '# 宿主端口 → 容器内 nginx 8080；被别的服务占用就改这里（改完 docker compose up -d 生效）',
        '# 监听地址：0.0.0.0 = 本机与局域网都能访问；127.0.0.1 = 只有本机能访问'
    )
}
$wanted = [ordered]@{
    HTTP_PORT                   = "$chosen"
    HTTP_BIND                   = '0.0.0.0'
    DJANGO_ALLOWED_HOSTS        = $hosts
    DJANGO_CSRF_TRUSTED_ORIGINS = $origins
}
foreach ($key in $wanted.Keys) {
    $done = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match ('^' + [regex]::Escape($key) + '=')) {
            $lines[$i] = "$key=" + $wanted[$key]
            $done = $true
            break
        }
    }
    if (-not $done) { $lines += ("$key=" + $wanted[$key]) }
}
[System.IO.File]::WriteAllText($envPath, ($lines -join "`n"), (New-Object System.Text.UTF8Encoding($false)))

Write-Host ''
Write-Host "已更新 $envPath"
Write-Host "  HTTP_PORT                   = $chosen"
Write-Host '  HTTP_BIND                   = 0.0.0.0'
Write-Host "  DJANGO_ALLOWED_HOSTS        = $hosts"
Write-Host "  DJANGO_CSRF_TRUSTED_ORIGINS = $origins"
Write-Host ''
Write-Host "本机访问：   http://localhost`:$chosen/"
Write-Host "局域网访问： http://${Ip}:$chosen/    （同一局域网的其他电脑用这个）"
Write-Host ''
Write-Host '接下来执行：docker compose up -d    （重建 nginx 容器，端口映射才会生效）'
Write-Host ''
Write-Host '若局域网其他电脑打不开，用【管理员】PowerShell 放行端口：'
Write-Host "  New-NetFirewallRule -DisplayName 'Yishang Platform HTTP' -Direction Inbound -Protocol TCP -LocalPort $chosen -Action Allow"