"""
英語などの見出しを日本語に翻訳するための小さな道具

deep-translator という無料のライブラリを使って、Google翻訳のWeb版を呼び出します。
APIキーは不要ですが、1件あたり1〜2秒かかるので、
一度翻訳した文はファイルに保存して、次からは再利用します(これをキャッシュと呼びます)。

必要ライブラリ:
    pip install deep-translator
"""

import json
import time
from pathlib import Path

# キャッシュ(翻訳済みの文をためておくファイル)の置き場所
CACHE_PATH = Path("data/news/translation_cache.json")

# 翻訳の間隔(秒)。続けて呼びすぎると相手側に断られることがあるので、少し待ちます
REQUEST_INTERVAL = 0.3
# 失敗したときに何回やり直すか
MAX_RETRIES = 2


def _load_cache() -> dict:
    """保存してある翻訳結果を読み込む。無ければ空の状態から始める"""
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        # ファイルが壊れていても翻訳自体は続けたいので、空から始めます
        return {}


def _save_cache(cache: dict) -> None:
    """翻訳結果をファイルに保存する"""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)


def _is_already_japanese(text: str) -> bool:
    """
    すでに日本語が含まれている文かどうかを調べる。
    ひらがな・カタカナが入っていれば日本語とみなして、翻訳を省きます。
    """
    for ch in text:
        code = ord(ch)
        if 0x3040 <= code <= 0x309F:   # ひらがな
            return True
        if 0x30A0 <= code <= 0x30FF:   # カタカナ
            return True
    return False


def translate_titles(titles: list[str], show_progress: bool = True) -> dict[str, str]:
    """
    見出しのリストを日本語に翻訳して、{元の文: 日本語} の辞書を返す。

    - すでに翻訳したことがある文は、キャッシュから取り出すので通信しません
    - 翻訳に失敗した文は、辞書に入れません(呼び出し側で元の文を使ってください)
    """
    cache = _load_cache()

    # 重複を除き、翻訳が必要なものだけを取り出します
    unique = []
    for t in titles:
        t = (t or "").strip()
        if not t or t in cache or t in unique:
            continue
        if _is_already_japanese(t):
            cache[t] = t  # もともと日本語なのでそのまま
            continue
        unique.append(t)

    if not unique:
        if show_progress:
            print("  翻訳: すべてキャッシュ済み(通信なし)")
        return {k: v for k, v in cache.items() if k in set(titles)}

    if show_progress:
        print(f"  翻訳: {len(unique)}件を新規に翻訳します"
              f"(残りはキャッシュ利用)")

    # deep-translator はここで初めて読み込みます。
    # 未インストールでも、翻訳なしで動作を続けられるようにするためです。
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print("  翻訳: deep-translator が未インストールのため翻訳を省略します")
        print("        pip install deep-translator")
        return {k: v for k, v in cache.items() if k in set(titles)}

    translator = GoogleTranslator(source="auto", target="ja")

    failed = 0
    for i, text in enumerate(unique, start=1):
        result = None
        for attempt in range(MAX_RETRIES):
            try:
                result = translator.translate(text)
                break
            except Exception:
                # 一時的な失敗はやり直します。それでも駄目なら諦めます。
                time.sleep(1.0 * (attempt + 1))

        if result:
            cache[text] = result
        else:
            failed += 1

        if show_progress and i % 25 == 0:
            print(f"    {i}/{len(unique)} 件")

        time.sleep(REQUEST_INTERVAL)

    _save_cache(cache)

    if show_progress:
        done = len(unique) - failed
        print(f"  翻訳: 完了 {done}件 / 失敗 {failed}件"
              f"(失敗した見出しは元の言語のまま表示されます)")

    return {k: v for k, v in cache.items() if k in set(titles)}
