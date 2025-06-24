$chatPayload = @'
{
  "input": {
    "question": "What does the XMIT_TRIG do?",
    "chat_history": [
      {"human": "Hi", "ai": "Hello!"},
      {"human": "Tell me about XYZ", "ai": "XYZ is a system..."}
    ],
    "index_name": "JACSKE_Program",
    "num_docs_retrieved": 3
  }
}
'@


$chatPayload = @'
{
  "input": {
    "question": "How do I fill out my timesheet?",
    "chat_history": [
      {"human": "Hi", "ai": "Hello!"}
    ],
    "index_name": "SEPS",
    "num_docs_retrieved": 1
  }
}
'@


$chatPayload = @'
{
  "input": {
    "question": "Where does the TX_TRIG signal get generated at, how odes it get created, where is it used, and what does it do?",
    "chat_history": [
      {"human": "Hi", "ai": "Hello!"}
    ],
    "index_name": "JACSKE_Program",
    "num_docs_retrieved": 1
  }
}
'@



$chatPayload = @'
{
  "input": {
    "question": "This is a test message",
    "chat_history": [
      {"human": "Hi", "ai": "Hello!"}
    ],
    "index_name": "TEST_INDEX",
    "num_docs_retrieved": 2
  }
}
'@




$tmpChat = "$env:TEMP\chat.json"
Set-Content -Path $tmpChat -Value $chatPayload -Encoding UTF8

$chatCmd = "curl -s -X POST http://localhost:8011/chat/stream_log -H `"Content-Type: application/json`" --data-binary @$tmpChat"
& cmd /c $chatCmd





$chatCmd = "curl -s http://localhost:8011/index-options"
& cmd /c $chatCmd
