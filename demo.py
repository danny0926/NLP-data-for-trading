"""
Political Alpha Monitor — One-Click Demo Launcher

Usage:
    python demo.py              # Launch Streamlit dashboard
    python demo.py --static     # Open static HTML dashboard
    python demo.py --refresh    # Refresh social data + regenerate dashboard, then launch
"""

import argparse
import os
import subprocess
import sys
import time
import webbrowser

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def check_dependencies():
    """Quick check that required packages exist."""
    missing = []
    for pkg in ["streamlit", "plotly", "pandas"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[!] Missing packages: {', '.join(missing)}")
        print(f"    Run: pip install -r requirements_dashboard.txt")
        return False
    return True


def refresh_data():
    """Fetch fresh social data and regenerate dashboard."""
    print("\n[1/3] Fetching latest social media posts...")
    subprocess.run(
        [sys.executable, "run_social_analysis.py", "--hours", "72"],
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    print("\n[2/3] Regenerating static dashboard...")
    subprocess.run(
        [sys.executable, "generate_dashboard.py"],
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    print("\n[3/3] Data refresh complete.\n")


def launch_streamlit():
    """Launch Streamlit dashboard and open browser."""
    print("=" * 60)
    print("  Political Alpha Monitor")
    print("  Congressional Trading Intelligence System")
    print("=" * 60)
    print()
    print("  Starting interactive dashboard...")
    print("  Browser will open automatically.")
    print("  Press Ctrl+C to stop.")
    print()

    subprocess.run(
        [
            sys.executable, "-m", "streamlit", "run",
            "streamlit_app.py",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--theme.base", "dark",
            "--theme.primaryColor", "#38bdf8",
            "--theme.backgroundColor", "#0f172a",
            "--theme.secondaryBackgroundColor", "#1e293b",
            "--theme.textColor", "#e2e8f0",
        ],
        cwd=PROJECT_ROOT,
    )


def open_static():
    """Open the static HTML dashboard in browser."""
    html_path = os.path.join(PROJECT_ROOT, "docs", "reports", "dashboard.html")
    if not os.path.exists(html_path):
        print("[!] Static dashboard not found. Generating...")
        subprocess.run(
            [sys.executable, "generate_dashboard.py"],
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

    print(f"Opening: {html_path}")
    webbrowser.open(f"file:///{html_path.replace(os.sep, '/')}")


def main():
    parser = argparse.ArgumentParser(
        description="Political Alpha Monitor - Demo Launcher"
    )
    parser.add_argument(
        "--static", action="store_true",
        help="Open static HTML dashboard instead of Streamlit",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Refresh social data and regenerate dashboard before launching",
    )
    args = parser.parse_args()

    if not check_dependencies():
        sys.exit(1)

    if args.refresh:
        refresh_data()

    if args.static:
        open_static()
    else:
        launch_streamlit()


if __name__ == "__main__":
    main()
