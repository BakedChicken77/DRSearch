# Stop on any unhandled error
$ErrorActionPreference = 'Stop'

# ------------- Retry parameters -------------
$RETRY_INTERVAL = 5    # seconds between attempts
$RETRY_TIMEOUT  = 300  # total seconds before giving up
# -------------------------------------------

# ------------- Path resolution -------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir   = Split-Path -Parent $ScriptDir
# -------------------------------------------

# ------------- Environment vars ------------
$env:LLM_SERVICE     = 'fake'
$env:VECTOR_BACKEND  = 'pgvector'
# if (-not $env:PGVECTOR_URL) {
#     $env:PGVECTOR_URL = 'postgresql://username:password@localhost:5432/pgvector_db'
# }
$env:AUTH_ENABLED    = 'False'
$env:RAG_ON          = 'True'
$env:LOG_OUTPUT_MODE = 'local'
# -------------------------------------------

# Change to repository root
Set-Location $RootDir

# ------------- Launch server ---------------
$serverProcess = Start-Process -FilePath 'poetry' `
    -ArgumentList 'run','uvicorn','app:app','--host','0.0.0.0','--port','8011' `
    -NoNewWindow -PassThru
$serverPid = $serverProcess.Id
Start-Sleep -Seconds 5
# -------------------------------------------

# ------------- Retry helper ----------------
function Check {
    param(
        [Parameter(Mandatory)][string] $CommandLine
    )

    $elapsed = 0
    while ($elapsed -le $RETRY_TIMEOUT) {
        & cmd /c $CommandLine
        $exit = $LASTEXITCODE

        if ($exit -eq 0) { return }
        elseif ($exit -eq 7) {
            Write-Host "Connection failed (exit $exit). Retrying in $RETRY_INTERVAL s ... (elapsed $elapsed/$RETRY_TIMEOUT)"
        }
        elseif ($exit -eq 22) {
            Write-Error "Command returned HTTP error (exit $exit). Not retrying: $CommandLine"
            break
        } else {
            Write-Host "Command failed (exit $exit). Retrying in $RETRY_INTERVAL s ... (elapsed $elapsed/$RETRY_TIMEOUT)"
        }

        Start-Sleep -Seconds $RETRY_INTERVAL
        $elapsed += $RETRY_INTERVAL
    }

    Write-Error "Command failed after $RETRY_TIMEOUT seconds: $CommandLine"
    Stop-Process -Id $serverPid -ErrorAction SilentlyContinue
    Wait-Process -Id $serverPid -ErrorAction SilentlyContinue
    exit 1
}
# -------------------------------------------

# ------------- Endpoint checks -------------

# 1) GET /index-options
Check "curl -s http://localhost:8011/index-options"

# 2) POST /feedback
$feedbackPayload = @'
{
  "run_id": "11111111-1111-1111-1111-111111111111",
  "key": "user_score",
  "score": 1,
  "feedback_id": "22222222-2222-2222-2222-222222222222",
  "comment": "Helpful response.",
  "conversation": [
    {"human": "What’s the part number?", "ai": "It's ABC123."},
    {"human": "Thanks", "ai": "You're welcome!"}
  ],
  "documents": ["doc1", "doc2"]
}
'@
$tmpFeedback = "$env:TEMP\feedback.json"
Set-Content -Path $tmpFeedback -Value $feedbackPayload -Encoding UTF8

$feedbackCmd = "curl -s -X POST http://localhost:8011/feedback -H `"Content-Type: application/json`" --data-binary @$tmpFeedback"
Check $feedbackCmd

# 3) POST /chat/stream_log
$chatPayload = @'
{
  "input": {
    "question": "What is the BOM for unit XYZ?",
    "chat_history": [
      {"human": "Hi", "ai": "Hello!"},
      {"human": "Tell me about XYZ", "ai": "XYZ is a system..."}
    ],
    "index_name": "test_docs",
    "num_docs_retrieved": 3
  }
}
'@
$tmpChat = "$env:TEMP\chat.json"
Set-Content -Path $tmpChat -Value $chatPayload -Encoding UTF8

$chatCmd = "curl -s -X POST http://localhost:8011/chat/stream_log -H `"Content-Type: application/json`" --data-binary @$tmpChat"
Check $chatCmd
# -------------------------------------------

# ------------- Clean shutdown --------------
Stop-Process -Id $serverPid -ErrorAction SilentlyContinue
Wait-Process  -Id $serverPid -ErrorAction SilentlyContinue

if (Test-Path $tmpFeedback) { Remove-Item -LiteralPath $tmpFeedback -Force }
if (Test-Path $tmpChat)     { Remove-Item -LiteralPath $tmpChat -Force }

# -------------------------------------------
