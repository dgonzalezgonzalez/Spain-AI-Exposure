# Isolate the paper's pinned inference runtime from the interactive Ollama app.
$ErrorActionPreference = 'Stop'
$tevRoot = Split-Path -Parent $PSScriptRoot
$tevLogDir = Join-Path $tevRoot 'data\cache\tev_runtime'
New-Item -ItemType Directory -Force -Path $tevLogDir | Out-Null
$env:OLLAMA_HOST = '127.0.0.1:11435'
$env:OLLAMA_VULKAN = '1'
$env:OLLAMA_IGPU_ENABLE = '1'
$env:GGML_VK_VISIBLE_DEVICES = '0'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_CONTEXT_LENGTH = '32768'
$env:OLLAMA_FLASH_ATTENTION = '0'
$env:OLLAMA_KV_CACHE_TYPE = 'f16'
$env:OLLAMA_NO_CLOUD = '1'
$tevOllama = (Get-Command ollama.exe).Source
$tevProcess = Start-Process -FilePath $tevOllama -ArgumentList 'serve' -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $tevLogDir 'server.stdout.log') `
    -RedirectStandardError (Join-Path $tevLogDir 'server.stderr.log') -PassThru
$tevProcess.Id | Set-Content -LiteralPath (Join-Path $tevLogDir 'server.pid')
$tevProcess | Select-Object Id, ProcessName
