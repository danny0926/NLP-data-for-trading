# ============================================================
# Political Alpha Monitor — Windows Task Scheduler 設定腳本
# 用法 (以系統管理員身份執行):
#   powershell -ExecutionPolicy Bypass -File setup_scheduler.ps1
#
# 建立的排程工作:
#   1. PoliticalAlphaMonitor-Daily   — 每天 06:00 (台灣時間) 完整流程
#   2. PoliticalAlphaMonitor-Weekly  — 每週日 05:00 擴大回溯 (--days 14)
# ============================================================

$ErrorActionPreference = "Stop"

# ── 專案路徑 ──
$ProjectDir = "D:\VScode_project\NLP data for trading"
$PythonExe = "$ProjectDir\venv\Scripts\python.exe"
$DailyScript = "$ProjectDir\run_daily.py"

# 驗證路徑
if (-not (Test-Path $DailyScript)) {
    Write-Error "找不到 $DailyScript，請確認專案路徑正確。"
    exit 1
}

# 嘗試找到 Python 執行檔
if (-not (Test-Path $PythonExe)) {
    # 嘗試 .venv
    $PythonExe = "$ProjectDir\.venv\Scripts\python.exe"
    if (-not (Test-Path $PythonExe)) {
        # 使用系統 Python
        $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
        if (-not $PythonExe) {
            Write-Error "找不到 Python 執行檔。請安裝 Python 或建立 venv。"
            exit 1
        }
    }
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Political Alpha Monitor — 排程設定" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  專案目錄: $ProjectDir"
Write-Host "  Python:    $PythonExe"
Write-Host ""

# ── 1. 每日排程 (06:00 台灣時間) ──

$TaskName = "PoliticalAlphaMonitor-Daily"
Write-Host "[1/2] 設定每日排程: $TaskName" -ForegroundColor Yellow

# 移除舊的同名排程（如果存在）
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "  移除舊排程..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$DailyAction = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$DailyScript`" --days 3" `
    -WorkingDirectory $ProjectDir

$DailyTrigger = New-ScheduledTaskTrigger `
    -Daily `
    -At "06:00"

$DailySettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$DailyPrincipal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $DailyAction `
    -Trigger $DailyTrigger `
    -Settings $DailySettings `
    -Principal $DailyPrincipal `
    -Description "Political Alpha Monitor — 每日自動執行 ETL + AI Discovery + Analysis + Dashboard"

Write-Host "  [OK] 每日排程已建立: 每天 06:00" -ForegroundColor Green

# ── 2. 每週排程 (週日 05:00，擴大回溯) ──

$WeeklyTaskName = "PoliticalAlphaMonitor-Weekly"
Write-Host ""
Write-Host "[2/2] 設定每週排程: $WeeklyTaskName" -ForegroundColor Yellow

$existingWeekly = Get-ScheduledTask -TaskName $WeeklyTaskName -ErrorAction SilentlyContinue
if ($existingWeekly) {
    Write-Host "  移除舊排程..."
    Unregister-ScheduledTask -TaskName $WeeklyTaskName -Confirm:$false
}

$WeeklyAction = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$DailyScript`" --days 14" `
    -WorkingDirectory $ProjectDir

$WeeklyTrigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Sunday `
    -At "05:00"

Register-ScheduledTask `
    -TaskName $WeeklyTaskName `
    -Action $WeeklyAction `
    -Trigger $WeeklyTrigger `
    -Settings $DailySettings `
    -Principal $DailyPrincipal `
    -Description "Political Alpha Monitor — 每週日擴大回溯 14 天"

Write-Host "  [OK] 每週排程已建立: 每週日 05:00" -ForegroundColor Green

# ── 驗證 ──
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  排程設定完成！" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  已建立的排程工作:" -ForegroundColor White
Get-ScheduledTask -TaskName "PoliticalAlphaMonitor-*" | Format-Table TaskName, State, @{
    Label = "NextRunTime"
    Expression = { (Get-ScheduledTaskInfo -TaskName $_.TaskName).NextRunTime }
}

Write-Host "  手動執行測試:" -ForegroundColor White
Write-Host "    Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "  移除排程:" -ForegroundColor White
Write-Host "    Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
Write-Host "    Unregister-ScheduledTask -TaskName '$WeeklyTaskName' -Confirm:`$false"
Write-Host ""
