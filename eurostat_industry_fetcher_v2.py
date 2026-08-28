"""
Eurostat API から EU加盟国の「産業のつながり(産業連関表)」データを取得するスクリプト (v2)

v1 からの変更点 — 実測にもとづく3点:

  1. 413 のリトライ
     v1 は27カ国中26カ国が 413 で失敗したが、その中身は
     "ASYNCHRONOUS_RESPONSE"(サーバが混んでいるので後で来い)という一時的な応答だった。
     同じURLを間隔をあけて叩き直せば 200 が返る。指数バックオフで再試行する。
     恒久的な "EXTRACTION_TOO_BIG" とは区別して扱う。

  2. 空セルの除去
     JSON-stat は全次元の直積を返すため、実測値のないセルが大半を占める。
     v1 は1カ国(BG)だけで196万行・301MBのCSVを吐いていたが、実データは約4%だった。

  3. 既定の絞り込み
     単位(MIO_EUR/MIO_NAC)と取引区分(TOTAL/IMP/DOM)を全部引くと6倍になる。
     既定では ユーロ建て × 全取引 に絞る。内訳が必要なら UNIT / STK_FLOW を変更すること。

必要ライブラリ:
    pip install requests pandas pyjstat

【用語の説明】
- 産業連関表(さんぎょうれんかんひょう): 「ある産業が作った製品が、別の産業でどれだけ
  材料として使われているか」を表にしたものです。例えば「自動車産業が、どれだけ鉄鋼産業の
  製品を買っているか」のような、産業同士のつながりが分かります。
- naio_10_cp1700: Eurostatが定めた、このデータセットの識別コードです。
  「naio」は National Accounts Input-Output(国民経済計算の産業連関)の略です。
- prd_ava(供給側の製品) × prd_use(使用側の製品) の組み合わせが「つながり」を表します。
  121 × 123 の組み合わせがあり、実データが入るのはそのうち約4%です。
- このデータは国ごとに別々に作られているため、国を1つずつ順番に取得します。
"""

import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

EU27_COUNTRIES = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
]

DATASET_CODE = "naio_10_cp1700"

# --- 絞り込み条件 ---
UNIT = "MIO_EUR"      # 百万ユーロ建て。各国通貨建てが必要なら "MIO_NAC"
STK_FLOW = "TOTAL"    # 全取引。国産のみは "DOM"、輸入のみは "IMP"
SINCE_YEAR = "2020"   # 実データがあるのは2010〜2022年(2023年は未収録)

MAX_RETRIES = 6
RETRY_BASE_WAIT = 15  # 秒。ASYNCHRONOUS_RESPONSE は指数的に待ち時間を延ばす
REQUEST_INTERVAL = 1.5

OUTPUT_DIR = Path("data/industry")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ExtractionTooBig(Exception):
    """返却行数が上限を超えた。リトライしても無駄なのでフィルタを狭めるしかない"""


def _classify_413(response: requests.Response) -> str:
    """413 の中身を見て 'async'(一時的) か 'too_big'(恒久的) かを判定する"""
    try:
        label = response.json()["error"][0]["label"]
    except (ValueError, KeyError, IndexError):
        return "unknown"
    if "ASYNCHRONOUS_RESPONSE" in label:
        return "async"
    if "EXTRACTION_TOO_BIG" in label:
        return "too_big"
    return "unknown"


def fetch_dataset(dataset_code: str, params: dict | None = None) -> dict:
    """1リクエスト分を取得する。一時的な 413 は待ってから再試行する"""
    url = f"{BASE_URL}/{dataset_code}"
    query = {"lang": "EN", "format": "JSON"}
    if params:
        query.update(params)

    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.get(url, params=query, timeout=120)

        if response.status_code == 413:
            kind = _classify_413(response)
            if kind == "too_big":
                raise ExtractionTooBig(response.json()["error"][0]["label"])
            if kind == "async" and attempt < MAX_RETRIES:
                wait = RETRY_BASE_WAIT * attempt
                print(f"    サーバ混雑 (試行 {attempt}/{MAX_RETRIES}) — {wait}秒待機")
                time.sleep(wait)
                continue

        response.raise_for_status()
        return response.json()

    raise RuntimeError(f"{MAX_RETRIES}回リトライしても取得できず")


def json_stat_to_dataframe(json_data: dict) -> pd.DataFrame:
    """JSON-stat形式のレスポンスをDataFrameに変換する(pyjstat利用)"""
    from pyjstat import pyjstat

    # 収録のない国は 200 で「値0件」が返る。この場合 pyjstat は
    # ValueError: Length mismatch を投げるため、手前で弾く。
    if not json_data.get("value"):
        return pd.DataFrame()

    dataset = pyjstat.Dataset.read(json.dumps(json_data))
    return dataset.write("dataframe")


def fetch_industry_data_by_country() -> pd.DataFrame:
    """国ごとに産業連関表データを取得し、1つのCSVにまとめる"""
    today = datetime.now().strftime("%Y%m%d")
    all_data = []
    failed = []
    no_data = []

    params_base = {
        "unit": UNIT,
        "stk_flow": STK_FLOW,
        "sinceTimePeriod": SINCE_YEAR,
    }

    for country in EU27_COUNTRIES:
        print(f"取得中: {country} ...")
        try:
            raw = fetch_dataset(DATASET_CODE, dict(params_base, geo=country))
        except ExtractionTooBig as e:
            print(f"  → 上限超過 ({country}): {e}")
            failed.append(country)
            continue
        except (requests.exceptions.RequestException, RuntimeError) as e:
            print(f"  → 取得失敗 ({country}): {e}")
            failed.append(country)
            continue

        try:
            df = json_stat_to_dataframe(raw)
        except Exception as e:
            print(f"  → 変換失敗 ({country}): {type(e).__name__}: {e}")
            failed.append(country)
            continue

        # 実測値のないセルを落とす。これをしないとCSVが数百MB規模に膨らむ
        if not df.empty:
            df = df.dropna(subset=["value"])

        if df.empty:
            print(f"  → データなし: {country}")
            no_data.append(country)
            time.sleep(REQUEST_INTERVAL)
            continue

        df["country"] = country
        all_data.append(df)
        print(f"  → 成功: {len(df):,}行")

        time.sleep(REQUEST_INTERVAL)

    if not all_data:
        print("データを1件も取得できませんでした。")
        return pd.DataFrame()

    combined = pd.concat(all_data, ignore_index=True)
    output_path = OUTPUT_DIR / f"industry_linkages_{today}.csv"
    combined.to_csv(output_path, index=False, encoding="utf-8")

    got = len(EU27_COUNTRIES) - len(failed) - len(no_data)
    print(f"\n合計 {len(combined):,} 行を保存しました: {output_path}")
    print(f"データを取得できた国: {got}/{len(EU27_COUNTRIES)}")
    if no_data:
        print(f"該当データなし: {', '.join(no_data)}")
    if failed:
        print(f"取得に失敗した国: {', '.join(failed)}")
    return combined


if __name__ == "__main__":
    fetch_industry_data_by_country()
