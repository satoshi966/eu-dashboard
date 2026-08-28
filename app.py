"""
EU ダッシュボード

data/ フォルダに保存済みのCSVを読み込んで、EUの貿易・エネルギー・移民・
産業のつながり・ニュースを1つの画面で見られるようにしたアプリです。

起動方法(ターミナルで実行):
    streamlit run app.py

必要ライブラリ:
    pip install streamlit plotly pandas
"""

import glob
import math
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ==========================================================================
# 1. 画面全体の基本設定
# ==========================================================================

# set_page_config は Streamlit の命令の中で「一番最初」に呼ぶ決まりです
st.set_page_config(
    page_title="EU ダッシュボード",
    page_icon="🇪🇺",
    layout="wide",                     # 画面を横幅いっぱいに使う
    initial_sidebar_state="expanded",  # サイドバーを最初から開いておく
)

# --- 配色(EUの旗の色をイメージ) ---
# 色を1か所にまとめておくと、後から変えたいときにここだけ直せば済みます
BLUE = "#003399"        # EU旗の青(基調色)
BLUE_MID = "#1a5cd8"    # 明るい青(グラフ用)
BLUE_LIGHT = "#7ba7f0"  # さらに明るい青
GOLD = "#f0b323"        # EU旗の金色(アクセント。ここぞという所だけに使う)
INK = "#1c2b45"         # 文字色(真っ黒より少し柔らかい紺)
MUTED = "#6b7a99"       # 補足文の色(グレー寄りの青)

# グラフの系列に順番に使われる色の並び
PALETTE = [BLUE, GOLD, BLUE_LIGHT, "#4d7fe0", "#96a8c8", "#2f4f8f"]

DATA_DIR = Path("data")

# --- 地図を描くための国コード対応表 ---
# 地図(コロプレス地図)を描くには、国名ではなく「ISO3166-1 alpha-3」という
# 3文字の国コードが必要です。データに出てくる26カ国分を用意しています。
COUNTRY_ISO3 = {
    "Austria": "AUT", "Belgium": "BEL", "Bulgaria": "BGR", "Croatia": "HRV",
    "Cyprus": "CYP", "Czechia": "CZE", "Denmark": "DNK", "Estonia": "EST",
    "Finland": "FIN", "France": "FRA", "Germany": "DEU", "Greece": "GRC",
    "Hungary": "HUN", "Ireland": "IRL", "Italy": "ITA", "Latvia": "LVA",
    "Lithuania": "LTU", "Luxembourg": "LUX", "Malta": "MLT",
    "Netherlands": "NLD", "Poland": "POL", "Portugal": "PRT",
    "Romania": "ROU", "Slovakia": "SVK", "Slovenia": "SVN",
    "Spain": "ESP", "Sweden": "SWE",
}


# ==========================================================================
# 2. 見た目の調整(CSS)
# ==========================================================================
# StreamlitはHTMLで画面を作っているので、CSSを流し込むと見た目を変えられます。
# 初心者のうちは「余白と文字の大きさを整えている部分」とだけ理解すればOKです。

st.markdown(
    f"""
    <style>
      /* ---- 全体の背景と余白 ---- */
      .stApp {{
          background-color: #f7f9fd;
      }}
      .block-container {{
          padding-top: 2.2rem;
          padding-bottom: 3rem;
          max-width: 1400px;
      }}

      /* ---- 見出し ---- */
      h1, h2, h3 {{
          color: {INK};
          font-weight: 700;
          letter-spacing: 0.01em;
      }}

      /* ページ最上部のタイトル帯 */
      .page-header {{
          border-left: 6px solid {BLUE};
          padding: 0.1rem 0 0.1rem 1rem;
          margin-bottom: 0.9rem;
      }}
      .page-header .title {{
          font-size: 1.9rem;
          font-weight: 700;
          color: {INK};
          line-height: 1.25;
      }}
      .page-header .subtitle {{
          font-size: 0.95rem;
          color: {MUTED};
          margin-top: 0.25rem;
      }}

      /* ---- 数字を大きく見せるカード ---- */
      .kpi-card {{
          background: #ffffff;
          border: 1px solid #e3e9f5;
          border-top: 4px solid {BLUE};
          border-radius: 12px;
          padding: 1.1rem 1.2rem 1rem 1.2rem;
          box-shadow: 0 2px 10px rgba(0, 51, 153, 0.06);
          height: 100%;
      }}
      .kpi-card .label {{
          font-size: 0.82rem;
          color: {MUTED};
          font-weight: 600;
          letter-spacing: 0.03em;
          margin-bottom: 0.45rem;
      }}
      .kpi-card .value {{
          font-size: 2.0rem;
          font-weight: 700;
          color: {BLUE};
          line-height: 1.1;
      }}
      .kpi-card .unit {{
          font-size: 0.95rem;
          font-weight: 600;
          color: {MUTED};
          margin-left: 0.25rem;
      }}
      .kpi-card .note {{
          font-size: 0.78rem;
          color: {MUTED};
          margin-top: 0.5rem;
      }}
      /* 金色を使うカード(1枚だけアクセントにする) */
      .kpi-card.accent {{
          border-top-color: {GOLD};
      }}
      .kpi-card.accent .value {{
          color: #b8830f;
      }}

      /* ---- 説明文のボックス ---- */
      .explain {{
          background: #ffffff;
          border-left: 4px solid {BLUE_LIGHT};
          border-radius: 8px;
          padding: 0.9rem 1.1rem;
          color: {INK};
          font-size: 0.93rem;
          line-height: 1.75;
          margin-bottom: 1.2rem;
      }}

      /* ---- ニュース一覧の1件分 ---- */
      .news-item {{
          background: #ffffff;
          border: 1px solid #e3e9f5;
          border-radius: 10px;
          padding: 0.9rem 1.1rem;
          margin-bottom: 0.7rem;
      }}
      .news-item a {{
          color: {BLUE};
          text-decoration: none;
          font-weight: 600;
          font-size: 1.0rem;
          line-height: 1.5;
      }}
      .news-item a:hover {{
          text-decoration: underline;
      }}
      .news-meta {{
          font-size: 0.78rem;
          color: {MUTED};
          margin-top: 0.4rem;
      }}

      /* 翻訳前の見出し(英語など)を小さく添える */
      .title-original {{
          font-size: 0.76rem;
          color: {MUTED};
          line-height: 1.45;
          margin-top: 0.3rem;
      }}
      .news-badge {{
          display: inline-block;
          background: #eaf0fc;
          color: {BLUE};
          border-radius: 4px;
          padding: 0.1rem 0.5rem;
          font-weight: 600;
          margin-right: 0.5rem;
      }}

      /* ---- 写真付きの記事 ---- */
      .news-thumb {{
          width: 100%;
          aspect-ratio: 16 / 10;
          object-fit: cover;          /* はみ出た部分を切り取って形をそろえる */
          border-radius: 10px;
          border: 1px solid #e3e9f5;
          display: block;
      }}
      .news-body {{
          padding: 0.1rem 0 0.9rem 0;
      }}
      .news-body a {{
          color: {BLUE};
          text-decoration: none;
          font-weight: 600;
          font-size: 1.0rem;
          line-height: 1.5;
      }}
      .news-body a:hover {{
          text-decoration: underline;
      }}

      /* ---- 動画カード ---- */
      .video-card {{
          background: #ffffff;
          border: 1px solid #e3e9f5;
          border-radius: 12px;
          overflow: hidden;
          margin-bottom: 1rem;
          box-shadow: 0 2px 8px rgba(0, 51, 153, 0.05);
      }}
      .video-thumb {{
          width: 100%;
          aspect-ratio: 16 / 9;
          object-fit: cover;
          display: block;
      }}
      .video-thumb-empty {{
          background: #eef2fa;
          color: {MUTED};
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.85rem;
      }}
      .video-body {{
          padding: 0.75rem 0.9rem 0.9rem 0.9rem;
      }}
      .video-body a {{
          color: {INK};
          text-decoration: none;
          font-weight: 600;
          font-size: 0.92rem;
          line-height: 1.5;
          display: block;
      }}
      .video-body a:hover {{
          color: {BLUE};
          text-decoration: underline;
      }}
      .video-badge {{
          display: inline-block;
          background: #fdf3dd;
          color: #8a6410;
          border-radius: 4px;
          padding: 0.1rem 0.5rem;
          font-weight: 600;
          margin-right: 0.5rem;
      }}

      /* ---- サイドバー ---- */
      section[data-testid="stSidebar"] {{
          background-color: #ffffff;
          border-right: 1px solid #e3e9f5;
      }}
      .sidebar-title {{
          font-size: 1.15rem;
          font-weight: 700;
          color: {BLUE};
          margin-bottom: 0.1rem;
      }}
      .sidebar-sub {{
          font-size: 0.78rem;
          color: {MUTED};
          margin-bottom: 1.2rem;
      }}

      /* Streamlit標準のメニューとフッターを隠してすっきりさせる */
      #MainMenu {{visibility: hidden;}}
      footer {{visibility: hidden;}}
    </style>
    """,
    unsafe_allow_html=True,
)


# ==========================================================================
# 3. データの読み込み
# ==========================================================================
# @st.cache_data を付けると、一度読んだデータを覚えておいてくれます。
# 画面を操作するたびに巨大なCSVを読み直さずに済むので、動作が速くなります。


def find_latest_csv(folder: str, prefix: str) -> Path | None:
    """
    data/<folder>/ の中から <prefix> で始まるCSVを探し、
    名前が一番後ろのもの(=日付が新しいもの)を返す。
    ファイル名に日付が入っているので、並べ替えの最後が最新になります。
    """
    pattern = str(DATA_DIR / folder / f"{prefix}*.csv")
    files = sorted(glob.glob(pattern))
    return Path(files[-1]) if files else None


@st.cache_data(show_spinner="貿易データを読み込み中...")
def load_trade() -> pd.DataFrame:
    """貿易データ。EU27全体と各相手国・地域との、月ごとの貿易額。"""
    path = find_latest_csv("eurostat", "trade_balance_")
    if path is None:
        return pd.DataFrame()

    df = pd.read_csv(path)
    # 列名が長いので、扱いやすい短い名前に付け替えます
    df = df.rename(columns={
        "Stock or flow": "flow",                     # 輸出 / 輸入 / 収支
        "External trade indicator": "indicator",     # 指標の種類
        "Geopolitical entity (partner)": "partner",  # 貿易相手
        "Standard International Trade Classification (SITC Rev. 4, 2006)": "product",
        "Time": "month",
    })
    # 指標は11種類ありますが、使うのは金額(百万ユーロ)だけです。
    # ここで絞らないと、金額と増加率が混ざって合計がおかしくなります。
    df = df[df["indicator"] == "Trade value in million ECU/EURO"]
    # 英語のままだと読みにくいので日本語にします
    df["flow"] = df["flow"].replace({
        "Imports": "輸入",
        "Exports": "輸出",
        "Balance for values/ratio for indices": "収支",
    })
    return df[["flow", "partner", "product", "month", "value"]]


@st.cache_data(show_spinner="エネルギーデータを読み込み中...")
def load_energy() -> pd.DataFrame:
    """天然ガスの輸入データ。どの国がどこから買っているかが年ごとに入っています。"""
    path = find_latest_csv("eurostat", "energy_imports_")
    if path is None:
        return pd.DataFrame()

    df = pd.read_csv(path)
    df = df.rename(columns={
        "Geopolitical entity (reporting)": "country",  # 輸入している国
        "Geopolitical entity (partner)": "partner",    # 輸入元
        "Unit of measure": "unit",
        "Time": "year",
    })
    # 単位が2種類(体積と熱量)あるので、分かりやすい「百万立方メートル」に統一します
    df = df[df["unit"] == "Million cubic metres"]
    return df[["country", "partner", "year", "value"]]


@st.cache_data(show_spinner="移民データを読み込み中...")
def load_migration() -> pd.DataFrame:
    """各国への移民の流入数(年ごと)。"""
    path = find_latest_csv("eurostat", "migration_flow_")
    if path is None:
        return pd.DataFrame()

    df = pd.read_csv(path)
    df = df.rename(columns={
        "Geopolitical entity (reporting)": "country",  # 受け入れ国
        "Country of citizenship": "citizenship",       # どの国籍の人か
        "Age definition": "age_def",
        "Time": "year",
    })
    # 「年齢の数え方」が2通り記録されていて、そのまま足すと二重に数えてしまいます。
    # 同じ国・同じ年の重複を1件に絞ります。片方の数え方しか無い国もあるため、
    # 優先する数え方を先頭に並べてから重複を落とします。
    priority = {"Age reached during the year": 0, "Age in completed years": 1}
    df["_priority"] = df["age_def"].map(priority).fillna(9)
    df = df.sort_values("_priority")
    df = df.drop_duplicates(subset=["country", "citizenship", "year"], keep="first")
    return df[["country", "citizenship", "year", "value"]]


@st.cache_data(show_spinner="産業データを読み込み中...")
def load_industry() -> pd.DataFrame:
    """産業連関表。ある産業の製品が、どの産業でどれだけ使われたか。"""
    path = find_latest_csv("industry", "industry_linkages_")
    if path is None:
        return pd.DataFrame()

    df = pd.read_csv(path)
    # このCSVには取得スクリプトが付けた country 列(国コード "DE" など)が既にあります。
    # 国名のほうを country として使いたいので、先に国コードの列を消しておきます。
    # (消さずに rename すると country 列が2つでき、後の処理でエラーになります)
    if "country" in df.columns:
        df = df.drop(columns=["country"])
    df = df.rename(columns={
        "Geopolitical entity (reporting)": "country",
        "Products and final uses": "use",                    # 使う側の産業
        "Products, adjustments and value added": "supply",   # 作る側(供給側)の産業
        "Time": "year",
    })
    return df[["country", "use", "supply", "year", "value"]]


@st.cache_data(show_spinner="国際比較データを読み込み中...")
def load_comparison() -> pd.DataFrame:
    """World Bank から取得した、EU・中国・ロシア・アメリカ・日本の比較データ。"""
    path = find_latest_csv("comparison", "country_comparison_")
    if path is None:
        return pd.DataFrame()

    df = pd.read_csv(path)
    df = df.rename(columns={
        "country_name": "country",     # 国・地域の名前
        "indicator_name": "indicator",  # 指標の名前
    })
    # 年は数値にしておきます(並べ替えや絞り込みのため)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    # 値が空の行は、グラフに出しても意味がないので落とします
    df = df.dropna(subset=["value", "year"])
    df["year"] = df["year"].astype(int)
    return df[["country", "indicator", "year", "value"]]


@st.cache_data(show_spinner="ニュースを読み込み中...")
def load_news() -> pd.DataFrame:
    """ECBと欧州委員会のRSSから取得したニュース一覧。"""
    path = find_latest_csv("news", "eu_news_")
    if path is None:
        return pd.DataFrame()

    df = pd.read_csv(path)
    # 文字列の日付を、日付として計算できる形に変換します
    df["published"] = pd.to_datetime(df["published"], errors="coerce")

    # 画像の列は、古いCSVには無いことがあるので、無ければ空で作っておきます
    for col in ("image_url", "image_source"):
        if col not in df.columns:
            df[col] = ""
    if "image_is_generic" not in df.columns:
        df["image_is_generic"] = False
    df["image_url"] = df["image_url"].fillna("")
    df["image_is_generic"] = df["image_is_generic"].fillna(False).astype(bool)

    # 日本語の見出し。古いCSVには無いので、無ければ元の見出しで埋めます
    if "title_ja" not in df.columns:
        df["title_ja"] = df["title"]
    df["title_ja"] = df["title_ja"].fillna(df["title"])

    return df.sort_values("published", ascending=False)


@st.cache_data(show_spinner="動画を読み込み中...")
def load_videos() -> pd.DataFrame:
    """YouTube公式チャンネルから取得した動画一覧。"""
    path = find_latest_csv("news", "eu_videos_")
    if path is None:
        return pd.DataFrame()

    df = pd.read_csv(path)
    df["published"] = pd.to_datetime(df["published"], errors="coerce")
    df["thumbnail_url"] = df.get("thumbnail_url", pd.Series(dtype=str)).fillna("")
    if "is_short" not in df.columns:
        df["is_short"] = False
    df["is_short"] = df["is_short"].fillna(False).astype(bool)

    # 日本語のタイトル。無ければ元のタイトルで埋めます
    if "title_ja" not in df.columns:
        df["title_ja"] = df["title"]
    df["title_ja"] = df["title_ja"].fillna(df["title"])

    # 同じ動画が2つ以上入っていたら、1つだけ残します。
    # (取得スクリプト側でも同じ処理をしていますが、古いCSVを読んだときのために
    #  こちらでも念のため行っています)
    df = _drop_duplicate_videos(df)

    return df.sort_values("published", ascending=False)


def _normalize_title(title: str) -> str:
    """
    重複を見つけるために、タイトルを比べやすい形にそろえる。
    末尾のチャンネル名(「 | DW News」など)やハッシュタグ、
    大文字小文字・余分な空白の違いを取り除きます。
    """
    text = str(title or "").lower()
    text = re.sub(r"#\w+", " ", text)        # ハッシュタグを削除
    text = text.split("|")[0]                 # 「 | チャンネル名」以降を切り落とす
    text = re.sub(r"[\s　]+", " ", text)  # 連続する空白を1つにまとめる
    return text.strip(" -–—:・|")


def _drop_duplicate_videos(df: pd.DataFrame) -> pd.DataFrame:
    """
    同じ動画が重複しているときに1本だけ残す。

    euronews などは、同じニュースを「ショート動画」と「通常の動画」の
    両方で投稿します。この2つは別の動画としてIDもURLも異なるため、
    内容(タイトル)もあわせて見比べる必要があります。
    ショートより通常の動画を優先し、それでも決まらなければ新しいほうを残します。
    """
    if df.empty or "video_id" not in df.columns:
        return df

    work = df.copy()
    work["_key"] = work["title"].map(_normalize_title)
    work = work.drop_duplicates(subset=["video_id"], keep="first")
    work = work.sort_values(by=["is_short", "published"], ascending=[True, False])
    # チャンネルが違えば別の取材なので、同じチャンネル内だけでまとめます
    work = work.drop_duplicates(subset=["source", "_key"], keep="first")
    return work.drop(columns=["_key"])


# ==========================================================================
# 4. 画面部品をつくる小さな関数
# ==========================================================================


def page_header(title: str, subtitle: str) -> None:
    """ページ上部のタイトル帯を表示する"""
    st.markdown(
        f'<div class="page-header">'
        f'<div class="title">{title}</div>'
        f'<div class="subtitle">{subtitle}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def explain(text: str) -> None:
    """薄い青の線が付いた説明文ボックスを表示する"""
    st.markdown(f'<div class="explain">{text}</div>', unsafe_allow_html=True)


def kpi_card(label: str, value: str, unit: str = "", note: str = "",
             accent: bool = False) -> str:
    """
    数字を大きく見せるカードのHTMLを組み立てて返す。
    accent=True にすると金色のカードになります(1枚だけ使うと目立ちます)。
    """
    css_class = "kpi-card accent" if accent else "kpi-card"
    unit_html = f'<span class="unit">{unit}</span>' if unit else ""
    note_html = f'<div class="note">{note}</div>' if note else ""
    return (
        f'<div class="{css_class}">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}{unit_html}</div>'
        f"{note_html}"
        f"</div>"
    )


def style_fig(fig: go.Figure, height: int = 420) -> go.Figure:
    """
    グラフの見た目をそろえるための関数。
    すべてのグラフをこれに通すことで、色や余白が統一されます。
    """
    fig.update_layout(
        height=height,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color=INK, size=13),
        margin=dict(l=10, r=10, t=55, b=10),
        title=dict(font=dict(size=16, color=INK)),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1, title_text="",
        ),
        # ホバー(マウスを乗せたとき)に出る吹き出しの見た目
        hoverlabel=dict(bgcolor="white", font_size=13, bordercolor=BLUE_LIGHT),
    )
    fig.update_xaxes(showgrid=False, linecolor="#dbe3f0", ticks="outside")
    fig.update_yaxes(showgrid=True, gridcolor="#eef2fa", zeroline=False)
    return fig


def short(text: str, n: int = 34) -> str:
    """長い産業名を、グラフに収まる長さに切り詰める"""
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


def fmt(num, digits: int = 0) -> str:
    """数値を3桁区切りの文字列にする(例: 1234567 -> 1,234,567)"""
    if num is None or pd.isna(num):
        return "—"
    return f"{num:,.{digits}f}"


# --------------------------------------------------------------------------
# 日本語の表記に整える関数
# --------------------------------------------------------------------------
# 英語圏の表記(1.2M など)は日本語では読みにくいので、
# 「万・億・兆」を使った日本のふつうの書き方に直します。

# 大きい数の単位。大きいほうから順に並べておきます
JP_UNITS = [
    (10 ** 12, "兆"),
    (10 ** 8, "億"),
    (10 ** 4, "万"),
]


def fmt_jp(num, digits: int = 1) -> str:
    """
    数値を日本語として読みやすい形にする。
        1234567   -> 123.5万
        120000000 -> 1.2億
        4523      -> 4,523
    digits は小数点以下の桁数です。
    """
    if num is None or pd.isna(num):
        return "—"

    num = float(num)
    sign = "-" if num < 0 else ""
    value = abs(num)

    for unit_value, unit_name in JP_UNITS:
        if value >= unit_value:
            scaled = value / unit_value
            # 「123.0万」より「123万」のほうが自然なので、
            # ちょうど割り切れるときは小数点以下を省きます
            if abs(scaled - round(scaled)) < 0.05:
                return f"{sign}{round(scaled):,.0f}{unit_name}"
            return f"{sign}{scaled:,.{digits}f}{unit_name}"

    # 1万未満はそのまま3桁区切りで表示します
    return f"{sign}{value:,.0f}"


def fmt_jp_date(value) -> str:
    """日付を「2026年8月28日」の形にする"""
    if value is None or pd.isna(value):
        return "日付不明"
    ts = pd.Timestamp(value)
    return f"{ts.year}年{ts.month}月{ts.day}日"


def fmt_jp_datetime(value) -> str:
    """日時を「2026年8月28日 10:30」の形にする"""
    if value is None or pd.isna(value):
        return "日付不明"
    ts = pd.Timestamp(value)
    return f"{ts.year}年{ts.month}月{ts.day}日 {ts.hour:02d}:{ts.minute:02d}"


def fmt_jp_month(value) -> str:
    """「2026-06」のような年月を「2026年6月」にする"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    text = str(value)
    if "-" in text:
        year, month = text.split("-")[:2]
        return f"{year}年{int(month)}月"
    return text


def jp_ticks(fig: go.Figure, values, axis: str = "x", unit: str = "") -> go.Figure:
    """
    グラフの目盛りを日本語表記(万・億)に置き換える。

    plotly は初期状態だと目盛りを「1.2M」「50k」のように英語式で書きます。
    そこで、目盛りの位置を自分で決めて、ラベルだけ日本語に差し替えます。
    unit を渡すと、一番大きい目盛りにだけ単位を付けます。
    """
    values = pd.Series(list(values)).dropna()
    if values.empty:
        return fig

    low = min(0, float(values.min()))
    high = float(values.max())
    if high == low:
        return fig

    # 目盛りを5本前後にして、きりのよい間隔を選びます
    span = high - low
    rough_step = span / 5
    magnitude = 10 ** math.floor(math.log10(rough_step)) if rough_step > 0 else 1
    for multiplier in (1, 2, 2.5, 5, 10):
        step = magnitude * multiplier
        if step >= rough_step:
            break

    start = math.floor(low / step) * step
    tickvals, ticktext = [], []
    position = start
    while position <= high + step * 0.5:
        tickvals.append(position)
        ticktext.append(fmt_jp(position))
        position += step

    if unit and ticktext:
        ticktext[-1] = f"{ticktext[-1]} {unit}"

    if axis == "x":
        fig.update_xaxes(tickmode="array", tickvals=tickvals, ticktext=ticktext)
    else:
        fig.update_yaxes(tickmode="array", tickvals=tickvals, ticktext=ticktext)
    return fig


# ==========================================================================
# 5. 上部のサマリーカード(全ページ共通)
# ==========================================================================


def render_summary_cards(trade, energy, migration, news, videos) -> None:
    """EU全体の状況がひと目で分かるカードを5枚並べる"""

    # --- 1枚目・2枚目: 直近1か月の貿易額と収支 ---
    total_trade, balance, latest_month = None, None, "—"
    if not trade.empty:
        # 「Extra-EU27」= EU27を1つのまとまりとみなしたときの、EU域外との貿易です
        ext = trade[
            (trade["partner"] == "Extra-EU27 (from 2020)")
            & (trade["product"] == "Total - all products")
        ]
        if not ext.empty:
            latest_month = ext["month"].max()
            last = ext[ext["month"] == latest_month]
            imports = last.loc[last["flow"] == "輸入", "value"].sum()
            exports = last.loc[last["flow"] == "輸出", "value"].sum()
            total_trade = imports + exports
            balance = exports - imports

    # --- 3枚目: 直近年の天然ガス輸入量 ---
    gas, gas_year = None, "—"
    if not energy.empty:
        # partner が "Total" の行が「すべての輸入元の合計」です。
        # 個別の相手国と一緒に足すと二重計上になるので、合計行だけを使います。
        totals = energy[energy["partner"] == "Total"]
        if not totals.empty:
            gas_year = int(totals["year"].max())
            gas = totals.loc[totals["year"] == gas_year, "value"].sum()

    # --- 4枚目: 直近年の移民流入数 ---
    migrants, mig_year = None, "—"
    if not migration.empty:
        totals = migration[migration["citizenship"] == "Total"]
        if not totals.empty:
            mig_year = int(totals["year"].max())
            migrants = totals.loc[totals["year"] == mig_year, "value"].sum()

    # --- 5枚目: ニュースと動画の件数 ---
    news_count = len(news)
    video_count = len(videos)
    news_note = "—"
    if news_count and news["published"].notna().any():
        news_note = f"最新: {fmt_jp_date(news['published'].max())}"
    if video_count:
        news_note += f" ／ 動画 {video_count}本"

    # 5枚を横に並べる
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(kpi_card(
            "域外貿易額 (輸出＋輸入)", fmt_jp(total_trade), "百万€",
            f"{fmt_jp_month(latest_month)} の1か月",
        ), unsafe_allow_html=True)
    with col2:
        st.markdown(kpi_card(
            "貿易収支 (輸出−輸入)", fmt_jp(balance), "百万€",
            "プラスなら黒字",
        ), unsafe_allow_html=True)
    with col3:
        st.markdown(kpi_card(
            "天然ガス輸入量", fmt_jp(gas), "百万m³",
            f"{gas_year}年 / 26カ国合計",
        ), unsafe_allow_html=True)
    with col4:
        st.markdown(kpi_card(
            "移民流入数", fmt_jp(migrants), "人",
            f"{mig_year}年 / 26カ国合計",
        ), unsafe_allow_html=True)
    with col5:
        st.markdown(kpi_card(
            "ニュース記事数", fmt(news_count), "件", news_note, accent=True,
        ), unsafe_allow_html=True)

    # カードとページ本体の間に余白を入れる
    st.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)


# ==========================================================================
# 6. 各ページの中身
# ==========================================================================


def page_trade(trade: pd.DataFrame) -> None:
    page_header("貿易収支", "EU27全体と、世界各国・地域とのモノの取引")

    if trade.empty:
        st.warning(
            "貿易データが見つかりません。"
            "eurostat_trade_fetcher_v2.py を実行してCSVを作成してください。"
        )
        return

    explain(
        "EU27を<b>1つのまとまり</b>として見たときの貿易額です。"
        "「輸出」から「輸入」を引いたものが<b>貿易収支</b>で、"
        "プラスなら売った方が多い(黒字)、マイナスなら買った方が多い(赤字)ことを表します。"
        "グラフの線や棒に<b>マウスを乗せると、正確な数字</b>が表示されます。"
    )

    # --- 貿易相手を選ぶ ---
    partners = sorted(trade["partner"].unique())
    target = "Extra-EU27 (from 2020)"
    default_index = partners.index(target) if target in partners else 0
    partner = st.selectbox("貿易相手を選ぶ", partners, index=default_index)

    subset = trade[
        (trade["partner"] == partner)
        & (trade["product"] == "Total - all products")
    ]

    # --- タブで2つの見方を切り替える ---
    # st.tabs は、見出しをクリックすると中身が入れ替わる部品です。
    tab_line, tab_compare = st.tabs(["📈 時系列で見る", "📊 国・地域を比べる"])

    # === タブ1: 月ごとの推移(折れ線) ===
    with tab_line:
        timeline = subset.groupby(["month", "flow"], as_index=False)["value"].sum()
        # ホバーに出す文字を、あらかじめ日本語の形にして列に持たせます
        timeline["月表示"] = timeline["month"].map(fmt_jp_month)
        timeline["金額表示"] = timeline["value"].map(fmt_jp)
        fig = px.line(
            timeline, x="month", y="value", color="flow", markers=True,
            color_discrete_map={"輸出": BLUE, "輸入": GOLD, "収支": BLUE_LIGHT},
            labels={"month": "年月", "value": "金額 (百万ユーロ)", "flow": ""},
            title=f"月ごとの推移 — {partner}",
            custom_data=["月表示", "金額表示"],
        )
        fig.update_traces(
            hovertemplate="%{customdata[0]}<br>%{customdata[1]} 百万€"
                          "<extra>%{fullData.name}</extra>"
        )
        st.plotly_chart(jp_ticks(style_fig(fig, 430), timeline["value"], "y"))

    # === タブ2: 国・地域ごとの輸出入を並べて比べる ===
    with tab_compare:
        st.caption(
            "同じ相手について、輸出(青)と輸入(金)の棒を並べています。"
            "輸出の棒が長ければEUの売り越し、輸入の棒が長ければ買い越しです。"
        )

        latest_month = trade["month"].max()
        # 「上位◯件まで表示するか」をスライダーで選べるようにします
        top_n = st.slider("表示する相手の数", min_value=5, max_value=25, value=12, step=1)

        compare = trade[
            (trade["month"] == latest_month)
            & (trade["product"] == "Total - all products")
            & (trade["flow"].isin(["輸出", "輸入"]))
            # 「EU域外の合計」などのまとめ項目は、個別の国と重複するので除きます
            & (~trade["partner"].isin([
                "Extra-EU27 (from 2020)",
                "European Union - 27 countries (from 2020)",
            ]))
        ]
        compare = compare.groupby(["partner", "flow"], as_index=False)["value"].sum()

        # 輸出と輸入を足した合計が大きい順に、上位だけを残します
        totals_by_partner = compare.groupby("partner")["value"].sum()
        keep = totals_by_partner.nlargest(top_n).index
        compare = compare[compare["partner"].isin(keep)]
        # 棒が大きい順に上から並ぶように、並び順を決めます
        order = totals_by_partner[keep].sort_values().index.tolist()

        compare["label"] = compare["partner"].map(lambda s: short(s, 28))
        compare["金額表示"] = compare["value"].map(fmt_jp)
        label_order = [short(p, 28) for p in order]

        fig_cmp = px.bar(
            compare, x="value", y="label", color="flow",
            orientation="h", barmode="group",   # group = 棒を横に並べる
            color_discrete_map={"輸出": BLUE, "輸入": GOLD},
            category_orders={"label": label_order, "flow": ["輸出", "輸入"]},
            labels={"value": "金額 (百万ユーロ)", "label": "", "flow": ""},
            title=f"国・地域ごとの輸出入の比較 上位{top_n} ({fmt_jp_month(latest_month)})",
            custom_data=["partner", "金額表示"],
        )
        fig_cmp.update_traces(
            hovertemplate="%{customdata[0]}<br>%{customdata[1]} 百万€"
                          "<extra>%{fullData.name}</extra>"
        )
        # 相手の数に応じてグラフの高さを変え、棒がつぶれないようにします
        st.plotly_chart(jp_ticks(
            style_fig(fig_cmp, max(420, 34 * top_n + 140)), compare["value"], "x"))

        # --- 収支(輸出−輸入)を1本の棒で見る ---
        st.caption(
            "こちらは **収支**(輸出−輸入)だけを取り出したものです。"
            "右に伸びていれば黒字、左に伸びていれば赤字を表します。"
        )
        wide = compare.pivot_table(
            index="partner", columns="flow", values="value", aggfunc="sum"
        ).fillna(0)
        wide["収支"] = wide.get("輸出", 0) - wide.get("輸入", 0)
        wide = wide.reset_index().sort_values("収支")
        wide["label"] = wide["partner"].map(lambda s: short(s, 28))
        # 黒字はEU青、赤字は金色にして、ひと目で区別できるようにします
        wide["色"] = wide["収支"].map(lambda v: "黒字" if v >= 0 else "赤字")
        wide["収支表示"] = wide["収支"].map(fmt_jp)

        fig_bal = px.bar(
            wide, x="収支", y="label", orientation="h", color="色",
            color_discrete_map={"黒字": BLUE, "赤字": GOLD},
            labels={"収支": "貿易収支 (百万ユーロ)", "label": "", "色": ""},
            title=f"相手ごとの貿易収支 ({fmt_jp_month(latest_month)})",
            custom_data=["partner", "収支表示"],
        )
        fig_bal.update_traces(
            hovertemplate="%{customdata[0]}<br>%{customdata[1]} 百万€"
                          "<extra>%{fullData.name}</extra>"
        )
        fig_bal.add_vline(x=0, line_width=1, line_color="#b9c4d8")
        st.plotly_chart(jp_ticks(
            style_fig(fig_bal, max(420, 34 * top_n + 140)), wide["収支"], "x"))

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    left, right = st.columns(2)

    # --- グラフ2: 貿易相手ランキング(横棒) ---
    with left:
        latest = trade["month"].max()
        ranking = trade[
            (trade["month"] == latest)
            & (trade["product"] == "Total - all products")
            & (trade["flow"].isin(["輸出", "輸入"]))
            # 「EU域外の合計」などのまとめ項目は、個別の国と重複するので除きます
            & (~trade["partner"].isin([
                "Extra-EU27 (from 2020)",
                "European Union - 27 countries (from 2020)",
            ]))
        ]
        ranking = ranking.groupby("partner", as_index=False)["value"].sum()
        ranking = ranking.nlargest(12, "value").sort_values("value")
        ranking["label"] = ranking["partner"].map(lambda s: short(s, 26))
        ranking["金額表示"] = ranking["value"].map(fmt_jp)
        fig2 = px.bar(
            ranking, x="value", y="label", orientation="h",
            labels={"value": "輸出＋輸入 (百万ユーロ)", "label": ""},
            title=f"貿易相手ランキング 上位12 ({fmt_jp_month(latest)})",
            custom_data=["partner", "金額表示"],
        )
        fig2.update_traces(
            marker_color=BLUE,
            hovertemplate="%{customdata[0]}<br>%{customdata[1]} 百万€<extra></extra>",
        )
        st.plotly_chart(jp_ticks(style_fig(fig2, 430), ranking["value"], "x"))

    # --- グラフ3: 品目の内訳(横棒) ---
    with right:
        products = trade[
            (trade["partner"] == partner)
            & (trade["month"] == trade["month"].max())
            & (trade["flow"].isin(["輸出", "輸入"]))
            # 「すべての製品」は合計なので、内訳を見るときは除きます
            & (trade["product"] != "Total - all products")
        ]
        products = products.groupby("product", as_index=False)["value"].sum()
        products = products.nlargest(12, "value").sort_values("value")
        products["label"] = products["product"].map(lambda s: short(s, 26))
        products["金額表示"] = products["value"].map(fmt_jp)
        fig3 = px.bar(
            products, x="value", y="label", orientation="h",
            labels={"value": "輸出＋輸入 (百万ユーロ)", "label": ""},
            title="品目の内訳 上位12",
            custom_data=["product", "金額表示"],
        )
        fig3.update_traces(
            marker_color=BLUE_MID,
            hovertemplate="%{customdata[0]}<br>%{customdata[1]} 百万€<extra></extra>",
        )
        st.plotly_chart(jp_ticks(style_fig(fig3, 430), products["value"], "x"))


def page_energy(energy: pd.DataFrame) -> None:
    page_header("エネルギー", "EU各国の天然ガス輸入 — どこから、どれだけ買っているか")

    if energy.empty:
        st.warning("エネルギーデータが見つかりません。")
        return

    explain(
        "天然ガスの輸入量です(単位は百万立方メートル)。"
        "EUは天然ガスの多くを域外から輸入しているため、"
        "<b>どの国から買っているか</b>はエネルギー安全保障に直結します。"
        "右下のグラフで2022年前後に注目すると、輸入元の顔ぶれが"
        "入れ替わっていく様子が読み取れます。"
        "<b>注記:</b> ギリシャはこのデータに収録がないため、26カ国の集計です。"
    )

    # partner が "Total" の行だけが「すべての輸入元の合計」です
    totals = energy[energy["partner"] == "Total"]

    # --- グラフ1: EU全体の輸入量の推移(塗りつぶしの折れ線) ---
    yearly = totals.groupby("year", as_index=False)["value"].sum()
    yearly["量表示"] = yearly["value"].map(fmt_jp)
    fig = px.area(
        yearly, x="year", y="value",
        labels={"year": "年", "value": "輸入量 (百万m³)"},
        title="EU(26カ国)の天然ガス輸入量の推移",
        custom_data=["量表示"],
    )
    fig.update_traces(
        line_color=BLUE, fillcolor="rgba(0,51,153,0.12)",
        hovertemplate="%{x}年<br>%{customdata[0]} 百万m³<extra></extra>",
    )
    st.plotly_chart(jp_ticks(style_fig(fig, 380), yearly["value"], "y"))

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    left, right = st.columns(2)

    # --- グラフ2: 直近年の国別ランキング ---
    with left:
        latest_year = int(totals["year"].max())
        by_country = totals[totals["year"] == latest_year]
        by_country = by_country.groupby("country", as_index=False)["value"].sum()
        by_country = by_country.nlargest(12, "value").sort_values("value")
        by_country["量表示"] = by_country["value"].map(fmt_jp)
        fig2 = px.bar(
            by_country, x="value", y="country", orientation="h",
            labels={"value": "輸入量 (百万m³)", "country": ""},
            title=f"国別の輸入量 上位12 ({latest_year}年)",
            custom_data=["量表示"],
        )
        fig2.update_traces(
            marker_color=BLUE,
            hovertemplate="%{y}<br>%{customdata[0]} 百万m³<extra></extra>",
        )
        st.plotly_chart(jp_ticks(style_fig(fig2, 430), by_country["value"], "x"))

    # --- グラフ3: 主な輸入元の推移 ---
    with right:
        # 合計行や不明な相手を除いて、実際の相手国だけを取り出します
        partners = energy[~energy["partner"].isin(["Total", "Not specified"])]
        top_partners = partners.groupby("partner")["value"].sum().nlargest(6).index
        trend = partners[partners["partner"].isin(top_partners)]
        trend = trend.groupby(["year", "partner"], as_index=False)["value"].sum()
        trend["量表示"] = trend["value"].map(fmt_jp)
        fig3 = px.line(
            trend, x="year", y="value", color="partner", markers=True,
            color_discrete_sequence=PALETTE,
            labels={"year": "年", "value": "輸入量 (百万m³)", "partner": ""},
            title="主な輸入元の推移 上位6",
            custom_data=["量表示"],
        )
        fig3.update_traces(
            hovertemplate="%{x}年<br>%{customdata[0]} 百万m³"
                          "<extra>%{fullData.name}</extra>"
        )
        st.plotly_chart(jp_ticks(style_fig(fig3, 430), trend["value"], "y"))


def page_migration(migration: pd.DataFrame) -> None:
    page_header("移民", "EU各国への人の流入 — 何人が、どこから来たか")

    if migration.empty:
        st.warning("移民データが見つかりません。")
        return

    explain(
        "各国が1年間に受け入れた移民の人数です。"
        "「国籍」は<b>移動してきた人がどの国のパスポートを持っているか</b>を表します。"
        "EU域内は移動の自由があるため、EU加盟国の国籍を持つ人の移動も多く含まれます。"
        "<b>注記:</b> ギリシャはこのデータに収録がないため、26カ国の集計です。"
    )

    totals = migration[migration["citizenship"] == "Total"]

    # --- タブで2つの見方を切り替える ---
    tab_trend, tab_map = st.tabs(["📈 推移で見る", "🗺️ 地図で見る"])

    # === タブ1: 年ごとの推移(棒グラフ) ===
    with tab_trend:
        yearly = totals.groupby("year", as_index=False)["value"].sum()
        yearly["人数表示"] = yearly["value"].map(fmt_jp)
        fig = px.bar(
            yearly, x="year", y="value",
            labels={"year": "年", "value": "流入数 (人)"},
            title="EU(26カ国)への移民流入数の推移",
            custom_data=["人数表示"],
        )
        fig.update_traces(
            marker_color=BLUE,
            hovertemplate="%{x}年<br>%{customdata[0]} 人<extra></extra>",
        )
        st.plotly_chart(jp_ticks(style_fig(fig, 400), yearly["value"], "y"))

    # === タブ2: 地図で見る(コロプレス地図) ===
    with tab_map:
        st.caption(
            "受け入れ数が多い国ほど濃い青で塗られます。"
            "国にマウスを乗せると人数が表示され、地図はドラッグで動かせます。"
        )

        # 見たい年をスライダーで選べるようにします
        year_list = sorted(int(y) for y in totals["year"].unique())
        selected_year = st.select_slider(
            "年を選ぶ", options=year_list, value=year_list[-1]
        )

        map_data = totals[totals["year"] == selected_year]
        map_data = map_data.groupby("country", as_index=False)["value"].sum()
        # 国名を3文字の国コードに変換します(地図はこのコードで国を見分けます)
        map_data["iso3"] = map_data["country"].map(COUNTRY_ISO3)
        map_data = map_data.dropna(subset=["iso3"])
        map_data["人数表示"] = map_data["value"].map(fmt_jp)

        fig_map = px.choropleth(
            map_data,
            locations="iso3",          # どの国かを示す列
            color="value",             # 色の濃さを決める列
            hover_name="country",
            color_continuous_scale=[[0, "#eef3fc"], [0.5, BLUE_LIGHT], [1, BLUE]],
            scope="europe",            # ヨーロッパだけを表示する
            labels={"value": "流入数 (人)"},
            title=f"移民の受け入れ数 ({selected_year}年)",
            custom_data=["人数表示"],
        )
        fig_map.update_traces(
            hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]} 人<extra></extra>",
            marker_line_color="white", marker_line_width=0.8,
        )
        # 地図の周りの枠線や余白を消して、すっきり見せます
        fig_map.update_geos(
            showframe=False, showcoastlines=False,
            landcolor="#f3f6fc", bgcolor="white",
            showcountries=True, countrycolor="#dbe3f0",
        )
        fig_map.update_layout(
            height=560, margin=dict(l=0, r=0, t=55, b=0),
            paper_bgcolor="white",
            font=dict(color=INK, size=13),
            title=dict(font=dict(size=16, color=INK)),
            hoverlabel=dict(bgcolor="white", font_size=13, bordercolor=BLUE_LIGHT),
            coloraxis_colorbar=dict(title="人数", thickness=14),
        )
        st.plotly_chart(fig_map)

        # 地図では小さい国が見えにくいので、数字の表も添えます
        ranked = map_data.sort_values("value", ascending=False)
        # 表の数字も「12.3万」のような日本語表記にします
        ranked = ranked[["country", "人数表示"]].reset_index(drop=True)
        ranked.index += 1
        ranked.columns = ["国", "流入数 (人)"]
        with st.expander(f"{selected_year}年の数値を表で見る"):
            st.dataframe(ranked, height=380)

        st.info(
            "ギリシャはこのデータに収録がないため、地図では色が付きません。"
            "また、地図に写るEU域外の国(ノルウェー、イギリスなど)も対象外です。",
            icon="ℹ️",
        )

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    left, right = st.columns(2)

    # --- グラフ2: 受け入れ国ランキング ---
    with left:
        latest_year = int(totals["year"].max())
        by_country = totals[totals["year"] == latest_year]
        by_country = by_country.groupby("country", as_index=False)["value"].sum()
        by_country = by_country.nlargest(12, "value").sort_values("value")
        by_country["人数表示"] = by_country["value"].map(fmt_jp)
        fig2 = px.bar(
            by_country, x="value", y="country", orientation="h",
            labels={"value": "流入数 (人)", "country": ""},
            title=f"受け入れ国ランキング 上位12 ({latest_year}年)",
            custom_data=["人数表示"],
        )
        fig2.update_traces(
            marker_color=BLUE,
            hovertemplate="%{y}<br>%{customdata[0]} 人<extra></extra>",
        )
        st.plotly_chart(jp_ticks(style_fig(fig2, 430), by_country["value"], "x"))

    # --- グラフ3: 国籍別ランキング ---
    with right:
        # 「Total」や「Europe」などのまとめ項目は、個別の国と重複するので除きます
        aggregate_labels = [
            "Total", "Europe",
            "European Union - 27 countries (2007-2013)",
            "European Union - 25 countries (2004-2006)",
            "European Union - 15 countries (1995-2004)",
            "European Free Trade Association",
            "European Free Trade Association except reporting country",
            "Other European countries (aggregate changing according to the context)",
            "Reporting country", "Unknown", "Stateless",
        ]
        citizenship = migration[
            (migration["year"] == migration["year"].max())
            & (~migration["citizenship"].isin(aggregate_labels))
        ]
        citizenship = citizenship.groupby("citizenship", as_index=False)["value"].sum()
        citizenship = citizenship.nlargest(12, "value").sort_values("value")
        citizenship["label"] = citizenship["citizenship"].map(lambda s: short(s, 26))
        citizenship["人数表示"] = citizenship["value"].map(fmt_jp)
        fig3 = px.bar(
            citizenship, x="value", y="label", orientation="h",
            labels={"value": "流入数 (人)", "label": ""},
            title="国籍別ランキング 上位12",
            custom_data=["citizenship", "人数表示"],
        )
        fig3.update_traces(
            marker_color=GOLD,
            hovertemplate="%{customdata[0]}<br>%{customdata[1]} 人<extra></extra>",
        )
        st.plotly_chart(jp_ticks(style_fig(fig3, 430), citizenship["value"], "x"))


def page_comparison(comparison: pd.DataFrame) -> None:
    page_header("国際比較", "EU・中国・ロシア・アメリカ・日本を、同じものさしで並べる")

    if comparison.empty:
        st.warning(
            "国際比較データが見つかりません。"
            "worldbank_comparison_fetcher.py を実行してCSVを作成してください。"
        )
        return

    explain(
        "世界銀行(World Bank)が公開している統計から、5つの国・地域を比べています。"
        "<b>EUは27カ国をまとめて1つ</b>として扱っているので、"
        "中国やアメリカといった1つの国と、規模の面で並べて見ることができます。"
        "棒にマウスを乗せると正確な数字が出ます。"
    )

    # --- どの指標を見るか選ぶ ---
    # 指標ごとに単位が違うので、1つずつ切り替えて見る形にします
    indicators = list(comparison["indicator"].unique())
    indicator = st.radio(
        "比べる項目", indicators, horizontal=True, label_visibility="collapsed"
    )

    subset = comparison[comparison["indicator"] == indicator]

    # 指標ごとに、単位と説明文を用意しておきます
    UNITS = {
        "GDP(名目・米ドル)": ("米ドル", "その国が1年間に生み出した価値の合計です。"
                              "経済の大きさを表す、もっとも代表的な数字です。"),
        "総人口": ("人", "その国・地域に住んでいる人の数です。"),
        "貿易総額(対GDP比)": ("%", "輸出と輸入の合計が、経済の大きさ(GDP)の何%にあたるかを示します。"
                              "数字が大きいほど、外国との取引に頼っている度合いが高いことを表します。"),
        "1人あたりエネルギー消費量": ("kg(石油換算)", "1人が1年間に使うエネルギーの量を、"
                                      "石油の重さに換算したものです。"),
    }
    unit, description = UNITS.get(indicator, ("", ""))
    if description:
        st.caption(description)

    # --- 見る年を選ぶ ---
    # 指標によって、データがそろっている年が違います。
    # 「5カ国すべての値がある最新の年」を初期値にします。
    country_total = comparison["country"].nunique()
    coverage = subset.groupby("year")["country"].nunique()
    full_years = coverage[coverage == country_total].index
    default_year = int(full_years.max()) if len(full_years) else int(subset["year"].max())

    year_list = sorted(int(y) for y in subset["year"].unique())
    year = st.select_slider("年を選ぶ", options=year_list, value=default_year)

    year_data = subset[subset["year"] == year].sort_values("value", ascending=True)

    # データが欠けている国があれば知らせます
    missing = sorted(set(comparison["country"].unique()) - set(year_data["country"]))
    if missing:
        st.info(
            f"{year}年は {', '.join(missing)} のデータがありません"
            f"(この年の棒グラフには表示されません)。",
            icon="ℹ️",
        )

    tab_bar, tab_trend = st.tabs(["📊 棒グラフで比べる", "📈 移り変わりを見る"])

    # === タブ1: 棒グラフ ===
    with tab_bar:
        year_data = year_data.copy()
        year_data["値表示"] = year_data["value"].map(
            lambda v: fmt_jp(v, 1) if abs(v) >= 10000 else f"{v:,.1f}"
        )
        # EUだけ色を変えて、どれがEUなのかすぐ分かるようにします
        year_data["色"] = year_data["country"].map(
            lambda c: "EU" if "EU" in c else "その他"
        )

        fig = px.bar(
            year_data, x="value", y="country", orientation="h", color="色",
            color_discrete_map={"EU": BLUE, "その他": BLUE_LIGHT},
            labels={"value": f"{indicator} ({unit})", "country": "", "色": ""},
            title=f"{indicator} — {year}年",
            custom_data=["値表示"],
        )
        fig.update_traces(
            hovertemplate=f"%{{y}}<br>%{{customdata[0]}} {unit}<extra></extra>"
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(jp_ticks(style_fig(fig, 420), year_data["value"], "x"))

        # --- EUを100としたときの比較 ---
        # 単位が大きすぎて実感しにくいので、EUを基準にした割合も出します
        eu_row = year_data[year_data["色"] == "EU"]
        if not eu_row.empty and eu_row["value"].iloc[0] != 0:
            eu_value = float(eu_row["value"].iloc[0])
            ratio = year_data.copy()
            ratio["割合"] = ratio["value"] / eu_value * 100
            ratio["割合表示"] = ratio["割合"].map(lambda v: f"{v:,.1f}")
            ratio = ratio.sort_values("割合")

            st.caption("**EUを100としたときの比較** — EUの何倍の規模かがひと目で分かります。")
            fig2 = px.bar(
                ratio, x="割合", y="country", orientation="h", color="色",
                color_discrete_map={"EU": GOLD, "その他": BLUE_LIGHT},
                labels={"割合": "EU=100 としたときの値", "country": "", "色": ""},
                title=f"EUを100としたときの{indicator} — {year}年",
                custom_data=["割合表示"],
            )
            fig2.update_traces(
                hovertemplate="%{y}<br>EU=100 に対して %{customdata[0]}<extra></extra>"
            )
            fig2.update_layout(showlegend=False)
            # EUの位置(100)に縦線を引いて、基準を分かりやすくします
            fig2.add_vline(x=100, line_width=1, line_dash="dash", line_color=GOLD)
            st.plotly_chart(style_fig(fig2, 420))

    # === タブ2: 推移 ===
    with tab_trend:
        st.caption(
            f"2000年から{int(subset['year'].max())}年までの移り変わりです。"
            "凡例の国名をクリックすると、その国の線を隠したり出したりできます。"
        )
        trend = subset.copy()
        trend["値表示"] = trend["value"].map(
            lambda v: fmt_jp(v, 1) if abs(v) >= 10000 else f"{v:,.1f}"
        )
        fig3 = px.line(
            trend, x="year", y="value", color="country", markers=True,
            color_discrete_sequence=PALETTE,
            labels={"year": "年", "value": f"{indicator} ({unit})", "country": ""},
            title=f"{indicator} の推移",
            custom_data=["値表示"],
        )
        fig3.update_traces(
            hovertemplate=f"%{{x}}年<br>%{{customdata[0]}} {unit}"
                          "<extra>%{fullData.name}</extra>"
        )
        st.plotly_chart(jp_ticks(style_fig(fig3, 480), trend["value"], "y"))


def page_news(news: pd.DataFrame, videos: pd.DataFrame) -> None:
    page_header("ニュース", "EUの公式発表・欧州各国の報道・テレビ局の最新動画")

    if news.empty and videos.empty:
        st.warning(
            "ニュースデータが見つかりません。"
            "eu_news_fetcher_v2.py を実行してCSVを作成してください。"
        )
        return

    explain(
        "各機関・報道各社が配信しているRSS(新着のお知らせ)から取得した一覧です。"
        "タイトルや画像をクリックすると、元のページが開きます。"
        "<b>注記:</b> 取得できるのは各配信元の<b>最新分のみ</b>で、"
        "過去記事をさかのぼって集めたものではありません。"
    )

    tab_articles, tab_videos = st.tabs(["📰 記事", "🎬 動画"])

    # ======================================================================
    # タブ1: 記事
    # ======================================================================
    with tab_articles:
        if news.empty:
            st.info("記事データがありません。")
        else:
            left, right = st.columns(2)

            # --- グラフ1: 発信元ごとの件数 ---
            with left:
                counts = news["source"].value_counts().reset_index()
                counts.columns = ["source", "count"]
                counts["label"] = counts["source"].map(lambda s: short(s, 24))
                counts = counts.sort_values("count")
                fig = px.bar(
                    counts, x="count", y="label", orientation="h",
                    labels={"count": "件数", "label": ""},
                    title="発信元ごとの件数",
                    custom_data=["source"],
                )
                fig.update_traces(
                    marker_color=BLUE,
                    hovertemplate="%{customdata[0]}<br>%{x} 件<extra></extra>",
                )
                st.plotly_chart(style_fig(fig, 340))

            # --- グラフ2: 日ごとの配信件数 ---
            with right:
                daily = news.dropna(subset=["published"]).copy()
                daily["date"] = daily["published"].dt.date
                daily = daily.groupby("date", as_index=False).size()
                fig2 = px.bar(
                    daily, x="date", y="size",
                    labels={"date": "日付", "size": "件数"},
                    title="日ごとの配信件数",
                )
                fig2.update_traces(
                    marker_color=GOLD,
                    hovertemplate="%{x}<br>%{y} 件<extra></extra>",
                )
                st.plotly_chart(style_fig(fig2, 340))

            st.markdown("### 記事一覧")

            col1, col2 = st.columns([3, 1])
            with col1:
                sources = ["すべて"] + sorted(news["source"].unique())
                choice = st.selectbox("発信元でしぼりこむ", sources)
            with col2:
                only_photo = st.checkbox("写真がある記事だけ", value=False)

            shown = news if choice == "すべて" else news[news["source"] == choice]
            if only_photo:
                # ロゴなどの既定画像は「写真あり」とみなしません
                shown = shown[(shown["image_url"] != "") & (~shown["image_is_generic"])]

            if shown.empty:
                st.info("条件に合う記事がありません。")
            else:
                st.caption(f"{len(shown)} 件")
                for _, row in shown.iterrows():
                    _render_article(row)

    # ======================================================================
    # タブ2: 動画
    # ======================================================================
    with tab_videos:
        if videos.empty:
            st.info(
                "動画データがありません。eu_news_fetcher_v2.py を実行すると "
                "data/news/eu_videos_*.csv が作られます。"
            )
            return

        st.caption(
            "Euronews・FRANCE 24・DW News の YouTube公式チャンネルから、"
            "最新の動画を取得しています(各チャンネル15本)。"
            "サムネイルをクリックするとYouTubeが開きます。"
        )

        col1, col2 = st.columns([3, 1])
        with col1:
            channels = ["すべて"] + sorted(videos["source"].unique())
            channel = st.selectbox("チャンネルでしぼりこむ", channels)
        with col2:
            hide_shorts = st.checkbox("ショート動画を除く", value=False)

        shown_videos = videos if channel == "すべて" else videos[videos["source"] == channel]
        if hide_shorts:
            shown_videos = shown_videos[~shown_videos["is_short"]]

        if shown_videos.empty:
            st.info("条件に合う動画がありません。")
            return

        st.caption(f"{len(shown_videos)} 本")

        # 3列のカード状に並べます
        columns = st.columns(3)
        for i, (_, row) in enumerate(shown_videos.iterrows()):
            with columns[i % 3]:
                _render_video(row)


def _titles(row) -> tuple[str, str]:
    """
    表示に使う「日本語の見出し」と「元の言語の見出し」を返す。
    翻訳できなかった記事は日本語が元の文と同じになるので、
    その場合は下に元の文を出さないようにします。
    """
    original = str(row.get("title", "") or "")
    japanese = str(row.get("title_ja", "") or "").strip()
    if not japanese:
        japanese = original
    # 翻訳結果が元と同じなら、二重に表示しても意味がないので原文は出しません
    subtitle = "" if japanese.strip() == original.strip() else original
    return japanese, subtitle


def _render_article(row) -> None:
    """記事1件を、画像付きのカードとして表示する"""
    date_text = fmt_jp_datetime(row["published"])
    title_ja, title_orig = _titles(row)
    orig_html = f'<div class="title-original">{title_orig}</div>' if title_orig else ""

    # ロゴなどの既定画像は表示しません(全記事で同じ絵が並んでしまうため)
    has_photo = bool(row["image_url"]) and not row["image_is_generic"]

    body = (
        f'<a href="{row["link"]}" target="_blank">{title_ja}</a>'
        f"{orig_html}"
        f'<div class="news-meta">'
        f'<span class="news-badge">{row["source"]}</span>{date_text}'
        f"</div>"
    )

    if has_photo:
        # 画像を左、文字を右に置く2列レイアウト
        img_col, text_col = st.columns([1, 3])
        with img_col:
            st.markdown(
                f'<a href="{row["link"]}" target="_blank">'
                f'<img src="{row["image_url"]}" class="news-thumb"></a>',
                unsafe_allow_html=True,
            )
        with text_col:
            st.markdown(f'<div class="news-body">{body}</div>',
                        unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="news-item">{body}</div>',
                    unsafe_allow_html=True)


def _render_video(row) -> None:
    """動画1件を、サムネイル付きのカードとして表示する"""
    date_text = fmt_jp_date(row["published"]) if pd.notna(row["published"]) else ""
    title_ja, title_orig = _titles(row)
    orig_html = f'<div class="title-original">{title_orig}</div>' if title_orig else ""

    badge = "ショート" if row["is_short"] else "動画"
    thumb = row["thumbnail_url"]
    thumb_html = (
        f'<img src="{thumb}" class="video-thumb">' if thumb
        else '<div class="video-thumb video-thumb-empty">画像なし</div>'
    )

    st.markdown(
        f'<div class="video-card">'
        f'<a href="{row["link"]}" target="_blank">{thumb_html}</a>'
        f'<div class="video-body">'
        f'<a href="{row["link"]}" target="_blank">{title_ja}</a>'
        f"{orig_html}"
        f'<div class="news-meta">'
        f'<span class="news-badge">{row["source"]}</span>'
        f'<span class="video-badge">{badge}</span>{date_text}'
        f"</div></div></div>",
        unsafe_allow_html=True,
    )


def page_industry(industry: pd.DataFrame) -> None:
    page_header("産業のつながり", "ある産業の製品が、どの産業でどれだけ使われているか")

    if industry.empty:
        st.warning(
            "産業データが見つかりません。"
            "eurostat_industry_fetcher_v2.py を実行してCSVを作成してください。"
        )
        return

    explain(
        "<b>産業連関表</b>という統計です。たとえば「自動車を作る産業が、"
        "鉄鋼を作る産業からどれだけ材料を買っているか」といった、"
        "産業どうしのつながりを金額で表しています。"
        "下のヒートマップは<b>縦が作る側・横が使う側</b>で、"
        "色が濃いマスほど取引額が大きいことを意味します。"
        "<b>注記:</b> 2020年以降のデータがある21カ国のみを収録しています。"
    )

    # --- 国と年を選ぶ ---
    col1, col2 = st.columns(2)
    with col1:
        countries = sorted(industry["country"].unique())
        default_index = countries.index("Germany") if "Germany" in countries else 0
        country = st.selectbox("国を選ぶ", countries, index=default_index)
    with col2:
        years = sorted(industry.loc[industry["country"] == country, "year"].unique())
        year = st.selectbox("年を選ぶ", years, index=len(years) - 1)

    subset = industry[(industry["country"] == country) & (industry["year"] == year)]
    # 「Total」は合計行なので、産業どうしの組み合わせを見るときは除きます
    detail = subset[(subset["use"] != "Total") & (subset["supply"] != "Total")]

    if detail.empty:
        st.info(f"{country} の {year}年 には、産業別の内訳データがありません。")
        return

    # --- グラフ1: ヒートマップ ---
    # 取引額の大きい産業を15ずつ選んで、15×15の表にします
    top_supply = detail.groupby("supply")["value"].sum().nlargest(15).index
    top_use = detail.groupby("use")["value"].sum().nlargest(15).index
    grid = detail[detail["supply"].isin(top_supply) & detail["use"].isin(top_use)]
    pivot = grid.pivot_table(index="supply", columns="use", values="value", aggfunc="sum")

    fig = px.imshow(
        pivot.values,
        x=[short(c, 20) for c in pivot.columns],
        y=[short(i, 20) for i in pivot.index],
        color_continuous_scale=[[0, "#ffffff"], [0.5, BLUE_LIGHT], [1, BLUE]],
        labels=dict(x="使う側の産業", y="作る側の産業", color="百万€"),
        title=f"産業どうしの取引額 — {country} / {year}年",
        aspect="auto",
    )
    fig.update_traces(
        hovertemplate="作る側: %{y}<br>使う側: %{x}<br>%{z:,.0f} 百万€<extra></extra>"
    )
    st.plotly_chart(style_fig(fig, 640))

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    left, right = st.columns(2)

    # --- グラフ2: 他産業に多く供給している産業 ---
    with left:
        supply = detail.groupby("supply", as_index=False)["value"].sum()
        supply = supply.nlargest(12, "value").sort_values("value")
        supply["label"] = supply["supply"].map(lambda s: short(s, 26))
        supply["金額表示"] = supply["value"].map(fmt_jp)
        fig2 = px.bar(
            supply, x="value", y="label", orientation="h",
            labels={"value": "供給額 (百万ユーロ)", "label": ""},
            title="他産業に多く供給している産業 上位12",
            custom_data=["supply", "金額表示"],
        )
        fig2.update_traces(
            marker_color=BLUE,
            hovertemplate="%{customdata[0]}<br>%{customdata[1]} 百万€<extra></extra>",
        )
        st.plotly_chart(jp_ticks(style_fig(fig2, 430), supply["value"], "x"))

    # --- グラフ3: 他産業から多く仕入れている産業 ---
    with right:
        use = detail.groupby("use", as_index=False)["value"].sum()
        use = use.nlargest(12, "value").sort_values("value")
        use["label"] = use["use"].map(lambda s: short(s, 26))
        use["金額表示"] = use["value"].map(fmt_jp)
        fig3 = px.bar(
            use, x="value", y="label", orientation="h",
            labels={"value": "投入額 (百万ユーロ)", "label": ""},
            title="他産業から多く仕入れている産業 上位12",
            custom_data=["use", "金額表示"],
        )
        fig3.update_traces(
            marker_color=GOLD,
            hovertemplate="%{customdata[0]}<br>%{customdata[1]} 百万€<extra></extra>",
        )
        st.plotly_chart(jp_ticks(style_fig(fig3, 430), use["value"], "x"))


# ==========================================================================
# 7. アプリ本体(サイドバーのメニューでページを切り替える)
# ==========================================================================


def main() -> None:
    # --- データを読み込む ---
    trade = load_trade()
    energy = load_energy()
    migration = load_migration()
    industry = load_industry()
    news = load_news()
    videos = load_videos()
    comparison = load_comparison()

    # --- サイドバー ---
    with st.sidebar:
        st.markdown('<div class="sidebar-title">🇪🇺 EU ダッシュボード</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="sidebar-sub">Eurostat / ECB / 欧州委員会</div>',
                    unsafe_allow_html=True)

        # radio(ラジオボタン)で1つだけ選ばせる = メニューになります
        page = st.radio(
            "メニュー",
            ["貿易収支", "エネルギー", "移民", "ニュース", "産業のつながり", "国際比較"],
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.caption("**データについて**")
        st.caption(
            "Eurostat の公式APIと、ECB・欧州委員会のRSSから取得したCSVを"
            "読み込んでいます。中身を更新したいときは、各 fetcher スクリプトを"
            "実行し直してから、下のボタンを押してください。"
        )
        if st.button("データを読み込み直す"):
            # 覚えているデータを捨てて、CSVを読み直します
            st.cache_data.clear()
            st.rerun()

    # --- 上部のサマリーカード(どのページでも共通で表示) ---
    render_summary_cards(trade, energy, migration, news, videos)

    # --- 選ばれたページを表示 ---
    if page == "貿易収支":
        page_trade(trade)
    elif page == "エネルギー":
        page_energy(energy)
    elif page == "移民":
        page_migration(migration)
    elif page == "ニュース":
        page_news(news, videos)
    elif page == "産業のつながり":
        page_industry(industry)
    elif page == "国際比較":
        page_comparison(comparison)


if __name__ == "__main__":
    main()
