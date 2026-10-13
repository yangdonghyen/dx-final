<#
Runs the complete plan-regeneration MySQL suite in a MySQL instance created
for this invocation only.  It never reuses a datadir or port from another
instance and never writes credentials to disk or console output.
#>
[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$MySqlBin = "C:\Program Files\MySQL\MySQL Server 8.0\bin",
    [switch]$RunRealExaonePreview,
    [switch]$SkipUnit
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
    # Base64url has no SQL quote or URL-reserved characters; suffixes ensure
    # letter, number, and punctuation categories without exposing the value.
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

$runId = [Guid]::NewGuid().ToString("N")
$instanceRoot = Join-Path $projectRoot (".task74c_mysql\" + $runId)
$dataDir = Join-Path $instanceRoot "data"
$errorLog = Join-Path $instanceRoot "mysql-error.log"
$pidFile = Join-Path $instanceRoot "mysql.pid"
$configFile = Join-Path $instanceRoot "my.ini"
$port = Get-FreeLoopbackPort
$sharedMemoryName = "task74c_" + $runId
$database = "plan_regeneration_test_" + $runId.Substring(0, 12)
$testUser = "task74c_runner"
$password = New-StrongPassword
$server = $null

try {
    # This UUID path must not exist; no prior datadir is ever initialized or removed.
    New-Item -ItemType Directory -Path $instanceRoot | Out-Null
    & $mysqld "--no-defaults" "--initialize-insecure" "--basedir=$mySqlBase" "--datadir=$dataDir" *> $null
    if ($LASTEXITCODE -ne 0) { throw "MySQL initialization failed. See the isolated instance error log." }

    # Keep server settings in a per-run config file.  This avoids Windows
    # Start-Process splitting the space in ``C:\Program Files``; no credential
    # is written here, and the file lives only in this unique disposable run.
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

        # A failed pre-readiness TCP attempt is expected and must not terminate
        # the polling loop under this script's strict error preference.
        $previousErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        # --no-defaults: a user/global [client] option file must not change
        # the protocol, user or password of this disposable probe.
        $probeOutput = & $mysql "--no-defaults" "--host=localhost" "--protocol=MEMORY" "--shared-memory-base-name=$sharedMemoryName" "--user=root" "--batch" "--skip-column-names" "-e" "SELECT 1" 2>&1
        $probeExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorPreference
        if ($probeExitCode -ne 0) {
            # The mysql client's own stderr text (no credentials are used here).
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
    $trailingPathSeparators = [char[]]@('\', '/')
    $expectedDataDir = [IO.Path]::GetFullPath($dataDir).TrimEnd($trailingPathSeparators)
    $actualDataDir = [IO.Path]::GetFullPath($facts[1]).TrimEnd($trailingPathSeparators)
    $expectedCurrentUser = "$testUser@127.0.0.1"
    $targetMatches = $facts.Count -eq 4 -and [int]$facts[0] -eq $port -and $actualDataDir -eq $expectedDataDir -and $facts[2] -eq $database -and $facts[3] -eq $expectedCurrentUser
    if (-not $targetMatches) {
        throw "MySQL target verification failed (port=$($facts.Count -eq 4 -and [int]$facts[0] -eq $port); datadir=$($actualDataDir -eq $expectedDataDir); database=$($facts.Count -eq 4 -and $facts[2] -eq $database); current_user=$($facts.Count -eq 4 -and $facts[3] -eq $expectedCurrentUser)); migrations will not run."
    }
    Write-Host "Isolated MySQL verified: port=$port datadir=$actualDataDir database=$($facts[2]) current_user=$($facts[3])"

    $encodedPassword = [Uri]::EscapeDataString($password)
    $env:PLAN_REGENERATION_MYSQL_TEST_URL = "mysql+pymysql://${testUser}:$encodedPassword@127.0.0.1:${port}/${database}?charset=utf8mb4"
    $env:PLAN_REGENERATION_MYSQL_TEST_DATADIR = $expectedDataDir
    $env:MYSQL_HOST = "127.0.0.1"
    $env:MYSQL_PORT = "$port"
    $env:MYSQL_DATABASE = $database
    $env:MYSQL_USER = $testUser
    $env:MYSQL_PASSWORD = $password
    $env:JWT_SECRET_KEY = New-StrongPassword
    $env:PLAN_PROVIDER = "mock"
    $env:PLACE_PROVIDER = "mock"
    $env:ROUTE_PROVIDER = "unavailable"

    Push-Location $backendRoot
    try {
        # Migration is deliberately after target verification and before tests.
        & $Python -B -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "Alembic migration failed." }

        $integrationOutput = & $Python -B -m pytest tests/integration/test_plan_regeneration_preview_mysql.py tests/integration/test_trip_travel_style_mysql.py -q -p no:cacheprovider --basetemp (Join-Path $instanceRoot "pytest-integration") -o log_cli=true -o log_cli_level=INFO 2>&1
        $integrationOutput | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -ne 0 -or ($integrationOutput -join "`n") -notmatch "\b18 passed\b") {
            throw "MySQL integration suite did not report 18 passed tests."
        }

        if ($RunRealExaonePreview) {
            # Read the local real-model configuration before pytest's isolation
            # fixture removes Settings environment variables.  Values remain in
            # process-only TASK75D variables and are never printed.
            $realConfig = & $Python -B -c "import json; from app.core.config import Settings; s=Settings(); print(json.dumps({'base_url': s.exaone_base_url, 'model': s.exaone_model}))"
            if ($LASTEXITCODE -ne 0) { throw "Unable to load local EXAONE configuration." }
            $realConfigObject = $realConfig | ConvertFrom-Json
            if (-not $realConfigObject.base_url -or -not $realConfigObject.model) { throw "Local EXAONE configuration is incomplete." }
            $env:TASK75D_EXAONE_BASE_URL = $realConfigObject.base_url
            $env:TASK75D_EXAONE_MODEL = $realConfigObject.model
            $env:PLAN_PROVIDER = "real"
            $env:RUN_REAL_EXAONE_PREVIEW = "1"
            $realOutput = & $Python -B -m pytest tests/integration/test_real_exaone_preview_opt_in.py -q -s -p no:cacheprovider --basetemp (Join-Path $instanceRoot "pytest-real-exaone") -o log_cli=true -o log_cli_level=INFO 2>&1
            $realOutput | ForEach-Object { Write-Host $_ }
            if ($LASTEXITCODE -ne 0 -or ($realOutput -join "`n") -notmatch "1 passed") {
                throw "Real EXAONE isolated HTTP preview test did not report 1 passed."
            }
        }

        if (-not $SkipUnit) {
            & $Python -B -m pytest tests/unit -q -p no:cacheprovider --basetemp (Join-Path $instanceRoot "pytest-unit")
            if ($LASTEXITCODE -ne 0) { throw "Backend unit suite failed." }
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
    Remove-Item Env:MYSQL_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:PLAN_REGENERATION_MYSQL_TEST_URL -ErrorAction SilentlyContinue
    Remove-Item Env:PLAN_REGENERATION_MYSQL_TEST_DATADIR -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_REAL_EXAONE_PREVIEW -ErrorAction SilentlyContinue
    Remove-Item Env:TASK75D_EXAONE_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:TASK75D_EXAONE_MODEL -ErrorAction SilentlyContinue
    # mysqld can detach from the Start-Process handle on Windows.  Its pid-file
    # is inside this invocation's UUID directory, so it is a safer ownership
    # proof than process name or port and cannot match a pre-existing instance.
    $ownedServerPid = $null
    if (Test-Path -LiteralPath $pidFile) {
        $pidText = (Get-Content -LiteralPath $pidFile -Raw).Trim()
        if ($pidText -match '^\d+$') { $ownedServerPid = [int]$pidText }
    }
    if ($null -ne $ownedServerPid) {
        $ownedProcess = Get-Process -Id $ownedServerPid -ErrorAction SilentlyContinue
        if ($null -ne $ownedProcess) {
            Stop-Process -Id $ownedServerPid -Force
            $ownedProcess.WaitForExit(15000) | Out-Null
        }
    }
    elseif ($null -ne $server) {
        $ownedProcess = Get-Process -Id $server.Id -ErrorAction SilentlyContinue
        if ($null -ne $ownedProcess) {
            Stop-Process -Id $server.Id -Force
            $ownedProcess.WaitForExit(15000) | Out-Null
        }
    }
    # Delete only the UUID directory created by this invocation, after the
    # owned server has stopped. This cannot target MySQL80's datadir.
    $resolvedRoot = [IO.Path]::GetFullPath($instanceRoot)
    $resolvedParent = [IO.Path]::GetFullPath((Join-Path $projectRoot ".task74c_mysql")).TrimEnd('\') + '\'
    if ($resolvedRoot.StartsWith($resolvedParent, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedRoot)) {
        Remove-Item -LiteralPath $resolvedRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
