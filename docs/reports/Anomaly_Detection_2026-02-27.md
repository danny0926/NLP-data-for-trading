# 國會交易異常偵測報告

**偵測日期**: 2026-02-27
**資料來源**: congress_trades (SQLite)
**偵測筆數**: 168

---

## 摘要統計

### 嚴重度分布
| 嚴重度 | 數量 |
|--------|------|
| CRITICAL | 6 |
| HIGH | 158 |
| MEDIUM | 4 |
| LOW | 0 |

### 異常類型分布
| 類型 | 說明 | 數量 |
|------|------|------|
| VOLUME | 交易頻率異常 | 0 |
| TIMING | 申報延遲異常 | 149 |
| CLUSTER | 多議員同標的集中交易 | 1 |
| SIZE | 交易金額偏離慣常範圍 | 14 |
| REVERSAL | 短期買後賣 | 4 |

---

## 議員複合異常分數排名

| 排名 | 議員 | 複合分數 | 風險等級 |
|------|------|----------|----------|
| 1 | Gilbert Cisneros | 38.50 | CRITICAL |
| 2 | Sheri Biggs | 36.90 | CRITICAL |
| 3 | Steve Cohen | 32.57 | CRITICAL |
| 4 | Donald Sternoff Jr. Beyer | 24.78 | CRITICAL |
| 5 | Richard W. Allen | 14.82 | HIGH |
| 6 | April McClain Delaney | 9.24 | MEDIUM |
| 7 | Suzan K. DelBene | 7.44 | MEDIUM |
| 8 | David H McCormick | 7.31 | MEDIUM |
| 9 | Michael A. Jr. Collins | 6.36 | MEDIUM |
| 10 | Richard Blumenthal | 6.06 | MEDIUM |

---

## 重大異常詳情（CRITICAL + HIGH）

### 1. [CRITICAL] SIZE — Gilbert Cisneros
- **標的**: N/A
- **分數**: 10.0/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 Los Angeles, CA Dept. Wtr. & Pwr. Wtrwks. Rev. Bonds 金額 $250,001 - $500,000（估值 $375,000），遠高於個人平均 $20,544，z-score=6.24

### 2. [CRITICAL] SIZE — Gilbert Cisneros
- **標的**: N/A
- **分數**: 10.0/10
- **日期**: 2025-12-30
- **描述**: Gilbert Cisneros 交易 Wisconsin State Health & Educational Facilities Authority Rev. Bonds 金額 $250,001 - $500,000（估值 $375,000），遠高於個人平均 $20,544，z-score=6.24

### 3. [CRITICAL] SIZE — Gilbert Cisneros
- **標的**: N/A
- **分數**: 10.0/10
- **日期**: 2026-01-23
- **描述**: Gilbert Cisneros 交易 Southeast Energy Authority Cooperative District, Alabama Bonds 金額 $250,001 - $500,000（估值 $375,000），遠高於個人平均 $20,544，z-score=6.24

### 4. [CRITICAL] SIZE — Gilbert Cisneros
- **標的**: N/A
- **分數**: 10.0/10
- **日期**: 2026-01-27
- **描述**: Gilbert Cisneros 交易 California Community Choice Financing Authority Rev Bonds 金額 $250,001 - $500,000（估值 $375,000），遠高於個人平均 $20,544，z-score=6.24

### 5. [CRITICAL] SIZE — Gilbert Cisneros
- **標的**: N/A
- **分數**: 10.0/10
- **日期**: 2026-01-30
- **描述**: Gilbert Cisneros 交易 California Community Choice Financing Authority Rev Bonds 金額 $250,001 - $500,000（估值 $375,000），遠高於個人平均 $20,544，z-score=6.24

### 6. [CRITICAL] SIZE — Gilbert Cisneros
- **標的**: N/A
- **分數**: 10.0/10
- **日期**: 2026-01-30
- **描述**: Gilbert Cisneros 交易 Perris, CA Union High School District GO Ref. Bonds 金額 $250,001 - $500,000（估值 $375,000），遠高於個人平均 $20,544，z-score=6.24

### 7. [HIGH] CLUSTER — Donald Sternoff Jr. Beyer, Sheri Biggs, Steve Cohen
- **標的**: GS
- **分數**: 9.5/10
- **日期**: 2025-12-17
- **描述**: 3 位議員在 5 天內交易 GS：Donald Sternoff Jr. Beyer, Sheri Biggs, Steve Cohen。日期：2025-12-17, 2025-12-18, 2025-12-22

### 8. [HIGH] TIMING — Sheri Biggs
- **標的**: N/A
- **分數**: 7.8/10
- **日期**: 2025-12-01
- **描述**: Sheri Biggs 交易 Apollo Debt Solutions BDC Class S 延遲 88 天才申報（超過 60 天門檻，交易日=2025-12-01，申報日=2026-02-27）

### 9. [HIGH] TIMING — Sheri Biggs
- **標的**: N/A
- **分數**: 7.7/10
- **日期**: 2025-12-02
- **描述**: Sheri Biggs 交易 Fannie Mae Note 9/24/26 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27）

### 10. [HIGH] TIMING — Sheri Biggs
- **標的**: UBS
- **分數**: 7.7/10
- **日期**: 2025-12-02
- **描述**: Sheri Biggs 交易 UBS 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27）

### 11. [HIGH] TIMING — April McClain Delaney
- **標的**: TECH
- **分數**: 7.7/10
- **日期**: 2025-12-02
- **描述**: April McClain Delaney 交易 TECH 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27）

### 12. [HIGH] TIMING — April McClain Delaney
- **標的**: CDW
- **分數**: 7.7/10
- **日期**: 2025-12-02
- **描述**: April McClain Delaney 交易 CDW 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27）

### 13. [HIGH] TIMING — April McClain Delaney
- **標的**: IDXX
- **分數**: 7.7/10
- **日期**: 2025-12-02
- **描述**: April McClain Delaney 交易 IDXX 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27）

### 14. [HIGH] TIMING — April McClain Delaney
- **標的**: LVY
- **分數**: 7.7/10
- **日期**: 2025-12-02
- **描述**: April McClain Delaney 交易 LVY 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27）

### 15. [HIGH] TIMING — April McClain Delaney
- **標的**: MLM
- **分數**: 7.7/10
- **日期**: 2025-12-02
- **描述**: April McClain Delaney 交易 MLM 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27）

### 16. [HIGH] TIMING — April McClain Delaney
- **標的**: PTC
- **分數**: 7.7/10
- **日期**: 2025-12-02
- **描述**: April McClain Delaney 交易 PTC 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27）

### 17. [HIGH] TIMING — April McClain Delaney
- **標的**: PWR
- **分數**: 7.7/10
- **日期**: 2025-12-02
- **描述**: April McClain Delaney 交易 PWR 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27）

### 18. [HIGH] TIMING — April McClain Delaney
- **標的**: TDY
- **分數**: 7.7/10
- **日期**: 2025-12-02
- **描述**: April McClain Delaney 交易 TDY 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27）

### 19. [HIGH] TIMING — April McClain Delaney
- **標的**: TSCO
- **分數**: 7.7/10
- **日期**: 2025-12-02
- **描述**: April McClain Delaney 交易 TSCO 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27）

### 20. [HIGH] TIMING — April McClain Delaney
- **標的**: CLH
- **分數**: 7.6/10
- **日期**: 2025-12-03
- **描述**: April McClain Delaney 交易 CLH 延遲 86 天才申報（超過 60 天門檻，交易日=2025-12-03，申報日=2026-02-27）

### 21. [HIGH] TIMING — April McClain Delaney
- **標的**: TECH
- **分數**: 7.4/10
- **日期**: 2025-12-05
- **描述**: April McClain Delaney 交易 TECH 延遲 84 天才申報（超過 60 天門檻，交易日=2025-12-05，申報日=2026-02-27）

### 22. [HIGH] TIMING — April McClain Delaney
- **標的**: BRO
- **分數**: 7.4/10
- **日期**: 2025-12-05
- **描述**: April McClain Delaney 交易 BRO 延遲 84 天才申報（超過 60 天門檻，交易日=2025-12-05，申報日=2026-02-27）

### 23. [HIGH] TIMING — April McClain Delaney
- **標的**: CDW
- **分數**: 7.4/10
- **日期**: 2025-12-05
- **描述**: April McClain Delaney 交易 CDW 延遲 84 天才申報（超過 60 天門檻，交易日=2025-12-05，申報日=2026-02-27）

### 24. [HIGH] TIMING — April McClain Delaney
- **標的**: PTC
- **分數**: 7.4/10
- **日期**: 2025-12-05
- **描述**: April McClain Delaney 交易 PTC 延遲 84 天才申報（超過 60 天門檻，交易日=2025-12-05，申報日=2026-02-27）

### 25. [HIGH] TIMING — Donald Sternoff Jr. Beyer
- **標的**: S
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Donald Sternoff Jr. Beyer 交易 S 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 26. [HIGH] TIMING — Gilbert Cisneros
- **標的**: ARMK
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 ARMK 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 27. [HIGH] TIMING — Gilbert Cisneros
- **標的**: N/A
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 California State Dept. of Water Resources CVP Revenue Bonds 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 28. [HIGH] TIMING — Gilbert Cisneros
- **標的**: CP
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 CP 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 29. [HIGH] TIMING — Gilbert Cisneros
- **標的**: CSGP
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 CSGP 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 30. [HIGH] TIMING — Gilbert Cisneros
- **標的**: DASH
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 DASH 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 31. [HIGH] TIMING — Gilbert Cisneros
- **標的**: FLEX
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 FLEX 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 32. [HIGH] TIMING — Gilbert Cisneros
- **標的**: GPN
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 GPN 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 33. [HIGH] TIMING — Gilbert Cisneros
- **標的**: ISRG
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 ISRG 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 34. [HIGH] TIMING — Gilbert Cisneros
- **標的**: N/A
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 Los Angeles, CA Dept. Wtr. & Pwr. Wtrwks. Rev. Bonds 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 35. [HIGH] TIMING — Gilbert Cisneros
- **標的**: LPLA
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 LPLA 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 36. [HIGH] TIMING — Gilbert Cisneros
- **標的**: NFLX
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 NFLX 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 37. [HIGH] TIMING — Gilbert Cisneros
- **標的**: PWR
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 PWR 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 38. [HIGH] TIMING — Gilbert Cisneros
- **標的**: SARO
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 SARO 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 39. [HIGH] TIMING — Gilbert Cisneros
- **標的**: SYK
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 SYK 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 40. [HIGH] TIMING — Gilbert Cisneros
- **標的**: TRGP
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 TRGP 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 41. [HIGH] TIMING — Gilbert Cisneros
- **標的**: COO
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 COO 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 42. [HIGH] TIMING — Gilbert Cisneros
- **標的**: WDAY
- **分數**: 6.9/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 WDAY 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27）

### 43. [HIGH] TIMING — Gilbert Cisneros
- **標的**: AGIO
- **分數**: 6.8/10
- **日期**: 2025-12-11
- **描述**: Gilbert Cisneros 交易 AGIO 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27）

### 44. [HIGH] TIMING — Gilbert Cisneros
- **標的**: ARQT
- **分數**: 6.8/10
- **日期**: 2025-12-11
- **描述**: Gilbert Cisneros 交易 ARQT 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27）

### 45. [HIGH] TIMING — Gilbert Cisneros
- **標的**: CBOE
- **分數**: 6.8/10
- **日期**: 2025-12-11
- **描述**: Gilbert Cisneros 交易 CBOE 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27）

### 46. [HIGH] TIMING — Gilbert Cisneros
- **標的**: HAL
- **分數**: 6.8/10
- **日期**: 2025-12-11
- **描述**: Gilbert Cisneros 交易 HAL 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27）

### 47. [HIGH] TIMING — Gilbert Cisneros
- **標的**: ITT
- **分數**: 6.8/10
- **日期**: 2025-12-11
- **描述**: Gilbert Cisneros 交易 ITT 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27）

### 48. [HIGH] TIMING — Gilbert Cisneros
- **標的**: K
- **分數**: 6.8/10
- **日期**: 2025-12-11
- **描述**: Gilbert Cisneros 交易 K 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27）

### 49. [HIGH] TIMING — Gilbert Cisneros
- **標的**: PRIM
- **分數**: 6.8/10
- **日期**: 2025-12-11
- **描述**: Gilbert Cisneros 交易 PRIM 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27）

### 50. [HIGH] TIMING — Gilbert Cisneros
- **標的**: SUPN
- **分數**: 6.8/10
- **日期**: 2025-12-11
- **描述**: Gilbert Cisneros 交易 SUPN 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27）

### 51. [HIGH] TIMING — Gilbert Cisneros
- **標的**: COCO
- **分數**: 6.8/10
- **日期**: 2025-12-11
- **描述**: Gilbert Cisneros 交易 COCO 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27）

### 52. [HIGH] TIMING — Richard W. Allen
- **標的**: FERG
- **分數**: 6.7/10
- **日期**: 2025-12-12
- **描述**: Richard W. Allen 交易 FERG 延遲 77 天才申報（超過 60 天門檻，交易日=2025-12-12，申報日=2026-02-27）

### 53. [HIGH] TIMING — April McClain Delaney
- **標的**: BRO
- **分數**: 6.7/10
- **日期**: 2025-12-12
- **描述**: April McClain Delaney 交易 BRO 延遲 77 天才申報（超過 60 天門檻，交易日=2025-12-12，申報日=2026-02-27）

### 54. [HIGH] TIMING — April McClain Delaney
- **標的**: TSCO
- **分數**: 6.7/10
- **日期**: 2025-12-12
- **描述**: April McClain Delaney 交易 TSCO 延遲 77 天才申報（超過 60 天門檻，交易日=2025-12-12，申報日=2026-02-27）

### 55. [HIGH] TIMING — Gilbert Cisneros
- **標的**: AVAV
- **分數**: 6.4/10
- **日期**: 2025-12-15
- **描述**: Gilbert Cisneros 交易 AVAV 延遲 74 天才申報（超過 60 天門檻，交易日=2025-12-15，申報日=2026-02-27）

### 56. [HIGH] TIMING — Gilbert Cisneros
- **標的**: AVGO
- **分數**: 6.2/10
- **日期**: 2025-12-17
- **描述**: Gilbert Cisneros 交易 AVGO 延遲 72 天才申報（超過 60 天門檻，交易日=2025-12-17，申報日=2026-02-27）

### 57. [HIGH] TIMING — Gilbert Cisneros
- **標的**: N/A
- **分數**: 6.2/10
- **日期**: 2025-12-17
- **描述**: Gilbert Cisneros 交易 San Rafael, CA Elementary School District GO Bonds 延遲 72 天才申報（超過 60 天門檻，交易日=2025-12-17，申報日=2026-02-27）

### 58. [HIGH] TIMING — Steve Cohen
- **標的**: OZKAP
- **分數**: 6.2/10
- **日期**: 2025-12-17
- **描述**: Steve Cohen 交易 OZKAP 延遲 72 天才申報（超過 60 天門檻，交易日=2025-12-17，申報日=2026-02-27）

### 59. [HIGH] TIMING — Steve Cohen
- **標的**: RFD
- **分數**: 6.2/10
- **日期**: 2025-12-17
- **描述**: Steve Cohen 交易 RFD 延遲 72 天才申報（超過 60 天門檻，交易日=2025-12-17，申報日=2026-02-27）

### 60. [HIGH] TIMING — Steve Cohen
- **標的**: GS
- **分數**: 6.2/10
- **日期**: 2025-12-17
- **描述**: Steve Cohen 交易 GS 延遲 72 天才申報（超過 60 天門檻，交易日=2025-12-17，申報日=2026-02-27）

### 61. [HIGH] TIMING — Steve Cohen
- **標的**: MS
- **分數**: 6.2/10
- **日期**: 2025-12-17
- **描述**: Steve Cohen 交易 MS 延遲 72 天才申報（超過 60 天門檻，交易日=2025-12-17，申報日=2026-02-27）

### 62. [HIGH] TIMING — Suzan K. DelBene
- **標的**: N/A
- **分數**: 6.2/10
- **日期**: 2025-12-17
- **描述**: Suzan K. DelBene 交易 Tarrant CNTY Tex Cultural Ed Facs Fin 5.00% Due Nov 15, 2051 [GS] 延遲 72 天才申報（超過 60 天門檻，交易日=2025-12-17，申報日=2026-02-27）

### 63. [HIGH] TIMING — Donald Sternoff Jr. Beyer
- **標的**: GS
- **分數**: 6.1/10
- **日期**: 2025-12-18
- **描述**: Donald Sternoff Jr. Beyer 交易 GS 延遲 71 天才申報（超過 60 天門檻，交易日=2025-12-18，申報日=2026-02-27）

### 64. [HIGH] TIMING — Donald Sternoff Jr. Beyer
- **標的**: S
- **分數**: 6.1/10
- **日期**: 2025-12-18
- **描述**: Donald Sternoff Jr. Beyer 交易 S 延遲 71 天才申報（超過 60 天門檻，交易日=2025-12-18，申報日=2026-02-27）

### 65. [HIGH] TIMING — Gilbert Cisneros
- **標的**: AZN
- **分數**: 6.1/10
- **日期**: 2025-12-18
- **描述**: Gilbert Cisneros 交易 AZN 延遲 71 天才申報（超過 60 天門檻，交易日=2025-12-18，申報日=2026-02-27）

### 66. [HIGH] TIMING — Gilbert Cisneros
- **標的**: RACE
- **分數**: 6.1/10
- **日期**: 2025-12-18
- **描述**: Gilbert Cisneros 交易 RACE 延遲 71 天才申報（超過 60 天門檻，交易日=2025-12-18，申報日=2026-02-27）

### 67. [HIGH] TIMING — Gilbert Cisneros
- **標的**: AFT
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 AFT 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 68. [HIGH] TIMING — Gilbert Cisneros
- **標的**: ACN
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 ACN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 69. [HIGH] TIMING — Gilbert Cisneros
- **標的**: AMD
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 AMD 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 70. [HIGH] TIMING — Gilbert Cisneros
- **標的**: ARE
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 ARE 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 71. [HIGH] TIMING — Gilbert Cisneros
- **標的**: AMZN
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 AMZN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 72. [HIGH] TIMING — Gilbert Cisneros
- **標的**: AMCR
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 AMCR 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 73. [HIGH] TIMING — Gilbert Cisneros
- **標的**: APP
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 APP 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 74. [HIGH] TIMING — Gilbert Cisneros
- **標的**: AJG
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 AJG 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 75. [HIGH] TIMING — Gilbert Cisneros
- **標的**: BKR
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 BKR 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 76. [HIGH] TIMING — Gilbert Cisneros
- **標的**: SQ
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 SQ 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 77. [HIGH] TIMING — Gilbert Cisneros
- **標的**: BA
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 BA 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 78. [HIGH] TIMING — Gilbert Cisneros
- **標的**: BKNG
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 BKNG 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 79. [HIGH] TIMING — Gilbert Cisneros
- **標的**: BMY
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 BMY 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 80. [HIGH] TIMING — Gilbert Cisneros
- **標的**: BXP
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 BXP 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 81. [HIGH] TIMING — Gilbert Cisneros
- **標的**: CLX
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 CLX 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 82. [HIGH] TIMING — Gilbert Cisneros
- **標的**: COIN
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 COIN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 83. [HIGH] TIMING — Gilbert Cisneros
- **標的**: CAG
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 CAG 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 84. [HIGH] TIMING — Gilbert Cisneros
- **標的**: STZ
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 STZ 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 85. [HIGH] TIMING — Gilbert Cisneros
- **標的**: CTRA
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 CTRA 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 86. [HIGH] TIMING — Gilbert Cisneros
- **標的**: CCI
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 CCI 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 87. [HIGH] TIMING — Gilbert Cisneros
- **標的**: DASH
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 DASH 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 88. [HIGH] TIMING — Gilbert Cisneros
- **標的**: ERIE
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 ERIE 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 89. [HIGH] TIMING — Gilbert Cisneros
- **標的**: EXE
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 EXE 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 90. [HIGH] TIMING — Gilbert Cisneros
- **標的**: FICO
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 FICO 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 91. [HIGH] TIMING — Gilbert Cisneros
- **標的**: FIS
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 FIS 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 92. [HIGH] TIMING — Gilbert Cisneros
- **標的**: FISV
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 FISV 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 93. [HIGH] TIMING — Gilbert Cisneros
- **標的**: GEV
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 GEV 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 94. [HIGH] TIMING — Gilbert Cisneros
- **標的**: GIS
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 GIS 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 95. [HIGH] TIMING — Gilbert Cisneros
- **標的**: GPN
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 GPN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 96. [HIGH] TIMING — Gilbert Cisneros
- **標的**: IBM
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 IBM 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 97. [HIGH] TIMING — Gilbert Cisneros
- **標的**: INVH
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 INVH 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 98. [HIGH] TIMING — Gilbert Cisneros
- **標的**: LEN
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 LEN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 99. [HIGH] TIMING — Gilbert Cisneros
- **標的**: LIN
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 LIN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 100. [HIGH] TIMING — Gilbert Cisneros
- **標的**: LMT
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 LMT 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 101. [HIGH] TIMING — Gilbert Cisneros
- **標的**: MCK
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 MCK 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 102. [HIGH] TIMING — Gilbert Cisneros
- **標的**: MRK
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 MRK 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 103. [HIGH] TIMING — Gilbert Cisneros
- **標的**: MSFT
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 MSFT 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 104. [HIGH] TIMING — Gilbert Cisneros
- **標的**: MBJBF
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 MBJBF 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 105. [HIGH] TIMING — Gilbert Cisneros
- **標的**: NVDA
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 NVDA 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 106. [HIGH] TIMING — Gilbert Cisneros
- **標的**: ORCL
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 ORCL 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 107. [HIGH] TIMING — Gilbert Cisneros
- **標的**: PFE
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 PFE 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 108. [HIGH] TIMING — Gilbert Cisneros
- **標的**: PSA
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 PSA 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 109. [HIGH] TIMING — Gilbert Cisneros
- **標的**: O
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 O 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 110. [HIGH] TIMING — Gilbert Cisneros
- **標的**: SBAC
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 SBAC 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 111. [HIGH] TIMING — Gilbert Cisneros
- **標的**: SBAC
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 SBAC 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 112. [HIGH] TIMING — Gilbert Cisneros
- **標的**: CPB
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 CPB 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 113. [HIGH] TIMING — Gilbert Cisneros
- **標的**: CI
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 CI 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 114. [HIGH] TIMING — Gilbert Cisneros
- **標的**: UBER
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 UBER 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 115. [HIGH] TIMING — Gilbert Cisneros
- **標的**: UAL
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 UAL 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 116. [HIGH] TIMING — Gilbert Cisneros
- **標的**: UNH
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 UNH 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 117. [HIGH] TIMING — Gilbert Cisneros
- **標的**: VRSN
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 VRSN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 118. [HIGH] TIMING — Gilbert Cisneros
- **標的**: VRSK
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 VRSK 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 119. [HIGH] TIMING — Gilbert Cisneros
- **標的**: VICI
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 VICI 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 120. [HIGH] TIMING — Gilbert Cisneros
- **標的**: ZTS
- **分數**: 6.0/10
- **日期**: 2025-12-19
- **描述**: Gilbert Cisneros 交易 ZTS 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27）

### 121. [HIGH] TIMING — Sheri Biggs
- **標的**: GS
- **分數**: 5.7/10
- **日期**: 2025-12-22
- **描述**: Sheri Biggs 交易 GS 延遲 67 天才申報（超過 60 天門檻，交易日=2025-12-22，申報日=2026-02-27）

### 122. [HIGH] SIZE — David H McCormick
- **標的**: GS
- **分數**: 5.6/10
- **日期**: 2026-01-23
- **描述**: David H McCormick 交易 GS 金額 $1,000,001 - $5,000,000（估值 $3,000,000），遠高於個人平均 $555,556，z-score=2.81

### 123. [HIGH] TIMING — Donald Sternoff Jr. Beyer
- **標的**: N/A
- **分數**: 5.6/10
- **日期**: 2025-12-10
- **描述**: Donald Sternoff Jr. Beyer 交易 Virginia ST 4.00% 8/1/38 延遲 66 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-14）

### 124. [HIGH] TIMING — Gilbert Cisneros
- **標的**: AMZN
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 AMZN 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 125. [HIGH] TIMING — Gilbert Cisneros
- **標的**: ANET
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 ANET 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 126. [HIGH] TIMING — Gilbert Cisneros
- **標的**: AZO
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 AZO 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 127. [HIGH] TIMING — Gilbert Cisneros
- **標的**: BRK.B
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 BRK.B 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 128. [HIGH] TIMING — Gilbert Cisneros
- **標的**: BE
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 BE 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 129. [HIGH] TIMING — Gilbert Cisneros
- **標的**: BSX
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 BSX 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 130. [HIGH] TIMING — Gilbert Cisneros
- **標的**: CCJ
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 CCJ 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 131. [HIGH] TIMING — Gilbert Cisneros
- **標的**: SCHW
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 SCHW 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 132. [HIGH] TIMING — Gilbert Cisneros
- **標的**: CVX
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 CVX 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 133. [HIGH] TIMING — Gilbert Cisneros
- **標的**: NET
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 NET 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 134. [HIGH] TIMING — Gilbert Cisneros
- **標的**: COIN
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 COIN 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 135. [HIGH] TIMING — Gilbert Cisneros
- **標的**: COST
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 COST 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 136. [HIGH] TIMING — Gilbert Cisneros
- **標的**: ETN
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 ETN 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 137. [HIGH] TIMING — Gilbert Cisneros
- **標的**: HD
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 HD 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 138. [HIGH] TIMING — Gilbert Cisneros
- **標的**: MELI
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 MELI 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 139. [HIGH] TIMING — Gilbert Cisneros
- **標的**: META
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 META 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 140. [HIGH] TIMING — Gilbert Cisneros
- **標的**: NVDA
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 NVDA 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 141. [HIGH] TIMING — Gilbert Cisneros
- **標的**: ORCL
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 ORCL 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 142. [HIGH] TIMING — Gilbert Cisneros
- **標的**: PG
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 PG 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 143. [HIGH] TIMING — Gilbert Cisneros
- **標的**: PWR
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 PWR 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 144. [HIGH] TIMING — Gilbert Cisneros
- **標的**: HOOD
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 HOOD 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 145. [HIGH] TIMING — Gilbert Cisneros
- **標的**: RBLX
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 RBLX 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 146. [HIGH] TIMING — Gilbert Cisneros
- **標的**: SPOT
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 SPOT 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 147. [HIGH] TIMING — Gilbert Cisneros
- **標的**: TSM
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 TSM 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 148. [HIGH] TIMING — Gilbert Cisneros
- **標的**: TDG
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 TDG 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 149. [HIGH] TIMING — Gilbert Cisneros
- **標的**: VRT
- **分數**: 5.5/10
- **日期**: 2025-12-24
- **描述**: Gilbert Cisneros 交易 VRT 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27）

### 150. [HIGH] SIZE — Sheri Biggs
- **標的**: HN
- **分數**: 5.5/10
- **日期**: 2025-12-26
- **描述**: Sheri Biggs 交易 HN 金額 $250,001 - $500,000（估值 $375,000），遠高於個人平均 $66,389，z-score=2.75

### 151. [HIGH] SIZE — Gilbert Cisneros
- **標的**: N/A
- **分數**: 5.4/10
- **日期**: 2025-12-10
- **描述**: Gilbert Cisneros 交易 California State Dept. of Water Resources CVP Revenue Bonds 金額 $100,001 - $250,000（估值 $175,000），遠高於個人平均 $20,544，z-score=2.72

### 152. [HIGH] SIZE — Gilbert Cisneros
- **標的**: N/A
- **分數**: 5.4/10
- **日期**: 2025-12-17
- **描述**: Gilbert Cisneros 交易 San Rafael, CA Elementary School District GO Bonds 金額 $100,001 - $250,000（估值 $175,000），遠高於個人平均 $20,544，z-score=2.72

### 153. [HIGH] SIZE — Gilbert Cisneros
- **標的**: N/A
- **分數**: 5.4/10
- **日期**: 2026-01-30
- **描述**: Gilbert Cisneros 交易 Milwaukee, Wisconsin GO Promissory Notes Series N2 金額 $100,001 - $250,000（估值 $175,000），遠高於個人平均 $20,544，z-score=2.72

### 154. [HIGH] TIMING — Richard W. Allen
- **標的**: NFLX
- **分數**: 5.4/10
- **日期**: 2025-12-12
- **描述**: Richard W. Allen 交易 NFLX 延遲 64 天才申報（超過 60 天門檻，交易日=2025-12-12，申報日=2026-02-14）

### 155. [HIGH] TIMING — Sheri Biggs
- **標的**: HN
- **分數**: 5.3/10
- **日期**: 2025-12-26
- **描述**: Sheri Biggs 交易 HN 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27）

### 156. [HIGH] TIMING — Sheri Biggs
- **標的**: HN
- **分數**: 5.3/10
- **日期**: 2025-12-26
- **描述**: Sheri Biggs 交易 HN 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27）

### 157. [HIGH] TIMING — Gilbert Cisneros
- **標的**: AJINF
- **分數**: 5.3/10
- **日期**: 2025-12-26
- **描述**: Gilbert Cisneros 交易 AJINF 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27）

### 158. [HIGH] TIMING — Gilbert Cisneros
- **標的**: MHIYF
- **分數**: 5.3/10
- **日期**: 2025-12-26
- **描述**: Gilbert Cisneros 交易 MHIYF 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27）

### 159. [HIGH] TIMING — Gilbert Cisneros
- **標的**: NTDOF
- **分數**: 5.3/10
- **日期**: 2025-12-26
- **描述**: Gilbert Cisneros 交易 NTDOF 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27）

### 160. [HIGH] TIMING — Steve Cohen
- **標的**: SONY
- **分數**: 5.3/10
- **日期**: 2025-12-26
- **描述**: Steve Cohen 交易 SONY 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27）

### 161. [HIGH] TIMING — Michael A. Jr. Collins
- **標的**: N/A
- **分數**: 5.3/10
- **日期**: 2025-12-26
- **描述**: Michael A. Jr. Collins 交易 usdc 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27）

### 162. [HIGH] SIZE — Richard Blumenthal
- **標的**: N/A
- **分數**: 4.7/10
- **日期**: 2026-01-16
- **描述**: Richard Blumenthal 交易 KIRKOSWALD GLOBAL MACRO FUND LP 金額 $50,001 - $100,000（估值 $75,000），遠高於個人平均 $29,056，z-score=2.33

### 163. [HIGH] SIZE — Steve Cohen
- **標的**: MS
- **分數**: 4.2/10
- **日期**: 2025-12-17
- **描述**: Steve Cohen 交易 MS 金額 $50,001 - $100,000（估值 $75,000），遠高於個人平均 $31,571，z-score=2.10

### 164. [HIGH] SIZE — Richard W. Allen
- **標的**: N/A
- **分數**: 4.2/10
- **日期**: 2026-01-26
- **描述**: Richard W. Allen 交易 US Treasury Note 3.2% DUE 01/31/28 金額 $100,001 - $250,000（估值 $175,000），遠高於個人平均 $59,250，z-score=2.09

---

## 完整異常列表

| # | 類型 | 嚴重度 | 分數 | 議員 | 標的 | 描述 |
|---|------|--------|------|------|------|------|
| 1 | SIZE | CRITICAL | 10.0 | Gilbert Cisneros | N/A | Gilbert Cisneros 交易 Los Angeles, CA Dept. Wtr. & Pwr. Wtrwks. Rev. Bonds 金額 $250... |
| 2 | SIZE | CRITICAL | 10.0 | Gilbert Cisneros | N/A | Gilbert Cisneros 交易 Wisconsin State Health & Educational Facilities Authority Re... |
| 3 | SIZE | CRITICAL | 10.0 | Gilbert Cisneros | N/A | Gilbert Cisneros 交易 Southeast Energy Authority Cooperative District, Alabama Bon... |
| 4 | SIZE | CRITICAL | 10.0 | Gilbert Cisneros | N/A | Gilbert Cisneros 交易 California Community Choice Financing Authority Rev Bonds 金額... |
| 5 | SIZE | CRITICAL | 10.0 | Gilbert Cisneros | N/A | Gilbert Cisneros 交易 California Community Choice Financing Authority Rev Bonds 金額... |
| 6 | SIZE | CRITICAL | 10.0 | Gilbert Cisneros | N/A | Gilbert Cisneros 交易 Perris, CA Union High School District GO Ref. Bonds 金額 $250,... |
| 7 | CLUSTER | HIGH | 9.5 | Donald Sternoff Jr.  | GS | 3 位議員在 5 天內交易 GS：Donald Sternoff Jr. Beyer, Sheri Biggs, Steve Cohen。日期：2025-12-... |
| 8 | TIMING | HIGH | 7.8 | Sheri Biggs | N/A | Sheri Biggs 交易 Apollo Debt Solutions BDC Class S 延遲 88 天才申報（超過 60 天門檻，交易日=2025-1... |
| 9 | TIMING | HIGH | 7.7 | Sheri Biggs | N/A | Sheri Biggs 交易 Fannie Mae Note 9/24/26 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2... |
| 10 | TIMING | HIGH | 7.7 | Sheri Biggs | UBS | Sheri Biggs 交易 UBS 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27） |
| 11 | TIMING | HIGH | 7.7 | April McClain Delane | TECH | April McClain Delaney 交易 TECH 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27... |
| 12 | TIMING | HIGH | 7.7 | April McClain Delane | CDW | April McClain Delaney 交易 CDW 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27） |
| 13 | TIMING | HIGH | 7.7 | April McClain Delane | IDXX | April McClain Delaney 交易 IDXX 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27... |
| 14 | TIMING | HIGH | 7.7 | April McClain Delane | LVY | April McClain Delaney 交易 LVY 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27） |
| 15 | TIMING | HIGH | 7.7 | April McClain Delane | MLM | April McClain Delaney 交易 MLM 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27） |
| 16 | TIMING | HIGH | 7.7 | April McClain Delane | PTC | April McClain Delaney 交易 PTC 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27） |
| 17 | TIMING | HIGH | 7.7 | April McClain Delane | PWR | April McClain Delaney 交易 PWR 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27） |
| 18 | TIMING | HIGH | 7.7 | April McClain Delane | TDY | April McClain Delaney 交易 TDY 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27） |
| 19 | TIMING | HIGH | 7.7 | April McClain Delane | TSCO | April McClain Delaney 交易 TSCO 延遲 87 天才申報（超過 60 天門檻，交易日=2025-12-02，申報日=2026-02-27... |
| 20 | TIMING | HIGH | 7.6 | April McClain Delane | CLH | April McClain Delaney 交易 CLH 延遲 86 天才申報（超過 60 天門檻，交易日=2025-12-03，申報日=2026-02-27） |
| 21 | TIMING | HIGH | 7.4 | April McClain Delane | TECH | April McClain Delaney 交易 TECH 延遲 84 天才申報（超過 60 天門檻，交易日=2025-12-05，申報日=2026-02-27... |
| 22 | TIMING | HIGH | 7.4 | April McClain Delane | BRO | April McClain Delaney 交易 BRO 延遲 84 天才申報（超過 60 天門檻，交易日=2025-12-05，申報日=2026-02-27） |
| 23 | TIMING | HIGH | 7.4 | April McClain Delane | CDW | April McClain Delaney 交易 CDW 延遲 84 天才申報（超過 60 天門檻，交易日=2025-12-05，申報日=2026-02-27） |
| 24 | TIMING | HIGH | 7.4 | April McClain Delane | PTC | April McClain Delaney 交易 PTC 延遲 84 天才申報（超過 60 天門檻，交易日=2025-12-05，申報日=2026-02-27） |
| 25 | TIMING | HIGH | 6.9 | Donald Sternoff Jr.  | S | Donald Sternoff Jr. Beyer 交易 S 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-2... |
| 26 | TIMING | HIGH | 6.9 | Gilbert Cisneros | ARMK | Gilbert Cisneros 交易 ARMK 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 27 | TIMING | HIGH | 6.9 | Gilbert Cisneros | N/A | Gilbert Cisneros 交易 California State Dept. of Water Resources CVP Revenue Bonds ... |
| 28 | TIMING | HIGH | 6.9 | Gilbert Cisneros | CP | Gilbert Cisneros 交易 CP 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 29 | TIMING | HIGH | 6.9 | Gilbert Cisneros | CSGP | Gilbert Cisneros 交易 CSGP 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 30 | TIMING | HIGH | 6.9 | Gilbert Cisneros | DASH | Gilbert Cisneros 交易 DASH 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 31 | TIMING | HIGH | 6.9 | Gilbert Cisneros | FLEX | Gilbert Cisneros 交易 FLEX 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 32 | TIMING | HIGH | 6.9 | Gilbert Cisneros | GPN | Gilbert Cisneros 交易 GPN 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 33 | TIMING | HIGH | 6.9 | Gilbert Cisneros | ISRG | Gilbert Cisneros 交易 ISRG 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 34 | TIMING | HIGH | 6.9 | Gilbert Cisneros | N/A | Gilbert Cisneros 交易 Los Angeles, CA Dept. Wtr. & Pwr. Wtrwks. Rev. Bonds 延遲 79 天... |
| 35 | TIMING | HIGH | 6.9 | Gilbert Cisneros | LPLA | Gilbert Cisneros 交易 LPLA 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 36 | TIMING | HIGH | 6.9 | Gilbert Cisneros | NFLX | Gilbert Cisneros 交易 NFLX 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 37 | TIMING | HIGH | 6.9 | Gilbert Cisneros | PWR | Gilbert Cisneros 交易 PWR 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 38 | TIMING | HIGH | 6.9 | Gilbert Cisneros | SARO | Gilbert Cisneros 交易 SARO 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 39 | TIMING | HIGH | 6.9 | Gilbert Cisneros | SYK | Gilbert Cisneros 交易 SYK 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 40 | TIMING | HIGH | 6.9 | Gilbert Cisneros | TRGP | Gilbert Cisneros 交易 TRGP 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 41 | TIMING | HIGH | 6.9 | Gilbert Cisneros | COO | Gilbert Cisneros 交易 COO 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 42 | TIMING | HIGH | 6.9 | Gilbert Cisneros | WDAY | Gilbert Cisneros 交易 WDAY 延遲 79 天才申報（超過 60 天門檻，交易日=2025-12-10，申報日=2026-02-27） |
| 43 | TIMING | HIGH | 6.8 | Gilbert Cisneros | AGIO | Gilbert Cisneros 交易 AGIO 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27） |
| 44 | TIMING | HIGH | 6.8 | Gilbert Cisneros | ARQT | Gilbert Cisneros 交易 ARQT 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27） |
| 45 | TIMING | HIGH | 6.8 | Gilbert Cisneros | CBOE | Gilbert Cisneros 交易 CBOE 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27） |
| 46 | TIMING | HIGH | 6.8 | Gilbert Cisneros | HAL | Gilbert Cisneros 交易 HAL 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27） |
| 47 | TIMING | HIGH | 6.8 | Gilbert Cisneros | ITT | Gilbert Cisneros 交易 ITT 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27） |
| 48 | TIMING | HIGH | 6.8 | Gilbert Cisneros | K | Gilbert Cisneros 交易 K 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27） |
| 49 | TIMING | HIGH | 6.8 | Gilbert Cisneros | PRIM | Gilbert Cisneros 交易 PRIM 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27） |
| 50 | TIMING | HIGH | 6.8 | Gilbert Cisneros | SUPN | Gilbert Cisneros 交易 SUPN 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27） |
| 51 | TIMING | HIGH | 6.8 | Gilbert Cisneros | COCO | Gilbert Cisneros 交易 COCO 延遲 78 天才申報（超過 60 天門檻，交易日=2025-12-11，申報日=2026-02-27） |
| 52 | TIMING | HIGH | 6.7 | Richard W. Allen | FERG | Richard W. Allen 交易 FERG 延遲 77 天才申報（超過 60 天門檻，交易日=2025-12-12，申報日=2026-02-27） |
| 53 | TIMING | HIGH | 6.7 | April McClain Delane | BRO | April McClain Delaney 交易 BRO 延遲 77 天才申報（超過 60 天門檻，交易日=2025-12-12，申報日=2026-02-27） |
| 54 | TIMING | HIGH | 6.7 | April McClain Delane | TSCO | April McClain Delaney 交易 TSCO 延遲 77 天才申報（超過 60 天門檻，交易日=2025-12-12，申報日=2026-02-27... |
| 55 | TIMING | HIGH | 6.4 | Gilbert Cisneros | AVAV | Gilbert Cisneros 交易 AVAV 延遲 74 天才申報（超過 60 天門檻，交易日=2025-12-15，申報日=2026-02-27） |
| 56 | TIMING | HIGH | 6.2 | Gilbert Cisneros | AVGO | Gilbert Cisneros 交易 AVGO 延遲 72 天才申報（超過 60 天門檻，交易日=2025-12-17，申報日=2026-02-27） |
| 57 | TIMING | HIGH | 6.2 | Gilbert Cisneros | N/A | Gilbert Cisneros 交易 San Rafael, CA Elementary School District GO Bonds 延遲 72 天才申... |
| 58 | TIMING | HIGH | 6.2 | Steve Cohen | OZKAP | Steve Cohen 交易 OZKAP 延遲 72 天才申報（超過 60 天門檻，交易日=2025-12-17，申報日=2026-02-27） |
| 59 | TIMING | HIGH | 6.2 | Steve Cohen | RFD | Steve Cohen 交易 RFD 延遲 72 天才申報（超過 60 天門檻，交易日=2025-12-17，申報日=2026-02-27） |
| 60 | TIMING | HIGH | 6.2 | Steve Cohen | GS | Steve Cohen 交易 GS 延遲 72 天才申報（超過 60 天門檻，交易日=2025-12-17，申報日=2026-02-27） |
| 61 | TIMING | HIGH | 6.2 | Steve Cohen | MS | Steve Cohen 交易 MS 延遲 72 天才申報（超過 60 天門檻，交易日=2025-12-17，申報日=2026-02-27） |
| 62 | TIMING | HIGH | 6.2 | Suzan K. DelBene | N/A | Suzan K. DelBene 交易 Tarrant CNTY Tex Cultural Ed Facs Fin 5.00% Due Nov 15, 2051... |
| 63 | TIMING | HIGH | 6.1 | Donald Sternoff Jr.  | GS | Donald Sternoff Jr. Beyer 交易 GS 延遲 71 天才申報（超過 60 天門檻，交易日=2025-12-18，申報日=2026-02-... |
| 64 | TIMING | HIGH | 6.1 | Donald Sternoff Jr.  | S | Donald Sternoff Jr. Beyer 交易 S 延遲 71 天才申報（超過 60 天門檻，交易日=2025-12-18，申報日=2026-02-2... |
| 65 | TIMING | HIGH | 6.1 | Gilbert Cisneros | AZN | Gilbert Cisneros 交易 AZN 延遲 71 天才申報（超過 60 天門檻，交易日=2025-12-18，申報日=2026-02-27） |
| 66 | TIMING | HIGH | 6.1 | Gilbert Cisneros | RACE | Gilbert Cisneros 交易 RACE 延遲 71 天才申報（超過 60 天門檻，交易日=2025-12-18，申報日=2026-02-27） |
| 67 | TIMING | HIGH | 6.0 | Gilbert Cisneros | AFT | Gilbert Cisneros 交易 AFT 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 68 | TIMING | HIGH | 6.0 | Gilbert Cisneros | ACN | Gilbert Cisneros 交易 ACN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 69 | TIMING | HIGH | 6.0 | Gilbert Cisneros | AMD | Gilbert Cisneros 交易 AMD 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 70 | TIMING | HIGH | 6.0 | Gilbert Cisneros | ARE | Gilbert Cisneros 交易 ARE 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 71 | TIMING | HIGH | 6.0 | Gilbert Cisneros | AMZN | Gilbert Cisneros 交易 AMZN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 72 | TIMING | HIGH | 6.0 | Gilbert Cisneros | AMCR | Gilbert Cisneros 交易 AMCR 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 73 | TIMING | HIGH | 6.0 | Gilbert Cisneros | APP | Gilbert Cisneros 交易 APP 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 74 | TIMING | HIGH | 6.0 | Gilbert Cisneros | AJG | Gilbert Cisneros 交易 AJG 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 75 | TIMING | HIGH | 6.0 | Gilbert Cisneros | BKR | Gilbert Cisneros 交易 BKR 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 76 | TIMING | HIGH | 6.0 | Gilbert Cisneros | SQ | Gilbert Cisneros 交易 SQ 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 77 | TIMING | HIGH | 6.0 | Gilbert Cisneros | BA | Gilbert Cisneros 交易 BA 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 78 | TIMING | HIGH | 6.0 | Gilbert Cisneros | BKNG | Gilbert Cisneros 交易 BKNG 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 79 | TIMING | HIGH | 6.0 | Gilbert Cisneros | BMY | Gilbert Cisneros 交易 BMY 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 80 | TIMING | HIGH | 6.0 | Gilbert Cisneros | BXP | Gilbert Cisneros 交易 BXP 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 81 | TIMING | HIGH | 6.0 | Gilbert Cisneros | CLX | Gilbert Cisneros 交易 CLX 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 82 | TIMING | HIGH | 6.0 | Gilbert Cisneros | COIN | Gilbert Cisneros 交易 COIN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 83 | TIMING | HIGH | 6.0 | Gilbert Cisneros | CAG | Gilbert Cisneros 交易 CAG 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 84 | TIMING | HIGH | 6.0 | Gilbert Cisneros | STZ | Gilbert Cisneros 交易 STZ 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 85 | TIMING | HIGH | 6.0 | Gilbert Cisneros | CTRA | Gilbert Cisneros 交易 CTRA 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 86 | TIMING | HIGH | 6.0 | Gilbert Cisneros | CCI | Gilbert Cisneros 交易 CCI 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 87 | TIMING | HIGH | 6.0 | Gilbert Cisneros | DASH | Gilbert Cisneros 交易 DASH 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 88 | TIMING | HIGH | 6.0 | Gilbert Cisneros | ERIE | Gilbert Cisneros 交易 ERIE 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 89 | TIMING | HIGH | 6.0 | Gilbert Cisneros | EXE | Gilbert Cisneros 交易 EXE 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 90 | TIMING | HIGH | 6.0 | Gilbert Cisneros | FICO | Gilbert Cisneros 交易 FICO 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 91 | TIMING | HIGH | 6.0 | Gilbert Cisneros | FIS | Gilbert Cisneros 交易 FIS 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 92 | TIMING | HIGH | 6.0 | Gilbert Cisneros | FISV | Gilbert Cisneros 交易 FISV 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 93 | TIMING | HIGH | 6.0 | Gilbert Cisneros | GEV | Gilbert Cisneros 交易 GEV 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 94 | TIMING | HIGH | 6.0 | Gilbert Cisneros | GIS | Gilbert Cisneros 交易 GIS 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 95 | TIMING | HIGH | 6.0 | Gilbert Cisneros | GPN | Gilbert Cisneros 交易 GPN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 96 | TIMING | HIGH | 6.0 | Gilbert Cisneros | IBM | Gilbert Cisneros 交易 IBM 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 97 | TIMING | HIGH | 6.0 | Gilbert Cisneros | INVH | Gilbert Cisneros 交易 INVH 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 98 | TIMING | HIGH | 6.0 | Gilbert Cisneros | LEN | Gilbert Cisneros 交易 LEN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 99 | TIMING | HIGH | 6.0 | Gilbert Cisneros | LIN | Gilbert Cisneros 交易 LIN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 100 | TIMING | HIGH | 6.0 | Gilbert Cisneros | LMT | Gilbert Cisneros 交易 LMT 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 101 | TIMING | HIGH | 6.0 | Gilbert Cisneros | MCK | Gilbert Cisneros 交易 MCK 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 102 | TIMING | HIGH | 6.0 | Gilbert Cisneros | MRK | Gilbert Cisneros 交易 MRK 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 103 | TIMING | HIGH | 6.0 | Gilbert Cisneros | MSFT | Gilbert Cisneros 交易 MSFT 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 104 | TIMING | HIGH | 6.0 | Gilbert Cisneros | MBJBF | Gilbert Cisneros 交易 MBJBF 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 105 | TIMING | HIGH | 6.0 | Gilbert Cisneros | NVDA | Gilbert Cisneros 交易 NVDA 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 106 | TIMING | HIGH | 6.0 | Gilbert Cisneros | ORCL | Gilbert Cisneros 交易 ORCL 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 107 | TIMING | HIGH | 6.0 | Gilbert Cisneros | PFE | Gilbert Cisneros 交易 PFE 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 108 | TIMING | HIGH | 6.0 | Gilbert Cisneros | PSA | Gilbert Cisneros 交易 PSA 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 109 | TIMING | HIGH | 6.0 | Gilbert Cisneros | O | Gilbert Cisneros 交易 O 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 110 | TIMING | HIGH | 6.0 | Gilbert Cisneros | SBAC | Gilbert Cisneros 交易 SBAC 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 111 | TIMING | HIGH | 6.0 | Gilbert Cisneros | SBAC | Gilbert Cisneros 交易 SBAC 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 112 | TIMING | HIGH | 6.0 | Gilbert Cisneros | CPB | Gilbert Cisneros 交易 CPB 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 113 | TIMING | HIGH | 6.0 | Gilbert Cisneros | CI | Gilbert Cisneros 交易 CI 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 114 | TIMING | HIGH | 6.0 | Gilbert Cisneros | UBER | Gilbert Cisneros 交易 UBER 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 115 | TIMING | HIGH | 6.0 | Gilbert Cisneros | UAL | Gilbert Cisneros 交易 UAL 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 116 | TIMING | HIGH | 6.0 | Gilbert Cisneros | UNH | Gilbert Cisneros 交易 UNH 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 117 | TIMING | HIGH | 6.0 | Gilbert Cisneros | VRSN | Gilbert Cisneros 交易 VRSN 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 118 | TIMING | HIGH | 6.0 | Gilbert Cisneros | VRSK | Gilbert Cisneros 交易 VRSK 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 119 | TIMING | HIGH | 6.0 | Gilbert Cisneros | VICI | Gilbert Cisneros 交易 VICI 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 120 | TIMING | HIGH | 6.0 | Gilbert Cisneros | ZTS | Gilbert Cisneros 交易 ZTS 延遲 70 天才申報（超過 60 天門檻，交易日=2025-12-19，申報日=2026-02-27） |
| 121 | REVERSAL | MEDIUM | 6.0 | Gilbert Cisneros | TRGP | Gilbert Cisneros 買入 TRGP (2025-12-10) 後僅 30 天賣出 (2026-01-09)，買入金額 $1,001 - $15,0... |
| 122 | REVERSAL | MEDIUM | 6.0 | Gilbert Cisneros | BKR | Gilbert Cisneros 買入 BKR (2025-12-19) 後僅 21 天賣出 (2026-01-09)，買入金額 $1,001 - $15,00... |
| 123 | REVERSAL | MEDIUM | 6.0 | Gilbert Cisneros | CAG | Gilbert Cisneros 買入 CAG (2025-12-19) 後僅 21 天賣出 (2026-01-09)，買入金額 $1,001 - $15,00... |
| 124 | REVERSAL | MEDIUM | 6.0 | Gilbert Cisneros | VRSK | Gilbert Cisneros 買入 VRSK (2025-12-19) 後僅 21 天賣出 (2026-01-09)，買入金額 $1,001 - $15,0... |
| 125 | TIMING | HIGH | 5.7 | Sheri Biggs | GS | Sheri Biggs 交易 GS 延遲 67 天才申報（超過 60 天門檻，交易日=2025-12-22，申報日=2026-02-27） |
| 126 | SIZE | HIGH | 5.6 | David H McCormick | GS | David H McCormick 交易 GS 金額 $1,000,001 - $5,000,000（估值 $3,000,000），遠高於個人平均 $555,5... |
| 127 | TIMING | HIGH | 5.6 | Donald Sternoff Jr.  | N/A | Donald Sternoff Jr. Beyer 交易 Virginia ST 4.00% 8/1/38 延遲 66 天才申報（超過 60 天門檻，交易日=2... |
| 128 | TIMING | HIGH | 5.5 | Gilbert Cisneros | AMZN | Gilbert Cisneros 交易 AMZN 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 129 | TIMING | HIGH | 5.5 | Gilbert Cisneros | ANET | Gilbert Cisneros 交易 ANET 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 130 | TIMING | HIGH | 5.5 | Gilbert Cisneros | AZO | Gilbert Cisneros 交易 AZO 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 131 | TIMING | HIGH | 5.5 | Gilbert Cisneros | BRK.B | Gilbert Cisneros 交易 BRK.B 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 132 | TIMING | HIGH | 5.5 | Gilbert Cisneros | BE | Gilbert Cisneros 交易 BE 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 133 | TIMING | HIGH | 5.5 | Gilbert Cisneros | BSX | Gilbert Cisneros 交易 BSX 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 134 | TIMING | HIGH | 5.5 | Gilbert Cisneros | CCJ | Gilbert Cisneros 交易 CCJ 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 135 | TIMING | HIGH | 5.5 | Gilbert Cisneros | SCHW | Gilbert Cisneros 交易 SCHW 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 136 | TIMING | HIGH | 5.5 | Gilbert Cisneros | CVX | Gilbert Cisneros 交易 CVX 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 137 | TIMING | HIGH | 5.5 | Gilbert Cisneros | NET | Gilbert Cisneros 交易 NET 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 138 | TIMING | HIGH | 5.5 | Gilbert Cisneros | COIN | Gilbert Cisneros 交易 COIN 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 139 | TIMING | HIGH | 5.5 | Gilbert Cisneros | COST | Gilbert Cisneros 交易 COST 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 140 | TIMING | HIGH | 5.5 | Gilbert Cisneros | ETN | Gilbert Cisneros 交易 ETN 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 141 | TIMING | HIGH | 5.5 | Gilbert Cisneros | HD | Gilbert Cisneros 交易 HD 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 142 | TIMING | HIGH | 5.5 | Gilbert Cisneros | MELI | Gilbert Cisneros 交易 MELI 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 143 | TIMING | HIGH | 5.5 | Gilbert Cisneros | META | Gilbert Cisneros 交易 META 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 144 | TIMING | HIGH | 5.5 | Gilbert Cisneros | NVDA | Gilbert Cisneros 交易 NVDA 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 145 | TIMING | HIGH | 5.5 | Gilbert Cisneros | ORCL | Gilbert Cisneros 交易 ORCL 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 146 | TIMING | HIGH | 5.5 | Gilbert Cisneros | PG | Gilbert Cisneros 交易 PG 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 147 | TIMING | HIGH | 5.5 | Gilbert Cisneros | PWR | Gilbert Cisneros 交易 PWR 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 148 | TIMING | HIGH | 5.5 | Gilbert Cisneros | HOOD | Gilbert Cisneros 交易 HOOD 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 149 | TIMING | HIGH | 5.5 | Gilbert Cisneros | RBLX | Gilbert Cisneros 交易 RBLX 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 150 | TIMING | HIGH | 5.5 | Gilbert Cisneros | SPOT | Gilbert Cisneros 交易 SPOT 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 151 | TIMING | HIGH | 5.5 | Gilbert Cisneros | TSM | Gilbert Cisneros 交易 TSM 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 152 | TIMING | HIGH | 5.5 | Gilbert Cisneros | TDG | Gilbert Cisneros 交易 TDG 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 153 | TIMING | HIGH | 5.5 | Gilbert Cisneros | VRT | Gilbert Cisneros 交易 VRT 延遲 65 天才申報（超過 60 天門檻，交易日=2025-12-24，申報日=2026-02-27） |
| 154 | SIZE | HIGH | 5.5 | Sheri Biggs | HN | Sheri Biggs 交易 HN 金額 $250,001 - $500,000（估值 $375,000），遠高於個人平均 $66,389，z-score=2.... |
| 155 | SIZE | HIGH | 5.4 | Gilbert Cisneros | N/A | Gilbert Cisneros 交易 California State Dept. of Water Resources CVP Revenue Bonds ... |
| 156 | SIZE | HIGH | 5.4 | Gilbert Cisneros | N/A | Gilbert Cisneros 交易 San Rafael, CA Elementary School District GO Bonds 金額 $100,0... |
| 157 | SIZE | HIGH | 5.4 | Gilbert Cisneros | N/A | Gilbert Cisneros 交易 Milwaukee, Wisconsin GO Promissory Notes Series N2 金額 $100,0... |
| 158 | TIMING | HIGH | 5.4 | Richard W. Allen | NFLX | Richard W. Allen 交易 NFLX 延遲 64 天才申報（超過 60 天門檻，交易日=2025-12-12，申報日=2026-02-14） |
| 159 | TIMING | HIGH | 5.3 | Sheri Biggs | HN | Sheri Biggs 交易 HN 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27） |
| 160 | TIMING | HIGH | 5.3 | Sheri Biggs | HN | Sheri Biggs 交易 HN 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27） |
| 161 | TIMING | HIGH | 5.3 | Gilbert Cisneros | AJINF | Gilbert Cisneros 交易 AJINF 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27） |
| 162 | TIMING | HIGH | 5.3 | Gilbert Cisneros | MHIYF | Gilbert Cisneros 交易 MHIYF 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27） |
| 163 | TIMING | HIGH | 5.3 | Gilbert Cisneros | NTDOF | Gilbert Cisneros 交易 NTDOF 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27） |
| 164 | TIMING | HIGH | 5.3 | Steve Cohen | SONY | Steve Cohen 交易 SONY 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-27） |
| 165 | TIMING | HIGH | 5.3 | Michael A. Jr. Colli | N/A | Michael A. Jr. Collins 交易 usdc 延遲 63 天才申報（超過 60 天門檻，交易日=2025-12-26，申報日=2026-02-2... |
| 166 | SIZE | HIGH | 4.7 | Richard Blumenthal | N/A | Richard Blumenthal 交易 KIRKOSWALD GLOBAL MACRO FUND LP 金額 $50,001 - $100,000（估值 $... |
| 167 | SIZE | HIGH | 4.2 | Steve Cohen | MS | Steve Cohen 交易 MS 金額 $50,001 - $100,000（估值 $75,000），遠高於個人平均 $31,571，z-score=2.10 |
| 168 | SIZE | HIGH | 4.2 | Richard W. Allen | N/A | Richard W. Allen 交易 US Treasury Note 3.2% DUE 01/31/28 金額 $100,001 - $250,000（估值... |

---

*報告由 AnomalyDetector 自動生成 — 2026-02-27*