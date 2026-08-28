"""
EU関連ニュースをRSS(ニュースサイトの自動配信形式)から取得するスクリプト

【重要】このスクリプトはネットワーク接続が必要です。
このClaude.aiのチャット環境(サンドボックス)ではネットワークが無効化されているため実行できません。
Claude Code環境(ローカルPC)で実行してください。

必要ライブラリ:
    pip install feedparser requests pandas

【用語の説明】
- RSS: ニュースサイトが「新着記事」を自動で配信するための共通フォーマットです。
  多くの新聞社・機関が無料で提供しています(会員登録は不要です)。
- feedparser: RSSの中身を、Pythonで扱いやすい形に変換してくれるライブラリです。
"""

import feedparser
import pandas as pd
from pathlib import Path
from datetime import datetime

# --- 設定 ---
# EUに関連する主要なニュース源のRSSフィード一覧
# 用途に応じて自由に追加・削除してください
RSS_FEEDS = {
    "ECB(欧州中央銀行)": "https://www.ecb.europa.eu/rss/press.xml",
    "European Commission(欧州委員会)": "https://ec.europa.eu/commission/presscorner/api/rss?type=IP",
    # Eufeeds.com は27カ国分の新聞社を横断的にまとめているアグリゲーターです。
    # 個別の国のニュースが必要な場合は、Eufeeds.comのサイトで各国のフィードURLを確認してください。
}

OUTPUT_DIR = Path("data/news")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_feed(name: str, url: str) -> pd.DataFrame:
    """1つのRSSフィードを取得し、記事一覧をDataFrameにする"""
    print(f"取得中: {name} ...")
    feed = feedparser.parse(url)

    if feed.bozo:  # フィードの形式が壊れている/取得失敗の場合のフラグ
        print(f"  → 警告: フィードの解析に問題がある可能性があります ({name})")

    articles = []
    for entry in feed.entries:
        articles.append({
            "source": name,
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", entry.get("updated", "")),
            "summary": entry.get("summary", ""),
        })

    df = pd.DataFrame(articles)
    print(f"  → {len(df)}件の記事を取得")
    return df


def fetch_all_feeds():
    """定義済みの全RSSフィードを取得し、まとめて保存する"""
    today = datetime.now().strftime("%Y%m%d")
    all_articles = []

    for name, url in RSS_FEEDS.items():
        try:
            df = fetch_feed(name, url)
            all_articles.append(df)
        except Exception as e:
            print(f"  → 取得失敗 ({name}): {e}")

    if all_articles:
        combined = pd.concat(all_articles, ignore_index=True)
        output_path = OUTPUT_DIR / f"eu_news_{today}.csv"
        combined.to_csv(output_path, index=False, encoding="utf-8")
        print(f"\n合計 {len(combined)} 件の記事を保存しました: {output_path}")
        return combined
    else:
        print("記事を1件も取得できませんでした。")
        return pd.DataFrame()


if __name__ == "__main__":
    fetch_all_feeds()
