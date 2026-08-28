"""
EUダッシュボード データ更新ランナー

3つの取得スクリプトを順番に実行し、結果をログファイルに記録します。
run_all.bat から呼び出されますが、単体でも実行できます。

    python run_all.py

【なぜ .bat ではなくPythonで書いているか】
Windowsのバッチファイル(.bat)は日本語を含むと文字コードの問題で
正しく動かないことがあります。そこで .bat は最小限にして、
実際の処理と日本語のログはこちらのPythonで書いています。

ログの場所:
    logs/run_YYYYMMDD_HHMMSS.log   … 実行ごとのログ
    logs/latest.log                … 最新の実行のログ(いつも同じ名前)
"""

import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# --- 実行するスクリプト(表示名, ファイル名)を、実行したい順に並べます ---
# ここに1行足すだけで、新しいスクリプトを毎日の実行に追加できます。
SCRIPTS = [
    ("貿易・エネルギー・移民", "eurostat_trade_fetcher_v2.py"),
    ("産業のつながり", "eurostat_industry_fetcher_v2.py"),
    ("国際比較(World Bank)", "worldbank_comparison_fetcher.py"),
    ("ニュース・動画", "eu_news_fetcher_v2.py"),
]

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"

# ログを残しておく日数。これより古いログは自動で削除します
LOG_KEEP_DAYS = 30

# 1つのスクリプトがこの秒数を超えたら、異常とみなして打ち切ります(30分)
SCRIPT_TIMEOUT = 1800


class Logger:
    """画面とログファイルの両方に書き出すための小さな仕組み"""

    def __init__(self, path: Path):
        self.path = path
        self.file = open(path, "w", encoding="utf-8")

    def write(self, text: str = "") -> None:
        print(text)
        self.file.write(text + "\n")
        self.file.flush()   # 途中で止まってもログが残るように、毎回書き込みます

    def close(self) -> None:
        self.file.close()


def cleanup_old_logs(log: Logger) -> None:
    """古いログファイルを削除する"""
    limit = datetime.now() - timedelta(days=LOG_KEEP_DAYS)
    removed = 0
    for old in LOG_DIR.glob("run_*.log"):
        try:
            if datetime.fromtimestamp(old.stat().st_mtime) < limit:
                old.unlink()
                removed += 1
        except OSError:
            pass
    if removed:
        log.write(f"古いログを{removed}件削除しました({LOG_KEEP_DAYS}日より前)")


def run_script(log: Logger, title: str, filename: str) -> bool:
    """
    スクリプトを1本実行する。成功したら True を返す。
    スクリプトの出力(print した内容)は、そのままログに書き写します。
    """
    log.write("")
    log.write("-" * 58)
    log.write(f">>> {title}  ({filename})")
    log.write("-" * 58)

    script_path = BASE_DIR / filename
    if not script_path.exists():
        log.write(f"[エラー] ファイルが見つかりません: {filename}")
        return False

    started = time.time()
    try:
        # sys.executable は「いま動いているPython」を指します。
        # こう書いておくと、Pythonの場所が変わっても直す必要がありません。
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",   # 読めない文字があっても止まらないようにする
            timeout=SCRIPT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        log.write(f"[失敗] {filename} が{SCRIPT_TIMEOUT}秒を超えたため打ち切りました")
        return False

    # スクリプトが出力した内容を、そのままログに残します
    if result.stdout:
        for line in result.stdout.rstrip().splitlines():
            log.write("    " + line)
    if result.stderr:
        log.write("    --- エラー出力 ---")
        for line in result.stderr.rstrip().splitlines():
            log.write("    " + line)

    elapsed = time.time() - started
    if result.returncode == 0:
        log.write(f"[成功] {filename}  ({elapsed:.1f}秒)")
        return True

    log.write(f"[失敗] {filename}  終了コード={result.returncode}  ({elapsed:.1f}秒)")
    return False


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"run_{stamp}.log"

    log = Logger(log_path)
    started = time.time()

    log.write("=" * 58)
    log.write(" EUダッシュボード データ更新")
    log.write(f" 開始: {datetime.now():%Y年%m月%d日 %H:%M:%S}")
    log.write(f" 使用するPython: {sys.executable}")
    log.write("=" * 58)

    failed = []
    for title, filename in SCRIPTS:
        if not run_script(log, title, filename):
            failed.append(filename)

    elapsed = time.time() - started
    log.write("")
    log.write("=" * 58)
    log.write(f" 終了: {datetime.now():%Y年%m月%d日 %H:%M:%S}  "
              f"(所要 {elapsed / 60:.1f}分)")
    if failed:
        log.write(f" 結果: {len(failed)}件が失敗しました → {', '.join(failed)}")
    else:
        log.write(f" 結果: {len(SCRIPTS)}件すべて正常に完了しました")
    log.write("=" * 58)

    cleanup_old_logs(log)
    log.close()

    # 最新のログを latest.log という決まった名前でも残しておきます。
    # 「とりあえず最新の結果を見たい」ときに、この1つを開けば済みます。
    try:
        shutil.copyfile(log_path, LOG_DIR / "latest.log")
    except OSError:
        pass

    # 失敗があれば 0 以外を返します。
    # タスクスケジューラの「前回の実行結果」に異常として表示されます。
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
