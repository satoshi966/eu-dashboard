"""
Eurostat API から EU加盟国の貿易収支・資源輸出入データを取得するスクリプト (v2)

v1 からの変更点 — 実測した2種類の HTTP 413 に対応:

  1. ASYNCHRONOUS_RESPONSE
     「サーバが混んでいるので後で来い」という一時的な応答。リトライすれば通る。
     v1 はこれを恒久的な失敗として捨てていた(初回実行で nrg_ti_gas が落ちた原因)。

  2. EXTRACTION_TOO_BIG
     返却行数が上限 5,000,000 を超えるという恒久的な拒否。
     リトライしても無駄なので、国ごとに分割して取得し直す。

必要ライブラリ:
    pip install requests pandas pyjstat

参考:
    https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-getting-started
"""

import json
import time
from dataclasses import dataclass, field
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

MAX_RETRIES = 5
RETRY_BASE_WAIT = 20  # 秒。ASYNCHRONOUS_RESPONSE は指数バックオフで待つ


@dataclass
class DatasetSpec:
    """1データセット分の取得条件"""
    code: str
    # このデータセットで有効な geo コード。データセットごとに体系が違う点に注意
    geo: list[str] = field(default_factory=lambda: list(EU27_COUNTRIES))
    # 期間の絞り込み。EXTRACTION_TOO_BIG を避けるための主要な手段
    since: str | None = None
    # geo を一度に投げず、この件数ずつ分割する(None なら一括)
    geo_chunk: int | None = None
    extra: dict = field(default_factory=dict)


DATASETS: dict[str, DatasetSpec] = {
    # EU27全体と各貿易相手(56地域)との商品別貿易。月次。
    # 【注意】このデータセットの geo は 'EU27_2020' のみで、加盟国別の内訳を持たない。
    # 加盟国別の貿易収支が必要なら別データセットへの差し替えが必要。
    "trade_balance": DatasetSpec(
        code="ext_st_eu27_2020sitc", geo=["EU27_2020"], since="2023"
    ),
    # 天然ガスの輸出入。27カ国一括で約60万行、上限内に収まる
    "energy_imports": DatasetSpec(code="nrg_ti_gas", since="2000"),
    # 移民統計。年齢・性別の全内訳を引くと 5M 行上限を超えるため合計値に絞る。
    # 内訳が必要なら extra から age/sex を外し、geo_chunk=1 で国別に分割すること
    # (ただし全内訳は 27カ国で約3,300万行・3GBになる)。
    # 【注意】ギリシャ(GR)はこのデータセットに収録がなく、指定しても0件が返る。
    "migration_flow": DatasetSpec(
        code="migr_imm1ctz", extra={"age": "TOTAL", "sex": "T"}
    ),
}

OUTPUT_DIR = Path("data/eurostat")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ExtractionTooBig(Exception):
    """返却行数が上限を超えた。フィルタを狭めるしかない"""


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
    """1リクエスト分を取得する。一時的な 413 は指数バックオフでリトライする"""
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

    raise RuntimeError(f"{dataset_code}: {MAX_RETRIES}回リトライしても取得できず")


def json_stat_to_dataframe(json_data: dict) -> pd.DataFrame:
    """JSON-stat を DataFrame に変換する"""
    from pyjstat import pyjstat

    dataset = pyjstat.Dataset.read(json.dumps(json_data))
    return dataset.write("dataframe")


def _chunks(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def fetch_spec(spec: DatasetSpec) -> pd.DataFrame:
    """1データセットを取得する。必要なら国ごとに分割し、結果を結合して返す"""
    base_params = dict(spec.extra)
    if spec.since:
        base_params["sinceTimePeriod"] = spec.since

    groups = (
        list(_chunks(spec.geo, spec.geo_chunk))
        if spec.geo_chunk
        else [spec.geo]
    )

    frames = []
    for group in groups:
        params = dict(base_params, geo=group)
        label = ",".join(group) if len(group) <= 3 else f"{len(group)}カ国"
        try:
            raw = fetch_dataset(spec.code, params)
        except ExtractionTooBig as e:
            print(f"    [{label}] 上限超過のためスキップ: {e}")
            continue
        except requests.exceptions.RequestException as e:
            print(f"    [{label}] 取得失敗: {e}")
            continue

        df = json_stat_to_dataframe(raw)
        # JSON-stat は全次元の直積を返すため、実測値のないセルが大半を占める。
        # 落とさないとCSVが数GB規模に膨らむ。
        df = df.dropna(subset=["value"])
        if not df.empty:
            frames.append(df)
            print(f"    [{label}] {len(df):,}行")

        if len(groups) > 1:
            time.sleep(1)  # 分割取得時はAPIへの配慮で間隔を空ける

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def fetch_all_datasets() -> dict[str, pd.DataFrame]:
    """定義済みの全データセットを取得し、日付付きでローカル保存する"""
    today = datetime.now().strftime("%Y%m%d")
    results = {}

    for name, spec in DATASETS.items():
        print(f"取得中: {name} ({spec.code}) ...")
        df = fetch_spec(spec)

        if df.empty:
            print(f"  → {name}: データなし\n")
            results[name] = df
            continue

        csv_path = OUTPUT_DIR / f"{name}_{today}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")
        print(f"  → 保存完了: {csv_path} (計 {len(df):,}行)\n")
        results[name] = df

    return results


if __name__ == "__main__":
    fetch_all_datasets()
