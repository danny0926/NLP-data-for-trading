"""
Social Media NLP Pipeline
雙層情緒分析：FinTwitBERT (本地快速) → Gemini Flash (深度推理)

Stage 1: FinTwitBERT — 本地模型，免費，~100ms/post，處理 ~75% 的貼文
Stage 2: Gemini 2.5 Flash — API 深度推理，處理複雜/曖昧貼文
"""

import json
import logging
import os
import re
from typing import Optional, List, Dict

from google import genai

from src.config import GOOGLE_API_KEY, GEMINI_MODEL

logger = logging.getLogger("SocialNLP")

# ── 常數 ──

GEMINI_THRESHOLD = 0.75
MAX_RETRIES = 3

CASHTAG_RE = re.compile(r'\$([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b')
CRYPTO_TICKERS = {"BTC", "ETH", "DOGE", "SHIB", "SOL", "ADA", "XRP"}

SARCASM_PATTERNS = [
    re.compile(r'"[^"]{1,30}"'),                  # "air quotes"
    re.compile(r'/s\b'),                           # Reddit /s marker
    re.compile(r'[🙄😒🤦💀]'),                    # 諷刺 emoji
    re.compile(
        r'\b(sure|totally|obviously|clearly|great|wonderful)\b'
        r'.{0,50}'
        r'\b(bankrupt|crash|bubble|fraud|fail)\b',
        re.IGNORECASE,
    ),
]

# ── Stage 1: FinTwitBERT ──

_fintwit_pipeline = None
_fintwit_available = True  # False 表示 transformers 無法載入，永遠走 Gemini


def _get_fintwit_pipeline():
    """Lazy-load FinTwitBERT 模型（首次約 10 秒下載）。"""
    global _fintwit_pipeline, _fintwit_available
    if not _fintwit_available:
        return None
    if _fintwit_pipeline is not None:
        return _fintwit_pipeline

    try:
        from transformers import pipeline as hf_pipeline
        _fintwit_pipeline = hf_pipeline(
            "text-classification",
            model="StephanAkkerman/FinTwitBERT-sentiment",
            device=-1,  # CPU only
            truncation=True,
            max_length=512,
        )
        logger.info("FinTwitBERT 模型載入完成")
    except ImportError:
        logger.warning(
            "transformers / torch 未安裝，FinTwitBERT 不可用，"
            "所有貼文將路由至 Gemini 分析"
        )
        _fintwit_available = False
        _fintwit_pipeline = None
    except Exception as e:
        logger.warning(f"FinTwitBERT 載入失敗: {e}")
        _fintwit_available = False
        _fintwit_pipeline = None

    return _fintwit_pipeline


def fast_classify(text: str) -> Dict:
    """Stage 1: 本地 FinTwitBERT 快速分類。"""
    pipe = _get_fintwit_pipeline()
    if pipe is None:
        return {"label": "Neutral", "score": 0.0}

    result = pipe(text, truncation=True)[0]
    label_map = {
        "Bullish": "Bullish", "Bearish": "Bearish", "Neutral": "Neutral",
        "LABEL_0": "Bearish", "LABEL_1": "Neutral", "LABEL_2": "Bullish",
    }
    return {
        "label": label_map.get(result["label"], result["label"]),
        "score": result["score"],
    }


# ── Cashtag / Sarcasm 工具 ──


def extract_cashtags(text: str) -> List[str]:
    """從文字中萃取 $TICKER cashtag，排除加密貨幣。"""
    found = CASHTAG_RE.findall(text.upper())
    return [t for t in found if t not in CRYPTO_TICKERS]


def has_sarcasm_signal(text: str) -> bool:
    """偵測諷刺/反話信號。"""
    return any(p.search(text) for p in SARCASM_PATTERNS)


# ── Routing ──


def needs_deep_analysis(fast_result: Dict, text: str) -> bool:
    """判斷是否需要 Gemini 深度分析。"""
    # FinTwitBERT 不可用時，全部交給 Gemini
    if not _fintwit_available:
        return True
    if fast_result["score"] < GEMINI_THRESHOLD:
        return True
    if has_sarcasm_signal(text):
        return True
    # 無明確 ticker 且文字較長 → 需要 Gemini 做實體擷取
    if len(extract_cashtags(text)) == 0 and len(text) > 80:
        return True
    return False


# ── Stage 2: Gemini Prompts ──

SOCIAL_POLITICIAN_PROMPT = """你是美國政治-金融分析師，解讀國會議員社群發言對股市的影響。

## 分析對象
- 議員：{name}
- 委員會：{committees}
- 發言平台：{platform}
- 發言時間：{post_time}
- 原文：
{post_text}

## 分析步驟
1. 表面語義：字面意思是什麼？
2. 政策映射：涉及哪個產業/法規？（參考委員會職能）
3. 情緒校正：是否有諷刺或反話？
4. 市場影響：哪些上市公司受影響？方向？
5. 信號強度：根據委員會地位評估影響力

## 輸出（嚴格 JSON，不含 markdown）
{{"sentiment": "Bullish" | "Bearish" | "Neutral", "confidence": 0.0-1.0, "signal_type": "POLICY_SIGNAL" | "TRADE_SIGNAL" | "PERSONAL_OPINION", "sarcasm_detected": false, "tickers_explicit": [], "tickers_implied": [], "sector": "", "impact_score": 1-10, "reasoning": ""}}
"""

SOCIAL_KOL_PROMPT = """你是分析科技富豪和意見領袖社群發言的金融分析師。

## 分析對象
- 發言者：{name}
- 影響力：{influence_profile}
- 已知關聯 ticker：{key_tickers}
- 平台：{platform}
- 原文：
{post_text}

## KOL 解讀規則
1. 🚀/🌙 = 強烈看漲; 💀 = 看跌
2. "To the Moon" "HODL" = 看漲特定資產
3. "Something big coming" = 正面催化劑
4. 否認賣出 = 再確認看多
5. 攻擊競爭對手 = 對方 Bearish
{contrarian_note}

## 輸出（嚴格 JSON，不含 markdown）
{{"sentiment": "Bullish" | "Bearish" | "Neutral", "confidence": 0.0-1.0, "signal_type": "ENDORSEMENT" | "PRODUCT_HINT" | "ATTACK" | "MEME" | "POLICY_ALIGNMENT", "sarcasm_detected": false, "tickers_explicit": [], "tickers_implied": [], "sector": "", "impact_score": 1-10, "reasoning": ""}}
"""

CRAMER_CONTRARIAN_NOTE = """
⚠️ 此人物為已知反向指標。Inverse Cramer 效應：推薦後 30 天平均 -5%。
sentiment 應反轉：他推薦 = Bearish，他看壞 = Bullish。
"""


# ── Gemini Client ──


class _GeminiClient:
    """Lazy-init Gemini client，重複使用同一實例。"""

    def __init__(self):
        self._client = None  # type: Optional[genai.Client]

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            api_key = GOOGLE_API_KEY or os.getenv("GOOGLE_API_KEY", "")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY 環境變數未設定")
            self._client = genai.Client(api_key=api_key)
        return self._client


_gemini = _GeminiClient()


def _extract_json(text: str) -> Optional[dict]:
    """從 LLM 輸出中萃取 JSON（沿用 discovery_engine_v4 邏輯）。"""
    if not text:
        return None
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    json_match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            try:
                cleaned = re.sub(r',\s*([\]}])', r'\1', json_match.group(0))
                return json.loads(cleaned)
            except json.JSONDecodeError:
                return None
    return None


def _call_gemini(prompt: str, model: Optional[str] = None) -> str:
    """呼叫 Gemini API，回傳原始文字。"""
    model = model or GEMINI_MODEL
    try:
        response = _gemini.client.models.generate_content(
            model=model,
            contents=prompt,
        )
        return response.text or ""
    except Exception as e:
        logger.error(f"Gemini API 錯誤: {e}")
        return ""


# ── Stage 2: Gemini 深度分析 ──


def _gemini_analyze(post: Dict, targets_config: Dict) -> Dict:
    """使用 Gemini 深度分析單篇貼文，回傳信號 dict。"""
    author = post["author_name"]
    author_type = post["author_type"]

    # 取得該作者的設定
    target_info = targets_config.get(author, {})

    if author_type == "politician":
        prompt = SOCIAL_POLITICIAN_PROMPT.format(
            name=author,
            committees=target_info.get("committees", "未知"),
            platform=post.get("platform", "unknown"),
            post_time=post.get("post_time", ""),
            post_text=post["post_text"],
        )
    else:
        # KOL / influencer
        # Jim Cramer 反向指標
        is_cramer = "cramer" in author.lower()
        contrarian_note = CRAMER_CONTRARIAN_NOTE if is_cramer else ""

        prompt = SOCIAL_KOL_PROMPT.format(
            name=author,
            influence_profile=target_info.get("influence_profile", "科技/金融意見領袖"),
            key_tickers=json.dumps(target_info.get("key_tickers", [])),
            platform=post.get("platform", "unknown"),
            post_text=post["post_text"],
            contrarian_note=contrarian_note,
        )

    # 呼叫 Gemini（含重試）
    result_dict = None
    for attempt in range(MAX_RETRIES):
        raw_output = _call_gemini(prompt)
        result_dict = _extract_json(raw_output)
        if result_dict and isinstance(result_dict, dict):
            break
        logger.warning(f"Gemini JSON 解析失敗 (attempt {attempt + 1}/{MAX_RETRIES})")
        prompt += "\n\n[重要] 上次輸出無法解析為 JSON，請嚴格輸出純 JSON 格式。"

    if not result_dict or not isinstance(result_dict, dict):
        logger.error(f"Gemini 分析失敗: {author} — 回傳預設值")
        return {
            "sentiment": "Neutral",
            "sentiment_score": 0.0,
            "signal_type": "UNKNOWN",
            "sarcasm_detected": 0,
            "tickers_explicit": "[]",
            "tickers_implied": "[]",
            "sector": "",
            "impact_score": 1.0,
            "reasoning": "Gemini 分析失敗，無法解析回應",
        }

    # 正規化為 social_signals 表格式
    return {
        "sentiment": result_dict.get("sentiment", "Neutral"),
        "sentiment_score": result_dict.get("confidence", 0.0),
        "signal_type": result_dict.get("signal_type", "UNKNOWN"),
        "sarcasm_detected": 1 if result_dict.get("sarcasm_detected") else 0,
        "tickers_explicit": json.dumps(result_dict.get("tickers_explicit", [])),
        "tickers_implied": json.dumps(result_dict.get("tickers_implied", [])),
        "sector": result_dict.get("sector", ""),
        "impact_score": result_dict.get("impact_score", 5.0),
        "reasoning": result_dict.get("reasoning", ""),
    }


# ── 主入口 ──


def analyze_posts(posts: List[Dict], targets_config: Dict) -> List[Dict]:
    """
    批次分析社群貼文。

    Args:
        posts: 貼文列表，每筆需包含 post_text, author_name, author_type, platform 等欄位
        targets_config: 目標人物設定 dict（key=人名，value=設定如 committees, key_tickers 等）

    Returns:
        信號列表，每筆對應 social_signals 表的一列
    """
    signals = []
    gemini_count = 0
    fintwit_count = 0

    for post in posts:
        text = post.get("post_text", "")
        if not text.strip():
            continue

        # Stage 1: 快速分類
        fast_result = fast_classify(text)

        # Stage 2 路由判斷
        if needs_deep_analysis(fast_result, text):
            signal = _gemini_analyze(post, targets_config)
            signal["analysis_model"] = "gemini_flash"
            gemini_count += 1
        else:
            # Stage 1 結果直接輸出
            signal = {
                "sentiment": fast_result["label"],
                "sentiment_score": fast_result["score"],
                "signal_type": "UNKNOWN",
                "sarcasm_detected": 0,
                "tickers_explicit": json.dumps(extract_cashtags(text)),
                "tickers_implied": "[]",
                "sector": "",
                "impact_score": 5.0,
                "reasoning": f"FinTwitBERT classification (confidence: {fast_result['score']:.2f})",
                "analysis_model": "fintwit_bert",
            }
            fintwit_count += 1

        # 附加貼文 metadata
        signal["post_id"] = post.get("db_id")
        signal["author_name"] = post["author_name"]
        signal["author_type"] = post["author_type"]
        signal["platform"] = post.get("platform", "unknown")

        signals.append(signal)

    logger.info(
        f"分析完成: {len(signals)} 篇 "
        f"(FinTwitBERT: {fintwit_count}, Gemini: {gemini_count})"
    )
    return signals
