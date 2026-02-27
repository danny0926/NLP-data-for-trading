import time
import argparse
from src.discovery_engine_v4 import DiscoveryEngineV4
from src.targets import CONGRESS_TARGETS, get_targets_by_tier, summary


def run_congress_monitoring(tiers=None, delay=5, model_name="gemini-2.5-flash"):
    """執行國會議員情報監控任務。

    Args:
        tiers: 要執行的 Tier 清單，例如 [1], [1,2], [1,2,3]。
               預設為 [1, 2]（Tier 1 + Tier 2）。
        delay: 每位議員之間的等待秒數（避免 API rate limit）。
        model_name: Gemini 模型名稱。
    """
    if tiers is None:
        tiers = [1, 2]

    engine = DiscoveryEngineV4(model_name=model_name)

    print(f"=== 啟動國會議員情報監控任務 ({model_name}) ===")
    print(f"追蹤清單概覽:\n{summary()}")
    print(f"本次執行 Tier: {tiers}")
    print("=" * 60)

    total_processed = 0
    total_errors = 0

    for tier in sorted(tiers):
        targets = get_targets_by_tier(tier)
        print(f"\n--- Tier {tier}: {len(targets)} 位議員 ---")

        for i, target in enumerate(targets):
            label = (
                f"[Tier {target['tier']}] "
                f"{target['name']} ({target['party']}-{target['state']}, "
                f"{target['chamber']})"
            )
            print(f"\n{label}")
            print(f"  備註: {target['note']}")

            try:
                engine.monitor_target("CONGRESS", target["name"])
                total_processed += 1
            except Exception as e:
                print(f"[!] 處理 {target['name']} 時發生錯誤: {e}")
                total_errors += 1

            # 最後一位不需要等待
            if not (tier == sorted(tiers)[-1] and i == len(targets) - 1):
                time.sleep(delay)

    print("\n" + "=" * 60)
    print(
        f"[完成] 成功處理 {total_processed} 位議員，"
        f"錯誤 {total_errors} 位。"
    )


def main():
    parser = argparse.ArgumentParser(
        description="國會議員情報監控 — Political Alpha Monitor"
    )
    parser.add_argument(
        "--tier",
        type=int,
        nargs="+",
        default=[1, 2],
        choices=[1, 2, 3],
        help="要執行的 Tier (預設: 1 2)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="執行所有 Tier (1+2+3)",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=5,
        help="每位議員之間等待秒數 (預設: 5)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-flash",
        help="Gemini 模型名稱 (預設: gemini-2.5-flash)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="僅列出追蹤清單，不執行監控",
    )

    args = parser.parse_args()

    if args.list:
        print("=== 國會議員追蹤清單 ===\n")
        for tier in (1, 2, 3):
            targets = get_targets_by_tier(tier)
            print(f"── Tier {tier} ({len(targets)} 人) ──")
            for t in targets:
                print(
                    f"  {t['name']:30s} {t['chamber']:6s} "
                    f"{t['party']}-{t['state']:2s}  {t['note']}"
                )
            print()
        print(summary())
        return

    tiers = [1, 2, 3] if args.all else args.tier
    run_congress_monitoring(
        tiers=tiers,
        delay=args.delay,
        model_name=args.model,
    )


if __name__ == "__main__":
    main()
