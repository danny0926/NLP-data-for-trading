"""
Extract 層 — Social Media Fetcher
統一社群媒體抓取：Twitter/X (Apify) + Truth Social (Apify) + Reddit (PRAW)。

支援三個平台的批次抓取，正規化為統一格式後寫入 social_posts 表。
缺少 API 憑證時優雅降級（跳過該平台，不會崩潰）。
"""

import hashlib
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.config import DB_PATH
from src.social_targets import (
    POLITICIAN_SOCIAL_TARGETS,
    KOL_SOCIAL_TARGETS,
    get_all_twitter_handles,
    get_all_truth_social_handles,
)

logger = logging.getLogger("ETL.SocialFetcher")

# ── Apify Actor IDs ──
# Twitter/X 搜尋 actor（依使用者搜尋關鍵字抓取推文）
TWITTER_ACTOR_ID = "apify/twitter-scraper"
# Truth Social scraper（搜尋帳號貼文）
TRUTH_SOCIAL_ACTOR_ID = "trudax/truth-social-scraper"

# ── Reddit 預設監控子版 ──
DEFAULT_SUBREDDITS = ["wallstreetbets", "stocks", "investing", "options"]


class SocialFetcher:
    """統一社群媒體抓取器 — Apify (Twitter/Truth Social) + PRAW (Reddit)"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH

        # ── Apify 初始化 ──
        self._apify_client = None
        apify_token = os.getenv("APIFY_API_TOKEN", "")
        if apify_token:
            try:
                from apify_client import ApifyClient
                self._apify_client = ApifyClient(token=apify_token)
                logger.info("Apify client 初始化成功")
            except ImportError:
                logger.warning("apify-client 未安裝，跳過 Twitter/Truth Social 抓取")
            except Exception as e:
                logger.warning(f"Apify client 初始化失敗: {e}")
        else:
            logger.warning("APIFY_API_TOKEN 未設定，跳過 Twitter/Truth Social 抓取")

        # ── PRAW (Reddit) 初始化 ──
        self._reddit = None
        reddit_id = os.getenv("REDDIT_CLIENT_ID", "")
        reddit_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        if reddit_id and reddit_secret:
            try:
                import praw
                self._reddit = praw.Reddit(
                    client_id=reddit_id,
                    client_secret=reddit_secret,
                    user_agent=os.getenv(
                        "REDDIT_USER_AGENT", "PoliticalAlphaMonitor/1.0"
                    ),
                )
                logger.info("Reddit PRAW 初始化成功")
            except ImportError:
                logger.warning("praw 未安裝，跳過 Reddit 抓取")
            except Exception as e:
                logger.warning(f"Reddit PRAW 初始化失敗: {e}")
        else:
            logger.warning("REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET 未設定，跳過 Reddit 抓取")

    # ================================================================
    # 公開介面
    # ================================================================

    def fetch_all_targets(
        self,
        hours: int = 24,
        dry_run: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        抓取所有平台、所有追蹤目標的貼文。

        Args:
            hours: 回溯時間窗口（小時）
            dry_run: True 時只抓取不寫入 DB

        Returns:
            正規化後的貼文列表
        """
        all_posts: List[Dict[str, Any]] = []

        # ── Twitter/X ──
        twitter_handles = get_all_twitter_handles()
        if twitter_handles and self._apify_client:
            logger.info(f"開始抓取 Twitter/X ({len(twitter_handles)} 個帳號)...")
            twitter_posts = self._fetch_twitter(twitter_handles, hours)
            all_posts.extend(twitter_posts)
            logger.info(f"Twitter/X 抓取完成: {len(twitter_posts)} 則貼文")
        else:
            logger.info("跳過 Twitter/X 抓取（無帳號或無 Apify client）")

        # ── Truth Social ──
        truth_handles = get_all_truth_social_handles()
        if truth_handles and self._apify_client:
            logger.info(f"開始抓取 Truth Social ({len(truth_handles)} 個帳號)...")
            truth_posts = self._fetch_truth_social(truth_handles, hours)
            all_posts.extend(truth_posts)
            logger.info(f"Truth Social 抓取完成: {len(truth_posts)} 則貼文")
        else:
            logger.info("跳過 Truth Social 抓取（無帳號或無 Apify client）")

        # ── Reddit ──
        reddit_config = self._build_reddit_config()
        if reddit_config and self._reddit:
            logger.info("開始抓取 Reddit...")
            reddit_posts = self._fetch_reddit(reddit_config, hours)
            all_posts.extend(reddit_posts)
            logger.info(f"Reddit 抓取完成: {len(reddit_posts)} 則貼文")
        else:
            logger.info("跳過 Reddit 抓取（無設定或無 PRAW client）")

        logger.info(f"全平台共抓取 {len(all_posts)} 則貼文")

        # ── 寫入 DB ──
        if not dry_run and all_posts:
            new_count = self._save_posts(all_posts)
            logger.info(f"新增 {new_count} 則貼文至 social_posts 表")
        elif dry_run:
            logger.info("[Dry Run] 跳過 DB 寫入")

        return all_posts

    def fetch_twitter_only(self, hours: int = 24, dry_run: bool = False) -> List[Dict[str, Any]]:
        """只抓取 Twitter/X 貼文。"""
        if not self._apify_client:
            logger.warning("Apify client 未初始化，無法抓取 Twitter")
            return []
        handles = get_all_twitter_handles()
        posts = self._fetch_twitter(handles, hours)
        if not dry_run and posts:
            self._save_posts(posts)
        return posts

    def fetch_truth_only(self, hours: int = 24, dry_run: bool = False) -> List[Dict[str, Any]]:
        """只抓取 Truth Social 貼文。"""
        if not self._apify_client:
            logger.warning("Apify client 未初始化，無法抓取 Truth Social")
            return []
        handles = get_all_truth_social_handles()
        posts = self._fetch_truth_social(handles, hours)
        if not dry_run and posts:
            self._save_posts(posts)
        return posts

    def fetch_reddit_only(self, hours: int = 24, dry_run: bool = False) -> List[Dict[str, Any]]:
        """只抓取 Reddit 貼文。"""
        if not self._reddit:
            logger.warning("PRAW client 未初始化，無法抓取 Reddit")
            return []
        config = self._build_reddit_config()
        posts = self._fetch_reddit(config, hours)
        if not dry_run and posts:
            self._save_posts(posts)
        return posts

    # ================================================================
    # Twitter/X (via Apify)
    # ================================================================

    def _fetch_twitter(self, handles: List[str], hours: int) -> List[Dict[str, Any]]:
        """
        透過 Apify Twitter scraper 抓取推文。

        使用 search query 格式 "from:handle" 來搜尋特定帳號的推文，
        再依時間窗口過濾。
        """
        posts: List[Dict[str, Any]] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # 將 handles 分批（避免單次搜尋過多）
        # 清理 handle 格式：移除 @
        clean_handles = [h.lstrip("@") for h in handles]
        search_terms = [f"from:{h}" for h in clean_handles]

        try:
            logger.info(f"呼叫 Apify Twitter scraper，搜尋 {len(search_terms)} 個帳號...")
            run = self._apify_client.actor(TWITTER_ACTOR_ID).call(
                run_input={
                    "searchTerms": search_terms,
                    "maxTweets": 50 * len(clean_handles),
                    "sort": "Latest",
                },
                timeout_secs=300,
            )

            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                logger.error("Apify run 未回傳 dataset ID")
                return posts

            for item in self._apify_client.dataset(dataset_id).iterate_items():
                # 時間過濾
                created_at = item.get("createdAt") or item.get("created_at") or ""
                post_time = self._parse_datetime(created_at)
                if post_time and post_time < cutoff:
                    continue

                author_handle = item.get("author", {}).get("userName", "") if isinstance(item.get("author"), dict) else ""
                if not author_handle:
                    author_handle = item.get("user", {}).get("screen_name", "") if isinstance(item.get("user"), dict) else ""

                author_name = item.get("author", {}).get("name", "") if isinstance(item.get("author"), dict) else ""
                if not author_name:
                    author_name = author_handle

                post = self._normalize_post(
                    raw={
                        "text": item.get("text") or item.get("full_text") or "",
                        "id": item.get("id") or item.get("id_str") or "",
                        "url": item.get("url") or "",
                        "created_at": created_at,
                        "likes": item.get("likeCount") or item.get("favorite_count") or 0,
                        "retweets": item.get("retweetCount") or item.get("retweet_count") or 0,
                        "replies": item.get("replyCount") or item.get("reply_count") or 0,
                        "author_name": author_name,
                        "author_handle": author_handle,
                    },
                    platform="twitter",
                    author_type=self._resolve_author_type(author_handle),
                )
                if post["post_text"]:
                    posts.append(post)

        except Exception as e:
            logger.error(f"Twitter 抓取失敗: {e}")

        return posts

    # ================================================================
    # Truth Social (via Apify)
    # ================================================================

    def _fetch_truth_social(self, handles: List[str], hours: int) -> List[Dict[str, Any]]:
        """
        透過 Apify Truth Social scraper 抓取貼文。
        Truth Social 帳號較少（目前主要是 Trump），逐帳號抓取。
        """
        posts: List[Dict[str, Any]] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        for handle in handles:
            clean_handle = handle.lstrip("@")
            logger.info(f"抓取 Truth Social: {clean_handle}")

            try:
                run = self._apify_client.actor(TRUTH_SOCIAL_ACTOR_ID).call(
                    run_input={
                        "username": clean_handle,
                        "maxPosts": 50,
                    },
                    timeout_secs=180,
                )

                dataset_id = run.get("defaultDatasetId")
                if not dataset_id:
                    logger.warning(f"Truth Social run 未回傳 dataset ({clean_handle})")
                    continue

                for item in self._apify_client.dataset(dataset_id).iterate_items():
                    created_at = item.get("created_at") or item.get("createdAt") or ""
                    post_time = self._parse_datetime(created_at)
                    if post_time and post_time < cutoff:
                        continue

                    post = self._normalize_post(
                        raw={
                            "text": item.get("content") or item.get("text") or "",
                            "id": str(item.get("id", "")),
                            "url": item.get("url") or item.get("uri") or "",
                            "created_at": created_at,
                            "likes": item.get("favourites_count") or item.get("likes") or 0,
                            "retweets": item.get("reblogs_count") or item.get("reblogs") or 0,
                            "replies": item.get("replies_count") or item.get("replies") or 0,
                            "author_name": item.get("account", {}).get("display_name", clean_handle) if isinstance(item.get("account"), dict) else clean_handle,
                            "author_handle": clean_handle,
                        },
                        platform="truth_social",
                        author_type=self._resolve_author_type(clean_handle),
                    )
                    if post["post_text"]:
                        posts.append(post)

            except Exception as e:
                logger.error(f"Truth Social 抓取失敗 ({clean_handle}): {e}")

            # 平台間短暫延遲
            time.sleep(1)

        return posts

    # ================================================================
    # Reddit (via PRAW)
    # ================================================================

    def _fetch_reddit(self, config: Dict[str, Any], hours: int) -> List[Dict[str, Any]]:
        """
        透過 PRAW 抓取 Reddit 貼文。
        兩種模式：
        1. 追蹤特定使用者（如 DeepFuckingValue）
        2. 監控特定 subreddit 的熱門貼文
        """
        posts: List[Dict[str, Any]] = []
        cutoff_ts = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()

        # ── 追蹤特定使用者 ──
        for user_info in config.get("users", []):
            username = user_info["username"]
            author_name = user_info.get("display_name", username)
            author_type = user_info.get("author_type", "kol")

            logger.info(f"抓取 Reddit 使用者: u/{username}")
            try:
                redditor = self._reddit.redditor(username)
                for submission in redditor.submissions.new(limit=20):
                    if submission.created_utc < cutoff_ts:
                        continue

                    post = self._normalize_post(
                        raw={
                            "text": f"{submission.title}\n\n{submission.selftext}" if submission.selftext else submission.title,
                            "id": submission.id,
                            "url": f"https://www.reddit.com{submission.permalink}",
                            "created_at": datetime.fromtimestamp(
                                submission.created_utc, tz=timezone.utc
                            ).isoformat(),
                            "likes": submission.score,
                            "retweets": 0,
                            "replies": submission.num_comments,
                            "author_name": author_name,
                            "author_handle": f"u/{username}",
                        },
                        platform="reddit",
                        author_type=author_type,
                    )
                    if post["post_text"]:
                        posts.append(post)

                # 也抓取留言
                for comment in redditor.comments.new(limit=20):
                    if comment.created_utc < cutoff_ts:
                        continue

                    post = self._normalize_post(
                        raw={
                            "text": comment.body,
                            "id": comment.id,
                            "url": f"https://www.reddit.com{comment.permalink}",
                            "created_at": datetime.fromtimestamp(
                                comment.created_utc, tz=timezone.utc
                            ).isoformat(),
                            "likes": comment.score,
                            "retweets": 0,
                            "replies": 0,
                            "author_name": author_name,
                            "author_handle": f"u/{username}",
                        },
                        platform="reddit",
                        author_type=author_type,
                    )
                    if post["post_text"]:
                        posts.append(post)

            except Exception as e:
                logger.error(f"Reddit 使用者抓取失敗 (u/{username}): {e}")

        # ── 監控 subreddit 熱門貼文 ──
        for sub_name in config.get("subreddits", []):
            logger.info(f"抓取 Reddit subreddit: r/{sub_name}")
            try:
                subreddit = self._reddit.subreddit(sub_name)
                for submission in subreddit.hot(limit=25):
                    if submission.created_utc < cutoff_ts:
                        continue
                    # 跳過 stickied 貼文（通常是版規）
                    if submission.stickied:
                        continue

                    author_name_raw = str(submission.author) if submission.author else "[deleted]"
                    post = self._normalize_post(
                        raw={
                            "text": f"{submission.title}\n\n{submission.selftext}" if submission.selftext else submission.title,
                            "id": submission.id,
                            "url": f"https://www.reddit.com{submission.permalink}",
                            "created_at": datetime.fromtimestamp(
                                submission.created_utc, tz=timezone.utc
                            ).isoformat(),
                            "likes": submission.score,
                            "retweets": 0,
                            "replies": submission.num_comments,
                            "author_name": author_name_raw,
                            "author_handle": f"u/{author_name_raw}",
                        },
                        platform="reddit",
                        author_type="community",
                    )
                    if post["post_text"]:
                        posts.append(post)

            except Exception as e:
                logger.error(f"Reddit subreddit 抓取失敗 (r/{sub_name}): {e}")

        return posts

    # ================================================================
    # 正規化
    # ================================================================

    def _normalize_post(
        self, raw: Dict[str, Any], platform: str, author_type: str
    ) -> Dict[str, Any]:
        """
        將各平台原始資料正規化為統一格式。

        Returns:
            統一格式 dict，對應 social_posts 表欄位
        """
        post_text = (raw.get("text") or "").strip()
        # 截斷過長文字（保留前 5000 字元）
        if len(post_text) > 5000:
            post_text = post_text[:5000] + "..."

        author_handle = (raw.get("author_handle") or "").strip()
        author_name = (raw.get("author_name") or author_handle).strip()

        # 產生去重 hash
        data_hash = self._generate_hash(
            platform,
            author_handle,
            post_text[:200],
            raw.get("created_at", ""),
        )

        return {
            "platform": platform,
            "author_name": author_name,
            "author_handle": author_handle,
            "author_type": author_type,
            "post_id": str(raw.get("id", "")),
            "post_text": post_text,
            "post_url": raw.get("url", ""),
            "post_time": raw.get("created_at", ""),
            "likes": int(raw.get("likes", 0) or 0),
            "retweets": int(raw.get("retweets", 0) or 0),
            "replies": int(raw.get("replies", 0) or 0),
            "media_type": raw.get("media_type"),
            "data_hash": data_hash,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    # ================================================================
    # DB 寫入
    # ================================================================

    def _save_posts(self, posts: List[Dict[str, Any]]) -> int:
        """
        寫入 social_posts 表，SHA256 去重。

        Returns:
            新增的貼文數量
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        new_count = 0

        for post in posts:
            try:
                cursor.execute(
                    """
                    INSERT INTO social_posts (
                        platform, author_name, author_handle, author_type,
                        post_id, post_text, post_url, post_time,
                        likes, retweets, replies, media_type,
                        data_hash, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        post["platform"],
                        post["author_name"],
                        post["author_handle"],
                        post["author_type"],
                        post["post_id"],
                        post["post_text"],
                        post["post_url"],
                        post["post_time"],
                        post["likes"],
                        post["retweets"],
                        post["replies"],
                        post["media_type"],
                        post["data_hash"],
                        post["fetched_at"],
                    ),
                )
                new_count += 1
            except sqlite3.IntegrityError:
                # data_hash 重複，跳過
                pass

        conn.commit()
        conn.close()
        return new_count

    # ================================================================
    # 輔助方法
    # ================================================================

    def _build_reddit_config(self) -> Dict[str, Any]:
        """
        從追蹤清單建立 Reddit 抓取設定。
        回傳 {users: [...], subreddits: [...]}
        """
        users = []
        for kol in KOL_SOCIAL_TARGETS:
            reddit_handle = kol.get("platforms", {}).get("reddit", "")
            if reddit_handle:
                # 格式: "u/DeepFuckingValue" → "DeepFuckingValue"
                username = reddit_handle.replace("u/", "").strip()
                users.append({
                    "username": username,
                    "display_name": kol["name"],
                    "author_type": "kol",
                })

        return {
            "users": users,
            "subreddits": DEFAULT_SUBREDDITS,
        }

    def _resolve_author_type(self, handle: str) -> str:
        """
        根據帳號判斷作者類型：politician / kol / unknown。
        """
        handle_lower = handle.lower().lstrip("@")

        # 檢查是否為議員
        for p in POLITICIAN_SOCIAL_TARGETS:
            p_handle = (p.get("twitter") or "").lower().lstrip("@")
            if p_handle and p_handle == handle_lower:
                return "politician"

        # 檢查是否為 KOL
        for k in KOL_SOCIAL_TARGETS:
            for platform_handle in k.get("platforms", {}).values():
                if platform_handle:
                    clean = platform_handle.lower().lstrip("@").replace("u/", "")
                    if clean == handle_lower:
                        return "kol"

        return "unknown"

    @staticmethod
    def _generate_hash(*fields: str) -> str:
        """SHA256 去重 hash。"""
        data_str = "|".join(str(f) for f in fields)
        return hashlib.sha256(data_str.encode()).hexdigest()

    @staticmethod
    def _parse_datetime(dt_str: str) -> Optional[datetime]:
        """
        嘗試解析各種日期時間格式。
        回傳 UTC datetime 或 None。
        """
        if not dt_str:
            return None

        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%a %b %d %H:%M:%S %z %Y",  # Twitter 格式
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(dt_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        # 最後嘗試 ISO 格式
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt
        except (ValueError, AttributeError):
            return None
