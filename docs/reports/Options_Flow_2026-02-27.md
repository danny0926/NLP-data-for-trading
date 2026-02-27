# Options Flow Analysis Report
**Generated**: 2026-02-27 21:46:03
**Tickers Analyzed**: 17

## Methodology

針對 alpha 訊號前 20 檔標的，分析最近到期日的選擇權活動：

1. **Put/Call Ratio**: 成交量加權。< 0.7 偏多，> 1.3 偏空
2. **異常成交量**: volume > 2x open interest 的合約
3. **IV Skew**: Call IV vs Put IV 差異
4. **國會交易交叉比對**:
   - Congress BUY + 高 call 量 = BULLISH_CONFIRMATION
   - Congress BUY + 高 put 量 = HEDGING_WARNING
   - Congress SELL + 高 put 量 = BEARISH_CONFIRMATION
   - Congress SELL + 高 call 量 = CONTRARIAN_WARNING

## Summary

| 指標 | 數值 |
|------|------|
| BULLISH_CONFIRMATION | 8 |
| BEARISH_CONFIRMATION | 1 |
| HEDGING_WARNING | 5 |
| CONTRARIAN_WARNING | 1 |
| NEUTRAL | 2 |
| 平均情緒分數 | -0.015 |
| 平均 Put/Call Ratio | 1.119 |
| 異常成交量合約總數 | 65 |

## Detailed Analysis

| # | Ticker | P/C Ratio | Sentiment | Signal Type | Call Vol | Put Vol | Unusual | Call IV | Put IV | Congress Dir | Alpha Str |
|---|--------|-----------|-----------|-------------|---------|---------|---------|---------|--------|-------------|-----------|
| 1 | **TDG** | 0.07 | +1.000 | BULLISH_CONFIRMATION | 705 | 48 | 1 | 5.78% | 3.95% | Buy | 0.606 |
| 2 | **SPGI** | 3.86 | -0.900 | HEDGING_WARNING | 154 | 595 | 2 | 20.06% | 25.26% | Buy | 0.690 |
| 3 | **DIS** | 0.28 | +0.833 | BULLISH_CONFIRMATION | 6,530 | 1,845 | 3 | 25.21% | 19.22% | Buy | 0.682 |
| 4 | **VRT** | 2.59 | -0.817 | HEDGING_WARNING | 4,472 | 11,570 | 12 | 10.11% | 30.97% | Buy | 0.606 |
| 5 | **NFLX** | 0.39 | +0.714 | BULLISH_CONFIRMATION | 241,312 | 95,304 | 7 | 24.94% | 20.28% | Buy | 0.682 |
| 6 | **ETN** | 1.55 | -0.650 | HEDGING_WARNING | 226 | 350 | 0 | 11.55% | 20.28% | Buy | 1.198 |
| 7 | **PWR** | 2.13 | -0.650 | HEDGING_WARNING | 310 | 661 | 2 | 1.67% | 97.22% | Buy | 0.665 |
| 8 | **WPM** | 0.33 | +0.500 | BULLISH_CONFIRMATION | 893 | 292 | 5 | 6.25% | 69.43% | Buy | 0.999 |
| 9 | **GS** | 1.44 | -0.500 | BEARISH_CONFIRMATION | 4,459 | 6,431 | 2 | 15.99% | 25.02% | Sale | 0.639 |
| 10 | **CSGP** | 1.48 | -0.500 | HEDGING_WARNING | 989 | 1,466 | 4 | 68.46% | 2.68% | Buy | 0.630 |
| 11 | **FNV** | 0.61 | +0.350 | BULLISH_CONFIRMATION | 83 | 51 | 0 | 4.77% | 18.52% | Buy | 0.999 |
| 12 | **ISRG** | 0.23 | +0.350 | BULLISH_CONFIRMATION | 995 | 224 | 2 | 25.77% | 43.43% | Buy | 0.630 |
| 13 | **SAN** | 0.64 | +0.350 | BULLISH_CONFIRMATION | 482 | 308 | 0 | 2.34% | 74.22% | Buy | 0.606 |
| 14 | **TSM** | 1.22 | -0.332 | NEUTRAL | 40,721 | 49,703 | 8 | 16.51% | 34.71% | Buy | 0.606 |
| 15 | **WDAY** | 1.20 | -0.226 | NEUTRAL | 4,999 | 6,019 | 8 | 75.32% | 22.19% | Buy | 0.630 |
| 16 | **AAPL** | 0.68 | +0.225 | BULLISH_CONFIRMATION | 208,884 | 141,903 | 8 | 18.03% | 29.37% | Buy | 0.925 |
| 17 | **STT** | 0.31 | -0.000 | CONTRARIAN_WARNING | 252 | 77 | 1 | 12.58% | 66.69% | Sale | 0.914 |

## Unusual Activity Highlights

### TDG (BULLISH_CONFIRMATION)

**異常 Call 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 1490.0 | 3 | 1 | 3.0x | 12.50% |

### SPGI (HEDGING_WARNING)

**異常 Put 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 470.0 | 5 | 2 | 2.5x | 0.00% |
| 540.0 | 7 | 1 | 7.0x | 0.00% |

### DIS (BULLISH_CONFIRMATION)

**異常 Call 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 92.0 | 8 | 3 | 2.7x | 0.00% |
| 126.0 | 3 | 1 | 3.0x | 50.00% |

**異常 Put 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 110.0 | 45 | 2 | 22.5x | 0.00% |

### VRT (HEDGING_WARNING)

**異常 Call 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 100.0 | 8 | 2 | 4.0x | 0.00% |
| 182.5 | 200 | 19 | 10.5x | 0.00% |

**異常 Put 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 282.5 | 439 | 1 | 439.0x | 0.00% |
| 285.0 | 270 | 6 | 45.0x | 0.00% |
| 287.5 | 689 | 9 | 76.6x | 0.00% |
| 290.0 | 310 | 42 | 7.4x | 0.00% |
| 292.5 | 491 | 49 | 10.0x | 0.00% |

### NFLX (BULLISH_CONFIRMATION)

**異常 Call 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 85.0 | 80,339 | 17,079 | 4.7x | 3.13% |
| 86.0 | 28,302 | 14,133 | 2.0x | 6.25% |
| 145.0 | 28 | 2 | 14.0x | 50.00% |

**異常 Put 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 84.0 | 21,015 | 10,009 | 2.1x | 3.13% |
| 85.0 | 6,345 | 2,187 | 2.9x | 0.00% |
| 95.0 | 44 | 5 | 8.8x | 0.00% |
| 98.0 | 2,002 | 225 | 8.9x | 0.00% |

### PWR (HEDGING_WARNING)

**異常 Call 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 240.0 | 55 | 10 | 5.5x | 0.00% |

**異常 Put 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 240.0 | 22 | 8 | 2.8x | 50.00% |

### WPM (BULLISH_CONFIRMATION)

**異常 Call 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 95.0 | 10 | 3 | 3.3x | 0.00% |
| 121.0 | 56 | 10 | 5.6x | 0.00% |
| 134.0 | 131 | 41 | 3.2x | 0.00% |
| 139.0 | 72 | 25 | 2.9x | 0.00% |

**異常 Put 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 116.0 | 5 | 2 | 2.5x | 50.00% |

### GS (BEARISH_CONFIRMATION)

**異常 Call 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 470.0 | 3 | 1 | 3.0x | 0.00% |
| 490.0 | 6 | 2 | 3.0x | 0.00% |

### CSGP (HEDGING_WARNING)

**異常 Put 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 65.0 | 890 | 63 | 14.1x | 0.00% |
| 70.0 | 130 | 32 | 4.1x | 0.00% |
| 75.0 | 38 | 2 | 19.0x | 0.00% |
| 80.0 | 120 | 19 | 6.3x | 0.00% |

### ISRG (BULLISH_CONFIRMATION)

**異常 Call 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 545.0 | 25 | 5 | 5.0x | 25.00% |

**異常 Put 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 530.0 | 5 | 1 | 5.0x | 0.00% |

### TSM (NEUTRAL)

**異常 Call 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 180.0 | 4 | 1 | 4.0x | 0.00% |
| 210.0 | 12 | 4 | 3.0x | 0.00% |
| 215.0 | 12 | 4 | 3.0x | 0.00% |
| 235.0 | 4 | 1 | 4.0x | 0.00% |
| 312.5 | 3 | 1 | 3.0x | 0.00% |

**異常 Put 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 360.0 | 19,772 | 7,587 | 2.6x | 25.00% |
| 377.5 | 1,258 | 598 | 2.1x | 0.00% |

### WDAY (NEUTRAL)

**異常 Call 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 139.0 | 256 | 101 | 2.5x | 0.00% |

**異常 Put 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 138.0 | 523 | 210 | 2.5x | 3.13% |
| 141.0 | 85 | 37 | 2.3x | 0.00% |
| 170.0 | 20 | 3 | 6.7x | 0.00% |
| 175.0 | 6 | 1 | 6.0x | 0.00% |
| 180.0 | 6 | 1 | 6.0x | 0.00% |

### AAPL (BULLISH_CONFIRMATION)

**異常 Call 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 272.5 | 26,021 | 6,397 | 4.1x | 0.00% |
| 277.5 | 38,685 | 12,934 | 3.0x | 6.25% |

**異常 Put 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 267.5 | 24,269 | 7,252 | 3.4x | 12.50% |
| 270.0 | 30,498 | 7,396 | 4.1x | 6.25% |
| 272.5 | 26,842 | 5,250 | 5.1x | 0.78% |
| 275.0 | 12,414 | 3,467 | 3.6x | 0.00% |
| 280.0 | 1,655 | 108 | 15.3x | 0.00% |

### STT (CONTRARIAN_WARNING)

**異常 Put 合約:**

| Strike | Volume | OI | Vol/OI | IV |
|--------|--------|----|--------|------|
| 55.0 | 5 | 2 | 2.5x | 191.60% |

## Disclaimer

選擇權資料來自 yfinance，可能存在延遲。本報告僅供研究參考，不構成投資建議。異常活動不一定代表方向性押注，可能為避險或套利操作。

---
*Generated by Political Alpha Monitor — Options Flow Analyzer v1.0 — 2026-02-27 21:46*
