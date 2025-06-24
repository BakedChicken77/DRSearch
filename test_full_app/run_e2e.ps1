Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Get script directory and logs folder
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ScriptDir "logs"

if (-not (Test-Path $LogDir)) {
    New-Item -Path $LogDir -ItemType Directory | Out-Null
}

# Define log paths
$simOutLog   = Join-Path $LogDir 'simulator1.out.log'
$simErrLog   = Join-Path $LogDir 'simulator1.err.log'
$frontOutLog = Join-Path $LogDir 'frontend1.out.log'
$frontErrLog = Join-Path $LogDir 'frontend1.err.log'


$env:AUTH_ENABLED = "False"                                                                                                                            
$env:NEXT_PUBLIC_AUTH_ENABLED= "False"

try {
    # Start backend
    cd ..
    Push-Location drsearch_backend
    $simProc = Start-Process -FilePath "poetry" `
        -ArgumentList 'run', 'uvicorn', 'testing_full_app.simulator:app', '--port', '8011' `
        -RedirectStandardOutput $simOutLog `
        -RedirectStandardError  $simErrLog `
        -WindowStyle Hidden -PassThru
    Pop-Location

    # Start frontend
    Push-Location drsearch_frontend
    yarn install --silent
    $env:API_BASE_URL = 'http://localhost:8011'
    $frontProc = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "yarn dev --port 3000" `
        -RedirectStandardOutput $frontOutLog `
        -RedirectStandardError  $frontErrLog `
        -NoNewWindow -PassThru


    # Wait for servers to be ready
    for ($i = 1; $i -le 60; $i++) {
        try {
            Invoke-WebRequest -Uri 'http://localhost:8011/index-options' -UseBasicParsing -TimeoutSec 5 | Out-Null
            Invoke-WebRequest -Uri 'http://localhost:3000'            -UseBasicParsing -TimeoutSec 5 | Out-Null
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    # Run Playwright tests
    & yarn playwright install --with-deps
    & yarn playwright test testing_full_app/e2e.spec.ts
    $STATUS = $LASTEXITCODE
}
finally {
    # Always cleanup
    if ($frontProc) {
        Stop-Process -Id $frontProc.Id -Force -ErrorAction SilentlyContinue
    }
    if ($simProc) {
        Stop-Process -Id $simProc.Id -Force -ErrorAction SilentlyContinue
    }

    # Extra safety net: kill anything still bound to 3000/8011
    $ports = @(3000, 8011)
    foreach ($port in $ports) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen
        foreach ($conn in $conns) {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }

    Pop-Location  # just in case one was left open
    exit $STATUS
}
