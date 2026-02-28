# PAM Research Context — 已驗證發現彙整

## 資料庫 Quick Reference

| 表名 | 用途 | 關鍵欄位 |
|------|------|----------|
| congress_trades | 原始交易 | politician_name, ticker, transaction_type, amount_range, chamber, filing_date |
| alpha_signals | Alpha 信號 | direction, expected_alpha_5d/20d, confidence, signal_strength, sqs_score |
| enhanced_signals | PACS+VIX 增強 | pacs_score, confidence_v2, enhanced_strength, vix_zone |
| signal_quality_scores | SQS 評分 | sqs, grade, actionability, timeliness, conviction |
| convergence_signals | 收斂信號 | politician_count, score, direction |
| politician_rankings | 議員排名 | pis_total, rank, pis_activity/conviction/diversification/timing |
| fama_french_results | FF3 回測 | ff3_car_5d/20d/60d, mkt_car_5d/20d/60d, alpha_est |
| portfolio_positions | 投組持倉 | weight, conviction_score, expected_alpha |
| sector_rotation_signals | 板塊輪動 | sector, momentum_score, net_ratio, rotation_type |

## 已驗證研究 (RB-001 ~ RB-007)

### RB-001: Signal Quality + Alpha
- Buy: +0.77% CAR_5d (p<0.001), +0.79% CAR_20d (p=0.007)
- Sale: contrarian (stocks go UP after congress sells)
- $15K-$50K: strongest alpha bucket (+93% vs $1K-$15K)
- Filing lag <15d: +1.13% alpha

### RB-004: Optimal Trading Timing
- Buy-only: 20d alpha +1.10% (59.2% WR) vs Sale -3.21%
- Senate >> House: +1.39% 20d (69.2% WR) vs -1.27%
- VIX Goldilocks 14-16: +1.03% 20d, 63.2% WR
- VIX <14: -2.94% 20d (significant), VIX >16: -1.68% 5d (significant)

### RB-005: Politician Deep Dive
- Top 5: Richard Allen (83.3% WR), Gilbert Cisneros, John Boozman, David McCormick, Steve Cohen
- K-means: "Active Stock Traders" cluster best for copy-trading

### RB-006: Multi-Signal Fusion (PACS)
- PACS = 50% signal_strength + 25% filing_lag_inv + 15% options + 10% convergence
- Q1-Q4 spread: 6.5% alpha difference (Q4/Q1 = 3.04x)
- SQS conviction r=-0.51 (NEGATIVE predictor!)
- Options sentiment independent from congress signals (|r|<0.15)

### RB-007: Sector Rotation
- NET BUY: 66.7% hit rate, +2.51% 20d return
- NET SELL: 38.9% hit rate (unreliable)
- Energy paradox: congress massive sell but XLE +22%
- Follow buy-only, exclude energy, overweight XLI/XLB/XLV

### Sprint 02-28 Quant Validation
- Convergence premium: +36% EA20d
- $15K-$50K: +93% alpha vs $1K-$15K
- Filing lag <15d: 4.6x alpha vs >=15d
- SQS Timeliness bottleneck: avg 15.5/100
- FF3 20d/60d: 100% NULL (time constraint, not bug)
