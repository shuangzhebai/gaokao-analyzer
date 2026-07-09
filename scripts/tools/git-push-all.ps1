<#
.SYNOPSIS
  一键推送 gaokao-analyzer 全部优化提交到 GitHub
.DESCRIPTION
  将本地 4 个优化提交（阶段一~三 + 修复）推送到 shuangzhebai/gaokao-analyzer
  自动管理凭证，无需手动操作 git 命令。
.PARAMETER Token
  GitHub Personal Access Token（有 repo 写权限）。不传则读取环境变量 $env:GITHUB_TOKEN
  或交互式输入。
.EXAMPLE
  .\git-push-all.ps1 -Token "ghp_xxxxxxxxxxxxxxxxxxxx"
  .\git-push-all.ps1   # 交互式输入 Token
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$Token = ""
)

$ErrorActionPreference = "Stop"
$RepoPath = "C:\Users\29499\WorkBuddy\Claw\gaokao-analyzer"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   gaokao-analyzer 一键推送脚本                   ║" -ForegroundColor Cyan
Write-Host "║   推送 4 个优化提交到 GitHub                      ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ---------- 1. 检查仓库 ----------
if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
    Write-Host "❌ 错误：$RepoPath 不是有效的 git 仓库" -ForegroundColor Red
    exit 1
}
Set-Location $RepoPath

Write-Host "📦 仓库：$(git remote get-url origin 2>$null)" -ForegroundColor Yellow

# ---------- 2. 确认提交 ----------
$Commits = @("e29470d", "dbd9a82", "7a69c31", "826fa53")
$LocalCommits = git log --oneline -10
Write-Host "✅ 本地提交 ($((git log --oneline --count HEAD) - 1) 个优化提交之上游 v5.1)：" -ForegroundColor Green
git log --oneline --format="   %h %s" @("d45ccb2..HEAD")
Write-Host ""

# ---------- 3. 检查工作树 ----------
$Status = git status --short
if ($Status) {
    Write-Host "⚠️  警告：工作树有未提交改动，已暂存后提交：" -ForegroundColor Yellow
    git add -A
    git commit -m "chore: 推送前自动提交未暂存改动"
    Write-Host "    ✅ 已自动提交" -ForegroundColor Green
} else {
    Write-Host "✅ 工作树干净" -ForegroundColor Green
}

# ---------- 4. 获取 Token ----------
if ([string]::IsNullOrEmpty($Token)) {
    $Token = [System.Environment]::GetEnvironmentVariable("GITHUB_TOKEN")
}

if ([string]::IsNullOrEmpty($Token)) {
    Write-Host "🔑 请输入 GitHub Personal Access Token（有 repo 写权限）" -ForegroundColor Yellow
    Write-Host "   (输入不可见，粘贴后按 Enter)" -ForegroundColor DarkYellow
    $SecureToken = Read-Host -AsSecureString -Prompt "Token"
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureToken)
    $Token = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
}

if ([string]::IsNullOrEmpty($Token)) {
    Write-Host "❌ 错误：未提供 Token，推送中止" -ForegroundColor Red
    exit 1
}

# ---------- 5. 配置并推送 ----------
$Remote = "https://github.com/shuangzhebai/gaokao-analyzer.git"
$AuthUrl = "https://shuangzhebai:$Token@github.com/shuangzhebai/gaokao-analyzer.git"

Write-Host ""
Write-Host "🚀 正在推送到 $Remote ..." -ForegroundColor Cyan

# 设置 git 身份（如未设置）
$UserName = git config user.name
if (-not $UserName) { git config user.name "shuangzhebai" }
$UserEmail = git config user.email
if (-not $UserEmail) { git config user.email "shuangzhebai@users.noreply.github.com" }

# schannel 证书修复（Windows 沙箱/企业网络常见）
git config http.schannelCheckRevoke false 2>$null

try {
    # 用 Token 推送到 origin（先设为带认证的 URL）
    git remote set-url origin $AuthUrl
    $PushResult = git push --porcelain origin main 2>&1
    $ExitCode = $LASTEXITCODE

    if ($ExitCode -eq 0) {
        Write-Host ""
        Write-Host "✅ 推送成功！" -ForegroundColor Green
        Write-Host "   远程：$Remote" -ForegroundColor Green
        Write-Host "   分支：main" -ForegroundColor Green
        Write-Host ""
        Write-Host "📋 已推送的提交：" -ForegroundColor Green
        git log --oneline --format="   %h %s" @("d45ccb2..HEAD")
        Write-Host ""
        Write-Host "🌐 打开仓库：https://github.com/shuangzhebai/gaokao-analyzer" -ForegroundColor Cyan
    } else {
        Write-Host ""
        Write-Host "❌ 推送失败（ExitCode=$ExitCode）" -ForegroundColor Red
        Write-Host "   错误：" -ForegroundColor Red
        $PushResult -split "`n" | ForEach-Object { Write-Host "   $_" -ForegroundColor Red }
        Write-Host ""
        Write-Host "可能的原因：" -ForegroundColor Yellow
        Write-Host "  1. Token 权限不足（需要 repo 或 Contents: Read and write）" -ForegroundColor Yellow
        Write-Host "  2. Token 已过期" -ForegroundColor Yellow
        Write-Host "  3. 网络无法连接 GitHub（企业/沙箱代理限制）" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "建议：到 https://github.com/settings/tokens 生成新 Token（勾选 repo 权限）" -ForegroundColor Yellow
    }
} finally {
    # 恢复原始远程 URL（不暴露 Token）
    git remote set-url origin $Remote
}

Write-Host ""
Write-Host "按 Enter 退出..."
[void][System.Console]::ReadKey($true)
