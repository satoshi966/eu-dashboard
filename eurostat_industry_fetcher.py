"""
Eurostat API から EU加盟国の「産業のつながり(産業連関表)」データを取得するスクリプト

【重要】このスクリプトはネットワーク接続が必要です。
このClaude.aiのチャット環境(サンドボックス)ではネットワークが無効化されているため実行できません。
Claude Code環境(ローカルPC)で実行してください。

必要ライブラリ:
    pip install requests pandas pyjstat

【用語の説明】
- 産業連関表(さんぎょうれんかんひょう): 「ある産業が作った製品が、別の産業でどれだけ
  材料として使われているか」を表にしたものです。例えば「自動車産業が、どれだけ鉄鋼産業の
  製品を買っているか」のような、産業同士のつながりが分かります。
- naio_10_cp1700: Eurostatが定めた、このデータセットの識別コードです。
  「naio」は National Accounts Input-Output(国民経済計算の産業連関)の略です。
- このデータは国ごとに別々に作られているため、EU全体をまとめて1回で取得することができず、
  国を1つずつ順番に取得する形になります(前回の貿易収支・移民データとはこの点が異なります)。
"""

import requests
import pandas as pd
import json
import time
from pathlib import Path
from datetime import datetime

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

# EU加盟27カ国の国コード(Eurostat標準)
EU27_COUNTRIES = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
]

# 産業連関表(基本価格表示・生産者価格ベース)のデータセットコード
DATASET_CODE = "naio_10_cp1700"

OUTPUT_DIR = Path("data/industry")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_dataset(dataset_code: str, params: dict | None = None) -> dict:
    """指定したEurostatデータセットをJSON形式で取得する"""
    url = f"{BASE_URL}/{dataset_code}"
    query = {"lang": "EN", "format": "JSON"}
    if params:
        query.update(params)

    response = requests.get(url, params=query, timeout=60)
    response.raise_for_status()
    return response.json()


def json_stat_to_dataframe(json_data: dict) -> pd.DataFrame:
    """JSON-stat形式のレスポンスをDataFrameに変換する(pyjstat利用)"""
    try:
        from pyjstat import pyjstat
        dataset = pyjstat.Dataset.read(json.dumps(json_data))
        return dataset.write("dataframe")
    except ImportError:
        print("pyjstat未インストールのため空のDataFrameを返します。 pip install pyjstat 推奨")
        return pd.DataFrame()


def fetch_industry_data_by_country():
    """
    国ごとに産業連関表データを取得する。
    一度に27カ国分を要求すると、貿易収支データの時と同様にサーバー側の上限に
    引っかかる可能性が高いため、最初から1カ国ずつ取得するようにしています。
    """
    today = datetime.now().strftime("%Y%m%d")
    all_data = []

    for country in EU27_COUNTRIES:
        print(f"取得中: {country} ...")
        try:
            raw = fetch_dataset(DATASET_CODE, params={"geo": country})
            df = json_stat_to_dataframe(raw)

            if not df.empty:
                df["country"] = country
                all_data.append(df)
                print(f"  → 成功: {len(df)}行")
            else:
                print(f"  → データなし: {country}")

        except requests.exceptions.HTTPError as e:
            print(f"  → 取得失敗 ({country}): {e}")
        except requests.exceptions.RequestException as e:
            print(f"  → 通信エラー ({country}): {e}")

        time.sleep(1.5)  # サーバーへの配慮(連続リクエストの間隔をあける)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        output_path = OUTPUT_DIR / f"industry_linkages_{today}.csv"
        combined.to_csv(output_path, index=False, encoding="utf-8")
        print(f"\n合計 {len(combined)} 行を保存しました: {output_path}")
        return combined
    else:
        print("データを1件も取得できませんでした。")
        return pd.DataFrame()


if __name__ == "__main__":
    fetch_industry_data_by_country()
