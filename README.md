# EU ダッシュボード

EU の貿易・エネルギー・移民・産業のつながり・ニュース・国際比較を、
1つの画面で見られるようにした Streamlit アプリです。

データは公的機関の公開API・RSSから取得しています。

- [Eurostat](https://ec.europa.eu/eurostat) — 貿易、エネルギー、移民、産業連関表
- [World Bank](https://data.worldbank.org/) — 国際比較(GDP・人口・貿易・エネルギー)
- ECB / 欧州委員会 / 各国報道機関の RSS — ニュース
- YouTube 公式チャンネルの RSS — 動画

## 準備

```bash
pip install streamlit plotly pandas requests pyjstat feedparser deep-translator
```

## 使い方

### 1. データを取得する

まとめて実行する場合:

```bash
python run_all.py
```

個別に実行する場合:

```bash
python eurostat_trade_fetcher_v2.py       # 貿易・エネルギー・移民
python eurostat_industry_fetcher_v2.py    # 産業のつながり(産業連関表)
python worldbank_comparison_fetcher.py    # 国際比較
python eu_news_fetcher_v2.py              # ニュース・動画
```

取得したデータは `data/` に保存されます(リポジトリには含めていません)。

### 2. ダッシュボードを開く

```bash
streamlit run app.py
```

## 毎日自動で更新する (Windows)

`run_all.bat` をタスクスケジューラに登録すると、毎日決まった時刻に更新できます。

```
タスク名   : EU Dashboard Daily Update
実行する物 : run_all.bat
開始場所   : このフォルダ
```

実行結果は `logs/latest.log` に記録されます。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `app.py` | ダッシュボード本体(Streamlit) |
| `run_all.py` / `run_all.bat` | 全スクリプトをまとめて実行し、ログを残す |
| `eurostat_trade_fetcher_v2.py` | 貿易・エネルギー・移民データの取得 |
| `eurostat_industry_fetcher_v2.py` | 産業連関表の取得 |
| `worldbank_comparison_fetcher.py` | 国際比較データの取得 |
| `eu_news_fetcher_v2.py` | ニュース記事・YouTube動画の取得 |
| `translate_util.py` | 見出しの日本語訳(結果をキャッシュ) |

`_v2` が付いていないファイル (`eurostat_trade_fetcher.py` など) は初期版です。
Eurostat API が一時的に返す `413 ASYNCHRONOUS_RESPONSE` を再試行しないため、
データの大半を取り逃します。**実際に使うのは `_v2` のほうです。**

## データについて知っておくとよいこと

- **ギリシャ** はエネルギーと移民のデータに収録がなく、集計は 26 カ国です。
- **産業のつながり** は 2020 年以降のデータがある 21 カ国のみです。
  ブルガリア・デンマーク・フィンランド・ギリシャ・オランダ・ルーマニアは含まれません。
- **貿易収支** は EU27 を1つのまとまりとして見た数字で、加盟国別の内訳はありません。
- **ニュースの見出し** は機械翻訳です。原文も画面に併記しています。
