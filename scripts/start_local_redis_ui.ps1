$ErrorActionPreference = 'Stop'

$redisDir = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\taizod1024.redis-windows-fork_Microsoft.Winget.Source_8wekyb3d8bbwe\Redis-8.8.0-Windows-x64-msys2'
$redisServer = Join-Path $redisDir 'redis-server.exe'

if (-not (Test-Path $redisServer)) {
    throw "redis-server.exe not found at $redisServer"
}

$redisPort = 6379
$redisDb = 1
$uiPort = 8081

$redisListening = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $redisPort -State Listen -ErrorAction SilentlyContinue
if (-not $redisListening) {
    Start-Process -FilePath $redisServer `
        -ArgumentList "--bind 127.0.0.1 --port $redisPort --save `"`" --appendonly no" `
        -WorkingDirectory $redisDir `
        -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

$uiListening = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $uiPort -State Listen -ErrorAction SilentlyContinue
if (-not $uiListening) {
    $redisCommander = Join-Path $env:APPDATA 'npm\redis-commander.cmd'
    if (-not (Test-Path $redisCommander)) {
        throw "redis-commander.cmd not found. Run: npm install -g redis-commander"
    }
    Start-Process -FilePath $redisCommander `
        -ArgumentList "--redis-host 127.0.0.1 --redis-port $redisPort --redis-db $redisDb --port $uiPort --address 127.0.0.1" `
        -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

Start-Process "http://127.0.0.1:$uiPort"
Write-Host "Redis is available at redis://127.0.0.1:$redisPort/$redisDb"
Write-Host "Redis Commander is available at http://127.0.0.1:$uiPort"
