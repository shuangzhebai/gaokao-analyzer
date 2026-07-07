# gaokao-analyzer GitHub one-click push script (PowerShell)
# Usage: right-click -> "Run with PowerShell" or run in PowerShell

$repo = "C:\Users\29499\WorkBuddy\Claw\gaokao-analyzer"
$remote = "https://github.com/shuangzhebai/gaokao-analyzer.git"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "    gaokao-analyzer GitHub Push Helper" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Open https://github.com/settings/tokens"
Write-Host "2. Generate a classic token with 'repo' scope"
Write-Host "3. Paste it below (input will be hidden)"
Write-Host ""

$token = Read-Host -AsSecureString "GitHub Token"
if ($token.Length -eq 0) {
    Write-Host "Token is empty. Exiting." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($token)
$tokenPlain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)

Set-Location $repo

Write-Host ""
Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
$env:GIT_SSL_NO_VERIFY = "true"
$pushUrl = "https://shuangzhebai:$tokenPlain@github.com/shuangzhebai/gaokao-analyzer.git"

try {
    $result = git -c http.sslVerify=false -c http.schannelCheckRevoke=false push --force $pushUrl main 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host ""
        Write-Host "SUCCESS" -ForegroundColor Green
        Write-Host $remote -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "FAILED. Error code: $exitCode" -ForegroundColor Red
        Write-Host $result -ForegroundColor Red
        Write-Host "Make sure your token has 'repo' permission." -ForegroundColor Red
    }
} finally {
    $tokenPlain = $null
    $env:GIT_SSL_NO_VERIFY = $null
}

Read-Host "Press Enter to exit"
