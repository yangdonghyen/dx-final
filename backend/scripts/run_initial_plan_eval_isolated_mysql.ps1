<#
Initial itinerary generation evaluation on a MySQL instance created for this
invocation only (same structure as run_task74c_isolated_mysql.ps1).

  -Provider Mock  (default) no Ollama call; checks environment and result files
  -Provider Real  calls the configured Ollama EXAONE model once
  -RouteProvider Unavailable (default) records no route facts
  -RouteProvider Mock uses deterministic offline route facts
  -RouteProvider Kakao opt-in: calls Kakao only during this user-run evaluation

It never touches the MySQL80 service, FastAPI, Flutter or Ollama processes:
the only process it stops is the mysqld it started (proved by its own pid-file).
Credentials are never written to disk or console.
#>
[CmdletBinding()]
param(
    [ValidateSet("Jeju", "Busan", "Trip76")]
    [string]$Trip = "Jeju",
    [ValidateSet("Mock", "Real", "Replay")]
    [string]$Provider = "Mock",
    # With -Provider Replay: result.json of an earlier real run to re-feed (no network).
    [string]$ReplayResult = "",
    # Export: saved trip places only.  Fixture: + synthetic search results (Mock only).
    # Kakao: + real Kakao place search (user-run only; needs the local Kakao key).
    [ValidateSet("Export", "Fixture", "Kakao")]
    [string]$Candidates = "Export",
    [ValidateSet("Unavailable", "Mock", "Kakao")]
    [string]$RouteProvider = "Unavailable",
    [string]$Python = "python",
    [string]$MySqlBin = "C:\Program Files\MySQL\MySQL Server 8.0\bin",
    [double]$AiTimeoutSeconds = 0,
    [switch]$PreflightOnly,
    [switch]$KeepInstanceFiles
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$backendRoot = Join-Path $projectRoot "backend"
$mysqld = Join-Path $MySqlBin "mysqld.exe"
$mysql = Join-Path $MySqlBin "mysql.exe"
$mySqlBase = Split-Path -Parent $MySqlBin
if (-not (Test-Path -LiteralPath $mysqld) -or -not (Test-Path -LiteralPath $mysql)) {
    throw "MySQL 8 binaries were not found. Pass -MySqlBin with the MySQL bin directory."
}

function New-StrongPassword {
    $bytes = [byte[]]::new(32)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) }
    finally { $rng.Dispose() }
    return ([Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "A").Replace("/", "B") + "a1!")
}

function Get-FreeLoopbackPort {
    for ($candidate = 34000; $candidate -lt 35000; $candidate++) {
        $listener = [System.Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $candidate)
        try {
            $listener.Start()
            return $candidate
        }
        catch [System.Net.Sockets.SocketException] {
            continue
        }
        finally {
            $listener.Stop()
        }
    }
    throw "No unused loopback port was found in the dedicated 34000-34999 range."
}

function Invoke-MySql([string[]]$Arguments) {
    & $mysql @Arguments
    if ($LASTEXITCODE -ne 0) { throw "mysql client command failed without exposing connection details." }
}

# Read-only facts about the production MySQL80 service (its my.ini), used only
# to refuse a run that could overlap it.  The service is never queried or changed.
function Get-ProductionMySqlFacts {
    $facts = @{ Port = 3306; DataDir = $null }
    $service = Get-CimInstance Win32_Service -Filter "Name='MySQL80'" -ErrorAction SilentlyContinue
    if ($null -eq $service -or $service.PathName -notmatch '--defaults-file="?([^"]+)"?') { return $facts }
    $ini = $Matches[1]
    if (-not (Test-Path -LiteralPath $ini)) { return $facts }
    $section = ""
    foreach ($line in Get-Content -LiteralPath $ini) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^\[(.+)\]$') { $section = $Matches[1].ToLowerInvariant(); continue }
        if ($section -ne "mysqld") { continue }
        if ($trimmed -match '^port\s*=\s*(\d+)') { $facts.Port = [int]$Matches[1] }
        if ($trimmed -match '^datadir\s*=\s*"?([^"]+)"?') { $facts.DataDir = [IO.Path]::GetFullPath($Matches[1].Trim().Replace('/', '\')).TrimEnd('\') }
    }
    return $facts
}

$runId = [Guid]::NewGuid().ToString("N")
$instanceParent = Join-Path $projectRoot ".initial_plan_eval_mysql"
$instanceRoot = Join-Path $instanceParent $runId
$dataDir = Join-Path $instanceRoot "data"
$errorLog = Join-Path $instanceRoot "mysql-error.log"
$pidFile = Join-Path $instanceRoot "mysql.pid"
$configFile = Join-Path $instanceRoot "my.ini"
$port = Get-FreeLoopbackPort
$sharedMemoryName = "initial_plan_eval_" + $runId
$database = "initial_plan_eval_" + $runId.Substring(0, 12)
$testUser = "initial_plan_eval"
$password = New-StrongPassword
$server = $null
$trailingPathSeparators = [char[]]@('\', '/')

# Pre-flight isolation checks: stop before anything is created.
$production = Get-ProductionMySqlFacts
$expectedDataDir = [IO.Path]::GetFullPath($dataDir).TrimEnd($trailingPathSeparators)
if ($port -eq 3306 -or $port -eq $production.Port) { throw "Refusing to run: selected port $port is the production MySQL port." }
if ($production.DataDir -and $expectedDataDir.StartsWith($production.DataDir, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to run: isolated datadir would be inside the production MySQL datadir."
}
if (Test-Path -LiteralPath $instanceRoot) { throw "Refusing to reuse an existing instance directory." }
Write-Host "Pre-flight: production MySQL80 port=$($production.Port) (not used); isolated port=$port"

try {
    New-Item -ItemType Directory -Path $instanceRoot -Force:$false | Out-Null
    & $mysqld "--no-defaults" "--initialize-insecure" "--basedir=$mySqlBase" "--datadir=$dataDir" *> $null
    if ($LASTEXITCODE -ne 0) { throw "MySQL initialization failed. See the isolated instance error log." }

    $iniDataDir = $dataDir.Replace('\', '/')
    $iniErrorLog = $errorLog.Replace('\', '/')
    $iniPidFile = $pidFile.Replace('\', '/')
    $iniBaseDir = $mySqlBase.Replace('\', '/')
    @"
[mysqld]
basedir="$iniBaseDir"
datadir="$iniDataDir"
port=$port
bind-address=127.0.0.1
skip-name-resolve
shared-memory
shared-memory-base-name=$sharedMemoryName
pid-file="$iniPidFile"
log-error="$iniErrorLog"
character-set-server=utf8mb4
collation-server=utf8mb4_0900_ai_ci
"@ | Set-Content -LiteralPath $configFile -Encoding ascii
    $server = Start-Process -FilePath $mysqld -ArgumentList "--defaults-file=$configFile" -PassThru -WindowStyle Hidden

    $ready = $false
    $lastProbeError = ""
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $server.Refresh()
        if ($server.HasExited) {
            throw "Isolated mysqld exited early. ExitCode=$($server.ExitCode); Log=$errorLog"
        }
        $previousErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $probeOutput = & $mysql "--no-defaults" "--host=localhost" "--protocol=MEMORY" "--shared-memory-base-name=$sharedMemoryName" "--user=root" "--batch" "--skip-column-names" "-e" "SELECT 1" 2>&1
        $probeExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorPreference
        if ($probeExitCode -ne 0) {
            $probeMessages = @($probeOutput | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
            $lastProbeError = "exit=$probeExitCode " + ($probeMessages -join " | ")
        }
        if ($probeExitCode -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "The new isolated MySQL instance did not become ready within 60 seconds. Last probe error: $lastProbeError; Log=$errorLog" }

    $bootstrapSql = "CREATE DATABASE ``$database`` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; CREATE USER '$testUser'@'127.0.0.1' IDENTIFIED BY '$password'; GRANT ALL PRIVILEGES ON ``$database``.* TO '$testUser'@'127.0.0.1'; FLUSH PRIVILEGES;"
    Invoke-MySql @("--no-defaults", "--host=localhost", "--protocol=MEMORY", "--shared-memory-base-name=$sharedMemoryName", "--user=root", "-e", $bootstrapSql)

    $env:MYSQL_PWD = $password
    $verification = & $mysql "--no-defaults" "--protocol=TCP" "--host=127.0.0.1" "--port=$port" "--user=$testUser" "--database=$database" "--batch" "--skip-column-names" "-e" "SELECT @@port, @@datadir, DATABASE(), CURRENT_USER();"
    if ($LASTEXITCODE -ne 0) { throw "Unable to verify the isolated MySQL connection." }
    $facts = $verification -split "`t"
    $actualDataDir = [IO.Path]::GetFullPath($facts[1]).TrimEnd($trailingPathSeparators)
    $expectedCurrentUser = "$testUser@127.0.0.1"
    $targetMatches = $facts.Count -eq 4 -and [int]$facts[0] -eq $port -and $actualDataDir -eq $expectedDataDir -and $facts[2] -eq $database -and $facts[3] -eq $expectedCurrentUser
    if (-not $targetMatches -or [int]$facts[0] -eq $production.Port -or ($production.DataDir -and $actualDataDir -eq $production.DataDir)) {
        throw "MySQL target verification failed; the evaluation will not run."
    }
    Write-Host "Isolated MySQL verified: port=$port datadir=$actualDataDir database=$($facts[2]) current_user=$($facts[3])"

    $encodedPassword = [Uri]::EscapeDataString($password)
    $env:INITIAL_PLAN_EVAL_MYSQL_URL = "mysql+pymysql://${testUser}:$encodedPassword@127.0.0.1:${port}/${database}?charset=utf8mb4"
    $env:INITIAL_PLAN_EVAL_MYSQL_DATADIR = $expectedDataDir
    # Process-level values override backend/.env, so every app code path points here.
    $env:MYSQL_HOST = "127.0.0.1"
    $env:MYSQL_PORT = "$port"
    $env:MYSQL_DATABASE = $database
    $env:MYSQL_USER = $testUser
    $env:MYSQL_PASSWORD = $password
    $env:JWT_SECRET_KEY = New-StrongPassword
    $env:PLACE_PROVIDER = $(if ($Candidates -eq "Kakao") { "real" } else { "mock" })
    # The Python evaluator receives its own explicit --route-provider option.
    # This setting only permits the real factory for the explicit Kakao case.
    $env:ROUTE_PROVIDER = $(if ($RouteProvider -eq "Kakao") { "kakao" } else { "unavailable" })
    $env:PLAN_PROVIDER = $(if ($Provider -eq "Real") { "real" } else { "mock" })
    if ($AiTimeoutSeconds -gt 0) { $env:AI_API_TIMEOUT_SECONDS = "$AiTimeoutSeconds" }
    $env:PYTHONIOENCODING = "utf-8"

    Push-Location $backendRoot
    try {
        & $Python -B -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "Alembic migration failed." }
        & $Python -B scripts/evaluate_initial_plan_generation.py --trip $Trip.ToLowerInvariant() --provider $Provider.ToLowerInvariant() --candidates $Candidates.ToLowerInvariant() --route-provider $RouteProvider.ToLowerInvariant() $(if ($PreflightOnly) { "--preflight-only" }) $(if ($Provider -eq "Replay") { "--replay"; (Resolve-Path -LiteralPath $ReplayResult).Path })
        if ($LASTEXITCODE -ne 0) { throw "Initial plan evaluation exited with code $LASTEXITCODE." }
    }
    finally {
        Pop-Location
    }
}
finally {
    foreach ($name in "MYSQL_PWD", "MYSQL_PASSWORD", "MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "JWT_SECRET_KEY",
        "INITIAL_PLAN_EVAL_MYSQL_URL", "INITIAL_PLAN_EVAL_MYSQL_DATADIR", "PLAN_PROVIDER", "PLACE_PROVIDER", "ROUTE_PROVIDER", "AI_API_TIMEOUT_SECONDS") {
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }
    # Stop only the mysqld whose pid-file lives in this run's UUID directory.
    $ownedServerPid = $null
    if (Test-Path -LiteralPath $pidFile) {
        $pidText = (Get-Content -LiteralPath $pidFile -Raw).Trim()
        if ($pidText -match '^\d+$') { $ownedServerPid = [int]$pidText }
    }
    if ($null -eq $ownedServerPid -and $null -ne $server) { $ownedServerPid = $server.Id }
    if ($null -ne $ownedServerPid) {
        $ownedProcess = Get-Process -Id $ownedServerPid -ErrorAction SilentlyContinue
        if ($null -ne $ownedProcess -and $ownedProcess.ProcessName -eq "mysqld") {
            Stop-Process -Id $ownedServerPid -Force
            $ownedProcess.WaitForExit(15000) | Out-Null
        }
    }
    # Remove only this run's UUID directory, after confirming it is under the dedicated parent.
    $resolvedRoot = [IO.Path]::GetFullPath($instanceRoot)
    if (-not $KeepInstanceFiles -and $resolvedRoot.StartsWith([IO.Path]::GetFullPath($instanceParent) + "\", [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedRoot)) {
        Remove-Item -LiteralPath $resolvedRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
