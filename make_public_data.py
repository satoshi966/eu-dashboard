"""
公開用にデータを軽くするスクリプト

data/ に入っている取得済みのCSVは合計260MBほどあり、そのままでは
GitHub に置けません(1ファイル100MBを超えると受け付けてもらえません)。
そこで、ダッシュボードの表示に必要な部分だけを取り出して
data_public/ に保存し直します。

    python make_public_data.py

app.py は data_public/ があればそちらを、なければ data/ を読みます。
手元では今までどおりフル版のデータで動き、
Streamlit Community Cloud では軽量版で動く、という使い分けになります。

【何を削っているか】
- 貿易 …… 11種類ある指標のうち、実際に使う「金額」だけを残す
- 産業 …… 取引額の小さい産業の組み合わせを落とす(グラフは上位15件しか使わない)
- その他 … そのままコピー(もともと小さいため)
"""

import shutil
from pathlib import Path

import pandas as pd

SOURCE_DIR = Path("data")
OUTPUT_DIR = Path("data_public")

# 産業データで、各国・各年について残す「作る側 × 使う側」の組み合わせの数。
# 画面では上位15×15(=225)しか使わないので、余裕をみて多めに残します。
INDUSTRY_TOP_N = 1200

# エネルギーデータで残す輸入元の数。
# 画面で使うのは「合計」と「上位6か国」だけなので、上位20を残せば
# ランキングの結果は変わりません(順位は全期間の合計で決めるため)。
ENERGY_TOP_PARTNERS = 20

# 移民データで残す国籍の数。画面で使うのは上位12なので、余裕をみて多めに残します。
MIGRATION_TOP_CITIZENSHIPS = 50


def show_size(path: Path) -> str:
    """ファイルの大きさを読みやすい文字にする"""
    mb = path.stat().st_size / 1024 / 1024
    return f"{mb:.2f} MB"


def slim_trade(src: Path, dst: Path) -> None:
    """
    貿易データを軽くする。

    このCSVには11種類の指標(金額・増加率・指数など)が入っていますが、
    ダッシュボードが使うのは「金額(百万ユーロ)」だけです。
    残りの10種類を落とすと、これだけで9割近く減ります。
    """
    df = pd.read_csv(src)
    before = len(df)
    df = df[df["External trade indicator"] == "Trade value in million ECU/EURO"]
    df.to_csv(dst, index=False, encoding="utf-8")
    print(f"  貿易      {before:,}行 → {len(df):,}行   "
          f"{show_size(src)} → {show_size(dst)}")


def slim_industry(src: Path, dst: Path) -> None:
    """
    産業データを軽くする。

    産業連関表は「121種類の産業 × 122種類の産業」の組み合わせを持っていますが、
    実際に金額が大きいのはごく一部です。画面のヒートマップも上位15×15しか
    表示しないため、取引額の大きい組み合わせだけを残します。
    """
    df = pd.read_csv(src)
    before = len(df)

    # 合計行(Total)は画面で使うので必ず残します
    totals = df[(df["Products and final uses"] == "Total")
                | (df["Products, adjustments and value added"] == "Total")]

    # それ以外は、国と年ごとに金額の大きい順で上位だけを残します
    detail = df.drop(totals.index)
    detail = (detail.sort_values("value", ascending=False)
                    .groupby(["country", "Time"], group_keys=False)
                    .head(INDUSTRY_TOP_N))

    slim = pd.concat([totals, detail], ignore_index=True)
    slim.to_csv(dst, index=False, encoding="utf-8")
    print(f"  産業      {before:,}行 → {len(slim):,}行   "
          f"{show_size(src)} → {show_size(dst)}")


def slim_energy(src: Path, dst: Path) -> None:
    """
    エネルギーデータを軽くする。

    輸入元(partner)が156種類ありますが、画面で使うのは
    「Total(全輸入元の合計)」と「取引量の多い上位6か国」だけです。
    順位は全期間の合計で決めているので、上位20を残しておけば
    グラフの中身は元のデータとまったく同じになります。
    """
    df = pd.read_csv(src)
    before = len(df)
    partner_col = "Geopolitical entity (partner)"

    # 合計行は必ず残します(EU全体の推移と国別ランキングで使うため)
    keep = {"Total"}

    # 合計や不明を除いた実際の相手国のうち、取引量の多い順に残します
    real = df[~df[partner_col].isin(["Total", "Not specified"])]
    top = real.groupby(partner_col)["value"].sum().nlargest(ENERGY_TOP_PARTNERS)
    keep.update(top.index)

    slim = df[df[partner_col].isin(keep)]
    slim.to_csv(dst, index=False, encoding="utf-8")
    print(f"  エネルギー {before:,}行 → {len(slim):,}行   "
          f"{show_size(src)} → {show_size(dst)}")


def slim_migration(src: Path, dst: Path) -> None:
    """
    移民データを軽くする。

    国籍(citizenship)が272種類ありますが、画面で使うのは
    「Total(合計)」と「上位12の国籍」だけです。
    余裕をみて上位50を残します。
    """
    df = pd.read_csv(src)
    before = len(df)
    col = "Country of citizenship"

    # 合計行は必ず残します(推移・国別ランキング・地図で使うため)
    keep = {"Total"}

    top = df[df[col] != "Total"].groupby(col)["value"].sum()
    keep.update(top.nlargest(MIGRATION_TOP_CITIZENSHIPS).index)

    slim = df[df[col].isin(keep)]
    slim.to_csv(dst, index=False, encoding="utf-8")
    print(f"  移民      {before:,}行 → {len(slim):,}行   "
          f"{show_size(src)} → {show_size(dst)}")


def copy_as_is(src: Path, dst: Path) -> None:
    """そのままコピーする(もともと小さいファイル用)"""
    shutil.copyfile(src, dst)
    print(f"  そのまま  {src.name}   {show_size(dst)}")


def main() -> int:
    if not SOURCE_DIR.exists():
        print("data フォルダがありません。先に各 fetcher を実行してください。")
        return 1

    print("公開用データを作成します...\n")

    # 出力先を作り直します(古いファイルが残らないように)
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    total_before = 0
    for src in sorted(SOURCE_DIR.rglob("*")):
        if not src.is_file():
            continue

        total_before += src.stat().st_size
        dst = OUTPUT_DIR / src.relative_to(SOURCE_DIR)
        dst.parent.mkdir(parents=True, exist_ok=True)

        if src.name.startswith("trade_balance_"):
            slim_trade(src, dst)
        elif src.name.startswith("industry_linkages_"):
            slim_industry(src, dst)
        elif src.name.startswith("energy_imports_"):
            slim_energy(src, dst)
        elif src.name.startswith("migration_flow_"):
            slim_migration(src, dst)
        elif src.suffix == ".csv" or src.suffix == ".json":
            copy_as_is(src, dst)

    total_after = sum(p.stat().st_size for p in OUTPUT_DIR.rglob("*") if p.is_file())
    print(f"\n合計  {total_before / 1024 / 1024:.1f} MB "
          f"→ {total_after / 1024 / 1024:.1f} MB")

    # GitHub に置けない大きさのファイルが残っていないか点検します
    too_big = [p for p in OUTPUT_DIR.rglob("*")
               if p.is_file() and p.stat().st_size > 50 * 1024 * 1024]
    if too_big:
        print("\n[警告] 50MBを超えるファイルがあります(GitHubが警告を出します):")
        for p in too_big:
            print(f"   {show_size(p)}  {p}")
        return 1

    print(f"\n保存先: {OUTPUT_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
