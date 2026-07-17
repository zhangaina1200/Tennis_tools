param([string]$Message = "")

$repoPath = "E:\Tennis_tools"
Set-Location $repoPath

# 1. Status
Write-Host "=== Git Status ===" -ForegroundColor Cyan
$status = git status --short 2>$null
if (-not $status) {
    Write-Host "No changes. Nothing to push." -ForegroundColor Green
    exit 0
}
Write-Host $status -ForegroundColor White

# 2. Commit message
if (-not $Message) {
    $changed = @()
    $status -split "`n" | ForEach-Object {
        if ($_ -match "^[MAD]\s+(.+)$") { $changed += $matches[1] }
    }
    if ($changed.Count -gt 0) {
        $files = ($changed -join ", ")
        if ($files.Length -gt 60) { $files = $files.Substring(0, 57) + "..." }
        $Message = "chore: update $files"
    } else {
        $Message = "chore: auto-commit"
    }
}

# 3. Stale lock
if (Test-Path "$repoPath\.git\index.lock") {
    Remove-Item "$repoPath\.git\index.lock" -Force -ErrorAction SilentlyContinue
}

# 4. Stage
Write-Host "`n=== Staging ===" -ForegroundColor Cyan
git add index.html .gitignore git-push.ps1 2>$null
Write-Host "Staged: index.html, .gitignore, git-push.ps1"

# 5. Commit
Write-Host "`n=== Committing ===" -ForegroundColor Cyan
git commit -m $Message 2>$null

# 6. Push (check network first)
Write-Host "`n=== Pushing ===" -ForegroundColor Cyan
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $ar = $tcp.BeginConnect("github.com", 443, $null, $null)
    $ar.AsyncWaitHandle.WaitOne(3000) | Out-Null
    if ($tcp.Connected) {
        $tcp.EndConnect($ar) | Out-Null
        $tcp.Close()
        git push origin master 2>$null
        Write-Host "OK - pushed!" -ForegroundColor Green
    } else {
        $tcp.Close()
        Write-Host "Network blocked. Run: git push origin master" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Network blocked. Run: git push origin master" -ForegroundColor Yellow
}
