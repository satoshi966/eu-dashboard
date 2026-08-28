"""
EU関連ニュースと動画をRSS(自動配信形式)から取得するスクリプト (v2)

このスクリプトは2つのCSVを作ります。
    data/news/eu_news_YYYYMMDD.csv    … 記事一覧(画像URL付き)
    data/news/eu_videos_YYYYMMDD.csv  … 動画一覧(サムネイル画像付き)

v1 からの変更点:
    v1 は feedparser にURLを直接渡していたが、feedparser は内部で urllib を使うため
    Windows環境ではCA証明書ストアを参照できず SSL: CERTIFICATE_VERIFY_FAILED で
    全フィードが0件になっていた。
    v2 では requests(certifi同梱)でHTTP取得し、取得済みのバイト列を feedparser に渡す。

画像URLの取得について:
    記事に添えられている画像のURLも保存します。探す順番は次のとおりです。
      1. RSSの中に画像が入っていればそれを使う(追加の通信が不要で一番速い)
      2. 見つからなければ記事ページを開いて og:image などを読む
    画像が見つからない記事は、画像なし(空欄)のまま保存します。

    【実測メモ】ECB と 欧州委員会 は報道発表をテキストのみで配信しており、
    記事ごとの写真がありません。記事ページの og:image も全記事共通のロゴでした。
    そのため image_is_generic 列に True を立てて、内容と関係ない画像であることが
    分かるようにしています。
    写真が実際に取れる配信元(France24、Guardian、Le Monde など)を
    別途追加してあるので、ダッシュボードではそちらの画像が表示されます。

必要ライブラリ:
    pip install feedparser requests pandas

【用語の説明】
- RSS: ニュースサイトが「新着記事」を自動で配信するための共通フォーマットです。
  多くの新聞社・機関が無料で提供しています(会員登録は不要です)。
- feedparser: RSSの中身を、Pythonで扱いやすい形に変換してくれるライブラリです。
- og:image: Webページに埋め込まれている「この記事の代表画像はこれです」という情報。
  SNSでリンクを貼ったときに出るサムネイル画像がこれにあたります。
"""

import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import feedparser
import pandas as pd
import requests

from translate_util import translate_titles

# ==========================================================================
# 設定
# ==========================================================================

# --- 公式発表(テキスト中心。写真は付きません) ---
OFFICIAL_FEEDS = {
    "ECB(欧州中央銀行)": "https://www.ecb.europa.eu/rss/press.xml",
    "European Commission(欧州委員会)": "https://ec.europa.eu/commission/presscorner/api/rss?type=IP",
}

# --- 報道機関(写真付き) ---
# 実際にフィードを叩いて「記事ごとに違う画像が入っているか」を確認したものだけを
# 載せています。確認した結果は次のとおりでした。
#     France24 / Guardian / Le Monde / Der Spiegel / El Pais / NOS / RTBF … 画像100%
#     Euronews(RSS) / DW(RSS) / ANSA / Yle …………………………………… 画像0%(不採用)
#     Politico Europe ……………………………………………………………… 画像20%(不採用)
# Euronews と DW については、YouTube の公式チャンネル(下の設定)から
# サムネイル付きで取得しています。
NEWS_FEEDS = {
    "FRANCE 24": "https://www.france24.com/en/rss",
    "The Guardian (Europe)": "https://www.theguardian.com/world/europe-news/rss",
    "Le Monde": "https://www.lemonde.fr/rss/une.xml",
    "Der Spiegel (International)": "https://www.spiegel.de/international/index.rss",
    "El País": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    "NOS (オランダ)": "https://feeds.nos.nl/nosnieuwsalgemeen",
    "RTBF (ベルギー)": "https://rss.rtbf.be/article/rss/highlight_rtbfinfo_info.xml",
}

# --- YouTube公式チャンネル ---
# YouTubeは「チャンネルID」を指定すると、最新15本の動画をRSSで配信しています。
# APIキーは不要です。IDはチャンネルページの canonical リンクから調べました
# (@ハンドルから機械的に取ると、別チャンネルに解決されることがあるため)。
YOUTUBE_CHANNELS = {
    "euronews": "UCSrZ3UV4jOidv8ppoVuvW9Q",
    "FRANCE 24 English": "UCQfwfsi5VrQ8yKZ-UWmAEFg",
    "DW News": "UCknLrEdhRCp1aegoMqRaCZg",
}
YOUTUBE_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"

# RSS配信元によってはUser-Agentのないリクエストを弾くため明示する
HEADERS = {"User-Agent": "eu-dashboard-news-fetcher/2.0"}
TIMEOUT = 30

# 1つのフィードから取り込む記事数の上限。
# El País のように150件以上を配信するところがあるため、そろえておきます。
MAX_ITEMS_PER_FEED = 30

# RSSに画像が無かったとき、記事ページを開いて画像を探すかどうか。
# False にすると通信量が減りますが、公式発表の画像は取得できなくなります。
FETCH_ARTICLE_PAGE = True
# 記事ページを続けて開くときの間隔(秒)。相手のサーバーへの配慮です。
ARTICLE_INTERVAL = 0.5

# 画像URLに含まれていたら「記事の中身とは関係ない画像」とみなす語。
# ロゴ、アイコン、SNS用の既定画像などを本文の写真と区別するために使います。
GENERIC_HINTS = (
    "logo", "icon", "sprite", "spacer", "pixel", "avatar", "banner",
    "social-default", "placeholder", "place holder", "default",
)

# 画像ではなく動画ファイルを指しているURLを弾くための拡張子
VIDEO_EXTENSIONS = (".mp4", ".m3u8", ".webm", ".mov", ".avi")

OUTPUT_DIR = Path("data/news")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- HTMLから画像を探すための検索パターン ---
META_IMAGE = re.compile(
    r'<meta[^>]+(?:property|name)\s*=\s*["\'](?:og:image|twitter:image)["\'][^>]*>',
    re.I,
)
META_CONTENT = re.compile(r'content\s*=\s*["\']([^"\']+)["\']', re.I)
IMG_TAG = re.compile(r'<img[^>]+src\s*=\s*["\']([^"\']+)["\']', re.I)


# ==========================================================================
# 小さな道具
# ==========================================================================


def _published(entry) -> str:
    """配信日時を ISO 形式に揃える。パース済みの値があればそちらを優先する"""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime(*parsed[:6]).isoformat()
    return entry.get("published", entry.get("updated", ""))


def _looks_generic(url: str) -> bool:
    """ロゴや既定画像など、記事の内容と関係ない画像かどうかを判定する"""
    return any(hint in url.lower() for hint in GENERIC_HINTS)


def _is_video_file(url: str) -> bool:
    """動画ファイルを指すURLかどうか(El País は media:content に動画を入れてくる)"""
    head = url.lower().split("?")[0]
    return head.endswith(VIDEO_EXTENSIONS)


def _image_from_entry(entry) -> str:
    """
    RSSの記事データそのものから画像URLを探す。
    配信元によって画像の入れ方が違うので、よくある置き場所を順に見ていきます。
    追加の通信が発生しないので、まずここを探します。
    """
    # media:content / media:thumbnail という拡張タグ(ニュースサイトで一般的)
    for key in ("media_content", "media_thumbnail"):
        for item in entry.get(key, []) or []:
            url = item.get("url", "")
            if not url:
                continue
            # 動画が入っていることがあるので、画像だけを受け取ります
            medium = str(item.get("medium", "")).lower()
            mime = str(item.get("type", "")).lower()
            if medium == "video" or mime.startswith("video") or _is_video_file(url):
                continue
            return url

    # enclosure(添付ファイル)として画像が付いている場合
    for link in entry.get("links", []) or []:
        if str(link.get("type", "")).startswith("image") and link.get("href"):
            return link["href"]

    # 記事の要約や本文のHTMLに <img> が埋め込まれている場合
    html_parts = [entry.get("summary", "") or ""]
    for content in entry.get("content", []) or []:
        html_parts.append(content.get("value", "") or "")
    for html in html_parts:
        found = IMG_TAG.search(html)
        if found:
            return found.group(1)

    return ""


def _image_from_page(url: str) -> tuple[str, str]:
    """
    記事ページを開いて画像URLを探す。
    戻り値は (画像URL, どこで見つけたか) の組。見つからなければ ("", "")。
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        # 1記事の画像が取れなくても全体は続行したいので、ここでは黙って諦めます
        return "", ""

    html = response.text

    # 1) og:image / twitter:image(記事の代表画像)
    meta = META_IMAGE.search(html)
    if meta:
        content = META_CONTENT.search(meta.group(0))
        if content:
            # 相対URL("/img/a.jpg")を絶対URLに直します
            return urljoin(url, content.group(1)), "og:image"

    # 2) 本文中の <img> のうち、ロゴやアイコンではなさそうな最初のもの
    for src in IMG_TAG.findall(html):
        if src.lower().endswith(".svg"):
            continue  # SVGはアイコンであることがほとんどなので飛ばす
        if _looks_generic(src):
            continue
        return urljoin(url, src), "本文"

    return "", ""


def _parse_feed(url: str) -> feedparser.FeedParserDict:
    """requests で取得した内容を feedparser に渡す(SSL問題を避けるため)"""
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    feed = feedparser.parse(response.content)

    # bozo は「XMLとして厳密に妥当ではない」というだけで、記事が取れていれば実害はない。
    # 記事が0件のときだけ問題として扱う。
    if feed.bozo and not feed.entries:
        raise ValueError(f"フィードを解析できません: {feed.bozo_exception}")
    return feed


# ==========================================================================
# 記事の取得
# ==========================================================================


def fetch_feed(name: str, url: str, open_article_page: bool) -> pd.DataFrame:
    """1つのRSSフィードを取得し、記事一覧をDataFrameにする"""
    print(f"取得中: {name} ...")
    feed = _parse_feed(url)

    articles = []
    for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
        link = entry.get("link", "")

        # --- 画像URLを探す ---
        image_url = _image_from_entry(entry)
        image_from = "RSS" if image_url else ""

        # RSSに無ければ記事ページを開いて探す(公式発表のフィード向け)
        if not image_url and open_article_page and link:
            image_url, image_from = _image_from_page(link)
            time.sleep(ARTICLE_INTERVAL)

        articles.append({
            "source": name,
            "title": entry.get("title", ""),
            "link": link,
            "published": _published(entry),
            "summary": entry.get("summary", ""),
            "image_url": image_url,
            # 画像をどこで見つけたか(RSS / og:image / 本文)。空欄なら画像なし
            "image_source": image_from,
            # ロゴや既定画像など、記事の内容と関係ない画像かどうか
            "image_is_generic": _looks_generic(image_url) if image_url else False,
        })

    df = pd.DataFrame(articles)
    has_image = int((df["image_url"] != "").sum())
    generic = int(df["image_is_generic"].sum())
    print(f"  → {len(df)}件の記事を取得 "
          f"(画像あり {has_image}件 / うち既定画像 {generic}件)")
    return df


def fetch_all_feeds() -> pd.DataFrame:
    """記事系のフィードをすべて取得し、1つのCSVにまとめる"""
    today = datetime.now().strftime("%Y%m%d")
    all_articles = []

    # 公式発表は記事ページを開いて画像を探します(RSSに画像がないため)
    for name, url in OFFICIAL_FEEDS.items():
        try:
            df = fetch_feed(name, url, open_article_page=FETCH_ARTICLE_PAGE)
            if not df.empty:
                all_articles.append(df)
        except Exception as e:
            print(f"  → 取得失敗 ({name}): {e}")

    # 報道機関のフィードはRSSに画像が入っているので、記事ページは開きません
    for name, url in NEWS_FEEDS.items():
        try:
            df = fetch_feed(name, url, open_article_page=False)
            if not df.empty:
                all_articles.append(df)
        except Exception as e:
            print(f"  → 取得失敗 ({name}): {e}")

    if not all_articles:
        print("記事を1件も取得できませんでした。")
        return pd.DataFrame()

    combined = pd.concat(all_articles, ignore_index=True)
    combined = combined.drop_duplicates(subset=["link"])
    combined = combined.sort_values("published", ascending=False)

    # --- 見出しを日本語に翻訳する ---
    # 翻訳できなかった見出しは、元の言語のままにします
    print("\n見出しを翻訳中...")
    mapping = translate_titles(combined["title"].tolist())
    combined["title_ja"] = combined["title"].map(
        lambda t: mapping.get((t or "").strip(), t)
    )

    output_path = OUTPUT_DIR / f"eu_news_{today}.csv"
    combined.to_csv(output_path, index=False, encoding="utf-8")

    total_image = int((combined["image_url"] != "").sum())
    real_image = int(((combined["image_url"] != "")
                      & (~combined["image_is_generic"])).sum())
    print(f"\n合計 {len(combined)} 件の記事を保存しました: {output_path}")
    print(f"画像URLあり: {total_image}件 "
          f"(うち記事固有とみられる画像: {real_image}件)")
    return combined


# ==========================================================================
# 動画の取得(YouTube公式チャンネル)
# ==========================================================================


def fetch_youtube_channel(name: str, channel_id: str) -> pd.DataFrame:
    """
    YouTubeの公式チャンネルから、最新の動画一覧を取得する。
    YouTubeはチャンネルごとにRSSを配信しているので、APIキーは要りません。
    配信されるのは最新15本です。
    """
    print(f"取得中: {name} (YouTube) ...")
    feed = _parse_feed(YOUTUBE_FEED.format(channel_id))

    videos = []
    for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
        # サムネイル画像は media:thumbnail に入っています
        thumbnails = entry.get("media_thumbnail") or []
        thumbnail = thumbnails[0].get("url", "") if thumbnails else ""

        link = entry.get("link", "")
        videos.append({
            "source": name,
            "title": entry.get("title", ""),
            "link": link,
            "published": _published(entry),
            "thumbnail_url": thumbnail,
            # 動画ID(yt:videoId)。埋め込み再生をしたくなったときに使えます
            "video_id": entry.get("yt_videoid", ""),
            # ショート動画かどうか(URLで見分けられます)
            "is_short": "/shorts/" in link,
        })

    df = pd.DataFrame(videos)
    has_thumb = int((df["thumbnail_url"] != "").sum())
    print(f"  → {len(df)}本の動画を取得 (サムネイルあり {has_thumb}本)")
    return df


def normalize_title(title: str) -> str:
    """
    重複を見つけるために、タイトルを比べやすい形にそろえる。

    同じ内容の動画でも、末尾のチャンネル名やハッシュタグが違うだけで
    「別のタイトル」と判定されてしまいます。そこで比較用に、
    次のものを取り除いた文字列を作ります。
        ・末尾の「 | DW News」のようなチャンネル名
        ・#shorts などのハッシュタグ
        ・大文字小文字の違い、余分な空白、前後の記号
    """
    text = str(title or "").lower()
    text = re.sub(r"#\w+", " ", text)          # ハッシュタグを削除
    text = text.split("|")[0]                   # 「 | チャンネル名」以降を切り落とす
    text = re.sub(r"[\s　]+", " ", text)   # 連続する空白を1つにまとめる
    return text.strip(" -–—:・|")


def deduplicate_videos(df: pd.DataFrame) -> pd.DataFrame:
    """
    同じ動画が2つ以上入っているときに、1つだけ残す。

    【なぜ動画IDだけでは足りないか】
    euronews は同じニュースを「ショート動画」と「通常の動画」の両方で投稿します。
    この2つは YouTube 上では別の動画なので、動画IDもURLも異なります。
    そのため、内容(タイトル)もあわせて見比べる必要があります。

    残すほうを選ぶ基準:
        1. ショート動画より、通常の動画を優先する(内容が詳しいため)
        2. それでも決まらなければ、新しいほうを残す
    """
    if df.empty:
        return df

    work = df.copy()
    work["_key"] = work["title"].map(normalize_title)

    before = len(work)

    # まず、同じ動画IDのものを取り除きます(念のための保険)
    work = work.drop_duplicates(subset=["video_id"], keep="first")

    # 次に「同じチャンネル × 同じ内容」の重複を取り除きます。
    # チャンネルが違えば別の取材なので、まとめません。
    # 並べ替えてから先頭を残すことで、上の基準どおりに選べます。
    work = work.sort_values(
        by=["is_short", "published"], ascending=[True, False]
    )
    work = work.drop_duplicates(subset=["source", "_key"], keep="first")

    removed = before - len(work)
    if removed:
        print(f"  重複していた動画を{removed}本除きました")

    return work.drop(columns=["_key"])


def fetch_all_videos() -> pd.DataFrame:
    """YouTubeの全チャンネルから動画一覧を取得し、1つのCSVにまとめる"""
    today = datetime.now().strftime("%Y%m%d")
    all_videos = []

    for name, channel_id in YOUTUBE_CHANNELS.items():
        try:
            df = fetch_youtube_channel(name, channel_id)
            if not df.empty:
                all_videos.append(df)
        except Exception as e:
            print(f"  → 取得失敗 ({name}): {e}")

    if not all_videos:
        print("動画を1件も取得できませんでした。")
        return pd.DataFrame()

    combined = pd.concat(all_videos, ignore_index=True)
    combined = combined.drop_duplicates(subset=["link"])
    combined = deduplicate_videos(combined)
    combined = combined.sort_values("published", ascending=False)

    # --- 動画タイトルも日本語に翻訳する ---
    print("\nタイトルを翻訳中...")
    mapping = translate_titles(combined["title"].tolist())
    combined["title_ja"] = combined["title"].map(
        lambda t: mapping.get((t or "").strip(), t)
    )

    output_path = OUTPUT_DIR / f"eu_videos_{today}.csv"
    combined.to_csv(output_path, index=False, encoding="utf-8")
    print(f"\n合計 {len(combined)} 本の動画を保存しました: {output_path}")
    return combined


if __name__ == "__main__":
    print("========== 記事 ==========")
    fetch_all_feeds()
    print("\n========== 動画 ==========")
    fetch_all_videos()
