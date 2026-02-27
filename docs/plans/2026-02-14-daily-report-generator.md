# Daily Report Generator — 設計文件

## Understanding

- **Building**: 每日國會交易報告生成器（含異常警報）
- **Because**: 將 congress_trades 結構化資料轉為可讀分析報告
- **For**: 人類使用者閱讀（終端輸出 / Markdown 檔案）
- **Constraints**: 透過 Gemini CLI 單次對話生成完整報告
- **Non-goals**: 不做自動下單、即時推送、股價回測

## 架構 — 方案 A

```
congress_trades (SQLite)
        │
        ▼
generate_report.py           ← 查詢 DB + 統計摘要 + 組裝 prompt
        │
        │  subprocess / stdin pipe
        ▼
gemini CLI (單次對話)         ← 接收結構化資料 + prompt → 輸出完整報告
        │
        ▼
reports/YYYY-MM-DD-daily.md  ← Markdown 報告檔
```

分工：
- Python（確定性）: DB 查詢、統計計算、prompt 組裝
- Gemini CLI（創造性）: 完整報告生成（摘要 + 分析 + 異常 + 趨勢）

## Prompt 結構

```
[系統指令] 你是國會交易分析師...
[原始資料] 表格格式的交易紀錄
[統計摘要] Python 預先計算的數字
[輸出要求] 繁體中文 Markdown，含：今日概覽、重要交易、異常警報、趨勢觀察
```

## CLI 介面

```bash
python generate_report.py                    # 今天
python generate_report.py --date 2026-02-13  # 指定日期
python generate_report.py --days 7           # 過去 N 天總結
```

## 輸出

- 路徑: `reports/YYYY-MM-DD-daily.md`
- 格式: Markdown（繁體中文）
- 同時輸出到終端

## Decision Log

| 決策 | 替代方案 | 理由 |
|------|---------|------|
| 方案 A（全部交 Gemini） | 方案 B（混合式） | 簡單架構 |
| Gemini CLI 單次對話 | SDK 多次 API | 使用者需求 |
| Daily + Anomaly 合併 | 分開模組 | 一次呼叫完成 |
| Markdown 輸出 | HTML/PDF | 簡單、git-friendly |

## 報告內容段落

1. 今日概覽（數字摘要）
2. 重要交易列表（附簡短分析）
3. 異常警報（大額、密集、多人同向等）
4. 趨勢觀察

## Next Steps

- [ ] 實作 generate_report.py
- [ ] 驗證 Gemini CLI 呼叫
- [ ] 整合到 run_etl_wsl.sh
