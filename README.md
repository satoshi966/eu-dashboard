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

取得したデータは `data/` に保存されます(約260MB。リポジトリには含めていません)。

### 3. 公開用の軽量データを作る (Streamlit Community Cloud に載せる場合)

```bash
python make_public_data.py
```

`data/` から表示に必要な部分だけを取り出して `data_public/`(約33MB)を作ります。
`app.py` は `data/` があればそちらを、なければ `data_public/` を読みます。
手元ではフル版、クラウドでは軽量版が使われます。

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
| `make_public_data.py` | 公開用に絞り込んだ `data_public/` を作る |
| `requirements.txt` | 必要なライブラリの一覧 |

`_v2` が付いていないファイル (`eurostat_trade_fetcher.py` など) は初期版です。
Eurostat API が一時的に返す `413 ASYNCHRONOUS_RESPONSE` を再試行しないため、
データの大半を取り逃します。**実際に使うのは `_v2` のほうです。**

## データについて知っておくとよいこと

- **ギリシャ** はエネルギーと移民のデータに収録がなく、集計は 26 カ国です。
- **産業のつながり** は 2020 年以降のデータがある 21 カ国のみです。
  ブルガリア・デンマーク・フィンランド・ギリシャ・オランダ・ルーマニアは含まれません。
- **貿易収支** は EU27 を1つのまとまりとして見た数字で、加盟国別の内訳はありません。
- **ニュースの見出し** は機械翻訳です。原文も画面に併記しています。

### 公開版(`data_public/`)で削っているもの

画面の表示結果は変わりませんが、元データの一部を落としています。

| データ | 残しているもの |
|---|---|
| 貿易 | 11種類ある指標のうち「金額(百万ユーロ)」だけ |
| 産業 | 国・年ごとに取引額の上位1,200組み合わせ + 合計行 |
| エネルギー | 「合計」と、取引量の多い輸入元 上位20 |
| 移民 | 「合計」と、人数の多い国籍 上位50 |

グラフが使うのは上位6〜15件までなので、順位や数値は元データと一致します。
元データそのものが必要な場合は、各 fetcher を実行して `data/` を作り直してください。
