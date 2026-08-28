"""
Eurostat API から EU加盟国の貿易収支・資源輸出入データを取得するスクリプト

【重要】このスクリプトはネットワーク接続が必要です。
このClaude.aiのチャット環境(サンドボックス)ではネットワークが無効化されているため実行できません。
Claude Code環境(ローカルPC / CI環境)で実行してください。

必要ライブラリ:
    pip install requests pandas

参考ドキュメント:
    https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-getting-started
"""

import requests
import pandas as pd
import json
import time
from pathlib import Path
from datetime import datetime

# --- 設定 ---
BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

# EU加盟27カ国の国コード(Eurostat標準)
EU27_COUNTRIES = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
]

# 主要データセットコード例(Eurostatのデータカタログで随時確認・調整が必要)
DATASETS = {
    # 国際貿易(商品別・国別)
    "trade_balance": "ext_st_eu27_2020sitc",
    # エネルギー資源の輸出入
    "energy_imports": "nrg_ti_gas",
    # 人口移動・移民統計
    "migration_flow": "migr_imm1ctz",
}

OUTPUT_DIR = Path("data/eurostat")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_dataset(dataset_code: str, params: dict | None = None) -> dict:
    """指定したEurostatデータセットをJSON-stat形式で取得する"""
    url = f"{BASE_URL}/{dataset_code}"
    query = {"lang": "EN", "format": "JSON"}
    if params:
        query.update(params)

    response = requests.get(url, params=query, timeout=30)
    response.raise_for_status()
    return response.json()


def json_stat_to_dataframe(json_data: dict) -> pd.DataFrame:
    """
    JSON-stat形式のレスポンスを扱いやすいDataFrameに変換する簡易パーサ。
    本格運用時は `pyjstat` ライブラリ(pip install pyjstat)の利用を推奨。
    """
    try:
        from pyjstat import pyjstat
        import io
        dataset = pyjstat.Dataset.read(json.dumps(json_data))
        return dataset.write("dataframe")
    except ImportError:
        print("pyjstat未インストールのため生JSONのまま返します。 pip install pyjstat 推奨")
        return pd.DataFrame()


def fetch_all_datasets():
    """定義済みの全データセットを取得し、日付付きでローカル保存する"""
    today = datetime.now().strftime("%Y%m%d")
    results = {}

    for name, code in DATASETS.items():
        print(f"取得中: {name} ({code}) ...")
        try:
            raw = fetch_dataset(code, params={"geo": EU27_COUNTRIES})
            df = json_stat_to_dataframe(raw)

            # 生JSONとパース済みCSVの両方を保存(スキーマ変更に備える)
            raw_path = OUTPUT_DIR / f"{name}_{today}_raw.json"
            csv_path = OUTPUT_DIR / f"{name}_{today}.csv"

            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False)

            if not df.empty:
                df.to_csv(csv_path, index=False, encoding="utf-8")
                print(f"  → 保存完了: {csv_path} ({len(df)}行)")
            else:
                print(f"  → 生JSONのみ保存: {raw_path}")

            results[name] = df

        except requests.exceptions.RequestException as e:
            print(f"  → 取得失敗 ({name}): {e}")

        time.sleep(1)  # APIへの配慮(連続リクエスト間隔)

    return results


if __name__ == "__main__":
    fetch_all_datasets()
