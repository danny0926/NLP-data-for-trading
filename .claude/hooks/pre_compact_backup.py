#!/usr/bin/env python3
"""PreCompact Hook — Context 壓縮前自動備份 supervisor 狀態。

Claude Code 在自動壓縮 context 前會觸發此 hook。
如果偵測到 /supervise 正在運行（supervisor_state.json 存在且 status=RUNNING），
自動將當前進度寫入 handoff 文件，確保下一個 context window 能接力。

同時備份 transcript 到 logs/context_backups/ 供事後審計。
"""

import json
import os
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path

# 專案根目錄（相對於 .claude/hooks/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
BACKUP_DIR = LOGS_DIR / "context_backups"
STATE_FILE = LOGS_DIR / "supervisor_state.json"
HANDOFF_FILE = LOGS_DIR / "supervisor_handoff.json"


def read_stdin_input():
    """讀取 Claude Code 傳入的 hook input JSON。"""
    try:
        raw = sys.stdin.read()
        if raw.strip():
            return json.loads(raw)
    except (json.JSONDecodeError, EOFError):
        pass
    return {}


def backup_transcript(hook_input: dict):
    """備份 transcript 到 logs/context_backups/。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    transcript_path = hook_input.get("transcript_path")
    if transcript_path and os.path.exists(transcript_path):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest = BACKUP_DIR / f"transcript_{ts}.jsonl"
        shutil.copy2(transcript_path, dest)
        print(f"[PreCompact] Transcript backed up to {dest}")

        # 只保留最近 10 個備份
        backups = sorted(BACKUP_DIR.glob("transcript_*.jsonl"), reverse=True)
        for old in backups[10:]:
            old.unlink()
            print(f"[PreCompact] Removed old backup: {old.name}")
    else:
        # 沒有 transcript_path，記錄時間戳
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        marker = BACKUP_DIR / f"compaction_marker_{ts}.txt"
        marker.write_text(
            f"Context compaction at {ts} UTC\n"
            f"Trigger: {hook_input.get('trigger', 'unknown')}\n"
        )
        print(f"[PreCompact] Compaction marker saved: {marker}")


def update_supervisor_handoff(hook_input: dict):
    """如果 supervisor 正在運行，自動寫 handoff。"""
    if not STATE_FILE.exists():
        print("[PreCompact] No supervisor_state.json — not in /supervise mode")
        return

    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[PreCompact] Failed to read supervisor_state.json: {e}")
        return

    if state.get("status") != "RUNNING":
        print(f"[PreCompact] Supervisor status is '{state.get('status')}', skipping handoff")
        return

    # 構建 handoff
    now_utc = datetime.now(timezone.utc).isoformat()
    context_window = state.get("context_window", 1)

    handoff = {
        "schema_version": "2.0",
        "written_at_utc": now_utc,
        "written_by": "PreCompact hook (automatic)",
        "deadline_utc": state.get("deadline_utc", ""),
        "context_window_number": context_window,
        "cumulative_commits": state.get("commits", []),
        "tasks_completed": state.get("tasks_completed", []),
        "tasks_remaining": state.get("tasks_remaining", []),
        "active_research": state.get("active_research", ""),
        "key_findings": state.get("key_findings", []),
        "agent_team_config": state.get("agent_team_config", {}),
        "resume_instructions": (
            f"This is an automatic handoff from PreCompact hook. "
            f"Context window #{context_window} was compacted. "
            f"Resume from where the previous context left off. "
            f"Check supervisor_state.json for the latest state."
        ),
    }

    HANDOFF_FILE.write_text(
        json.dumps(handoff, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 更新 state 的 context_window 計數
    state["context_window"] = context_window + 1
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[PreCompact] Supervisor handoff written: {HANDOFF_FILE}")
    print(f"[PreCompact] Context window incremented to #{context_window + 1}")
    print(f"[PreCompact] Deadline: {state.get('deadline_utc', 'N/A')}")


def main():
    hook_input = read_stdin_input()
    trigger = hook_input.get("trigger", "unknown")
    print(f"[PreCompact] Triggered ({trigger}) at {datetime.now(timezone.utc).isoformat()}")

    backup_transcript(hook_input)
    update_supervisor_handoff(hook_input)

    print("[PreCompact] Done")


if __name__ == "__main__":
    main()
