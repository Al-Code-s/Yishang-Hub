# 意尚智造集成平台 · Docker 容器数据库的导出 / 导入
#
# 容器里的 MySQL 是【独立实例】（数据在 Docker 卷 yishang-platform_mysql-data 里），
# 与宿主的开发库互不影响。本脚本用来在两边搬数据、以及给容器数据做备份：
#   Export：把容器库导成 db/yishang_platform_<日期>.sql（备份 / 搬到别的机器 / 带回开发库）
#   Import：把 .sql 导进容器库（会先等 MySQL 健康检查通过，避免「ERROR 2002 ... socket」那种失败）
#
# 用法（在仓库根目录执行）：
#   powershell -ExecutionPolicy Bypass -File scripts\docker_db.ps1 -Action Export
#   powershell -ExecutionPolicy Bypass -File scripts\docker_db.ps1 -Action Export -OutFile db\yishang_platform_2026-09-25.sql
#   powershell -ExecutionPolicy Bypass -File scripts\docker_db.ps1 -Action Import -File db\yishang_platform_2026-09-24.sql
#
# 提醒：
#   * 导出文件含业务数据，默认落在 db\ 下（**不要**发到公开网盘）；
#   * 导入用的快照自带 DROP TABLE IF EXISTS，**重复导入会覆盖同名表的数据**；
#   * docker compose down -v 会删掉数据卷（容器数据全没），日常重启不会。

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Export', 'Import')]
    [string]$Action,

    # Import 用：要导入的 .sql 文件
    [string]$File = '',

    # Export 用：导出到哪个文件（默认 db\yishang_platform_<今天>.sql）
    [string]$OutFile = '',

    # Export 用：允许覆盖已存在的文件
    [switch]$Force,

    # 等待 MySQL 就绪的最长秒数（Import 用）
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$envPath = Join-Path $root '.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    throw "找不到 $envPath；请在仓库根目录执行。"
}

$script:LastExitCode = 0

function Get-EnvValue {
    param([string]$Key, [string]$Default = '')
    $text = [System.IO.File]::ReadAllText($envPath, [System.Text.Encoding]::UTF8)
    if ($text -match ('(?m)^' + [regex]::Escape($Key) + '=(.*)$')) {
        $value = $Matches[1].Trim()
        if ($value) { return $value }
    }
    return $Default
}

function Resolve-RepoPath {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) { return $Path }
    return (Join-Path $root $Path)
}

# 调用外部命令。Windows PowerShell 5.1 在 $ErrorActionPreference='Stop' 时会把外部命令写到
# stderr 的普通警告（例如 docker 的 "WARNING: Error loading config file"）当成终止错误，
# 这里临时放开，改为按退出码自行判断。
function Invoke-Docker {
    param([string[]]$DockerArgs, [switch]$Quiet)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($Quiet) {
            $output = & docker @DockerArgs 2>$null
        }
        else {
            $output = & docker @DockerArgs
        }
        $script:LastExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }
    return $output
}

function Invoke-Compose {
    param([string[]]$ComposeArgs)
    $output = Invoke-Docker -DockerArgs (@('compose') + $ComposeArgs)
    if ($script:LastExitCode -ne 0) {
        throw ('docker compose ' + ($ComposeArgs -join ' ') + " 执行失败（exit $script:LastExitCode）。")
    }
    return $output
}

function Assert-DockerUsable {
    $null = Invoke-Docker -DockerArgs @('compose', 'version') -Quiet
    if ($script:LastExitCode -ne 0) {
        throw 'docker compose 不可用：确认 Docker Desktop 已启动，并在有权限访问它的终端里执行。'
    }
}

function Assert-MysqlRunning {
    Assert-DockerUsable
    $services = Invoke-Docker -DockerArgs @('compose', 'ps', '--status', 'running', '--services') -Quiet
    if ($script:LastExitCode -ne 0) {
        throw 'docker compose ps 执行失败：请确认当前目录是仓库根目录、Docker Desktop 已启动。'
    }
    if ($services -notcontains 'mysql') {
        throw 'MySQL 容器没有在运行。先执行：docker compose up -d --wait mysql'
    }
}

function Wait-MysqlHealthy {
    param([int]$Seconds = 180)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        $hit = Invoke-Docker -DockerArgs @('compose', 'ps', 'mysql') -Quiet |
            Select-String -Pattern 'healthy' -SimpleMatch
        if ($hit) {
            Write-Host '  MySQL 已就绪（healthy）'
            return
        }
        Start-Sleep -Seconds 3
    }
    throw "等待 MySQL 就绪超时（$Seconds 秒）。先看 docker compose ps mysql 与 docker compose logs mysql。"
}

$dbName = Get-EnvValue 'DB_NAME' 'yishang_platform'
$containerTmp = '/tmp/yishang_script_db.sql'

if ($Action -eq 'Export') {
    Assert-MysqlRunning

    $target = if ($OutFile) { $OutFile } else { 'db\yishang_platform_' + (Get-Date -Format 'yyyy-MM-dd') + '.sql' }
    $target = Resolve-RepoPath $target
    if ((Test-Path -LiteralPath $target) -and (-not $Force)) {
        throw "$target 已存在；确认要覆盖请加 -Force，或用 -OutFile 指定别的文件名。"
    }
    $parent = Split-Path -Parent $target
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    Write-Host "正在导出容器库 $dbName ..."
    $dumpCmd = 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction ' +
        '--default-character-set=utf8mb4 --routines --triggers ' + $dbName + ' > ' + $containerTmp
    $null = Invoke-Compose -ComposeArgs @('exec', '-T', 'mysql', 'sh', '-c', $dumpCmd)
    $null = Invoke-Compose -ComposeArgs @('cp', ('mysql:' + $containerTmp), $target)
    $null = Invoke-Compose -ComposeArgs @('exec', '-T', 'mysql', 'rm', '-f', $containerTmp)

    $info = Get-Item -LiteralPath $target
    if ($info.Length -lt 1024) {
        throw "导出文件只有 $($info.Length) 字节，看起来不对；请检查上面的 mysqldump 输出。"
    }
    $tables = (Select-String -LiteralPath $target -Pattern '^CREATE TABLE' -Encoding utf8).Count

    Write-Host ''
    Write-Host "已导出：$target"
    Write-Host ('  大小：{0:N0} 字节    表数：{1}' -f $info.Length, $tables)
    Write-Host ''
    Write-Host '这份导出就是容器数据的备份（含业务数据，不要外发）。'
    Write-Host '注意：docker compose down -v 会删掉数据卷，日常重启用 docker compose down / restart 即可。'
    exit 0
}

if (-not $File) {
    throw 'Import 需要指定 -File，例如：-File db\yishang_platform_2026-09-24.sql'
}
$source = Resolve-RepoPath $File
if (-not (Test-Path -LiteralPath $source)) {
    throw "找不到要导入的文件：$source"
}

Write-Host '确保 MySQL 已启动并健康 ...'
$null = Invoke-Compose -ComposeArgs @('up', '-d', '--wait', 'mysql')
Wait-MysqlHealthy -Seconds $TimeoutSeconds

Write-Host "正在导入 $source 到容器库 $dbName ..."
$null = Invoke-Compose -ComposeArgs @('cp', $source, ('mysql:' + $containerTmp))
$importCmd = 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot ' + $dbName + ' < ' + $containerTmp
$null = Invoke-Compose -ComposeArgs @('exec', '-T', 'mysql', 'sh', '-c', $importCmd)
$null = Invoke-Compose -ComposeArgs @('exec', '-T', 'mysql', 'rm', '-f', $containerTmp)

Write-Host ''
Write-Host '导入完成。核对一下（表数应为 154、用户数应为 15）：'
Write-Host "  docker compose exec mysql sh -c 'MYSQL_PWD=`$MYSQL_ROOT_PASSWORD` mysql -uroot $dbName -e ""select (select count(*) from identity_user) users, (select count(*) from information_schema.tables where table_schema=database()) tables_""'"
Write-Host ''
Write-Host '若数字不对，检查导入的是否为正确的快照文件；重复导入会覆盖同名表的数据。'