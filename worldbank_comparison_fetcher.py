"""
World Bank(世界銀行)のAPIから、主要国の国力を比較するためのデータを取得するスクリプト

【重要】このスクリプトはネットワーク接続が必要です。
このClaude.aiのチャット環境(サンドボックス)ではネットワークが無効化されているため実行できません。
Claude Code環境(ローカルPC)で実行してください。

必要ライブラリ:
    pip install requests pandas

【用語の説明】
- World Bank(世界銀行): 各国の経済発展を支援する国際機関で、GDP・人口・貿易額など、
  世界中の統計をまとめて無料公開しています。今回はここから「比較用のものさし」を借りてきます。
- インジケーター(指標)コード: 「どのデータの種類が欲しいか」を指定するための合言葉のようなものです。
  例えば「NY.GDP.MKTP.CD」は「GDP(名目・米ドル)」を意味します。
"""

import requests
import pandas as pd
import time
from pathlib import Path
from datetime import datetime

BASE_URL = "https://api.worldbank.org/v2/country"

# 比較したい国・地域のコード(World Bank標準の3文字コード)
# EUU = European Union(EU全体を1つの地域としてまとめた数値)
#   ※ EUのコードは "EUN" ではなく "EUU" です。
#      誤ったコードを指定してもエラーにはならず、「データなし」が静かに返るだけなので
#      気づきにくい点に注意してください(下の警告表示で気づけるようにしてあります)。
#      参考: EMU = ユーロ圏 / ECS = 欧州・中央アジア
COUNTRIES = {
    "EUU": "EU(欧州連合)",
    "CHN": "中国",
    "RUS": "ロシア",
    "USA": "アメリカ",
    "JPN": "日本",
}

# 比較したい指標(インジケーター)コード
INDICATORS = {
    "NY.GDP.MKTP.CD": "GDP(名目・米ドル)",
    "SP.POP.TOTL": "総人口",
    "NE.TRD.GNFS.ZS": "貿易総額(対GDP比)",
    "EG.USE.PCAP.KG.OE": "1人あたりエネルギー消費量",
}

OUTPUT_DIR = Path("data/comparison")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_indicator(country_code: str, indicator_code: str) -> pd.DataFrame:
    """1つの国・1つの指標のデータを取得する"""
    url = f"{BASE_URL}/{country_code}/indicator/{indicator_code}"
    params = {
        "format": "json",
        "per_page": 100,   # 直近100年分あれば十分カバーできます
        "date": "2000:2024",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    # World BankのAPIは [メタ情報, 実データ] という2つの要素のリストを返します
    if len(data) < 2 or data[1] is None:
        return pd.DataFrame()

    records = []
    for item in data[1]:
        records.append({
            "country_code": country_code,
            "indicator_code": indicator_code,
            "year": item.get("date"),
            "value": item.get("value"),
        })

    return pd.DataFrame(records)


def fetch_all_comparisons():
    """定義済みの全ての国×指標の組み合わせを取得する"""
    today = datetime.now().strftime("%Y%m%d")
    all_data = []

    for country_code, country_name in COUNTRIES.items():
        for indicator_code, indicator_name in INDICATORS.items():
            print(f"取得中: {country_name} - {indicator_name} ...")
            try:
                df = fetch_indicator(country_code, indicator_code)
                if not df.empty:
                    df["country_name"] = country_name
                    df["indicator_name"] = indicator_name
                    all_data.append(df)
                    print(f"  → 成功: {len(df)}件")
                else:
                    print(f"  → データなし")
            except requests.exceptions.RequestException as e:
                print(f"  → 取得失敗: {e}")

            time.sleep(0.5)  # サーバーへの配慮

    if not all_data:
        print("データを1件も取得できませんでした。")
        return pd.DataFrame()

    combined = pd.concat(all_data, ignore_index=True)

    # 年は文字列で返ってくるので、数値に直しておきます(並べ替えや絞り込みのため)
    combined["year"] = pd.to_numeric(combined["year"], errors="coerce")

    output_path = OUTPUT_DIR / f"country_comparison_{today}.csv"
    combined.to_csv(output_path, index=False, encoding="utf-8")
    print(f"\n合計 {len(combined)} 行を保存しました: {output_path}")

    # --- 取りこぼしがないか点検する ---
    # 国コードを間違えるとエラーにならず「データなし」になるだけなので、
    # 1件も取れなかった国・指標をここで目立たせます。
    got = set(combined["country_code"].unique())
    missing = [f"{name}({code})" for code, name in COUNTRIES.items() if code not in got]
    if missing:
        print(f"\n[警告] 1件も取得できなかった国・地域があります: {', '.join(missing)}")
        print("       国コードが正しいか確認してください。")

    # 値がすべて空の組み合わせも知らせます(コードは正しいが未収録の場合)
    empty = (combined.groupby(["country_name", "indicator_name"])["value"]
             .apply(lambda s: s.notna().sum() == 0))
    empty = [f"{c} / {i}" for (c, i), is_empty in empty.items() if is_empty]
    if empty:
        print(f"\n[注意] 値が空の組み合わせ: {', '.join(empty)}")

    return combined


if __name__ == "__main__":
    fetch_all_comparisons()
