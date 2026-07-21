#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dashboard.py
------------------
サッカークラブ・選手の「直接サインをもらえる系イベント」情報を
ネット上から収集し、GitHub Pages 用の一覧 HTML を生成するスクリプト。

情報源:
  1. Google ニュース RSS 検索  … APIキー不要・完全無料(標準)
  2. Google Custom Search API  … 環境変数 GOOGLE_API_KEY / GOOGLE_CSE_ID が
                                  設定されている場合のみ追加で利用(任意)

出力:
  data/events.json … 収集済みイベントの蓄積データ(重複排除・履歴保持用)
  docs/index.html  … GitHub Pages で公開される一覧ページ
"""

import html
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

# ---------------------------------------------------------------- 基本設定
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
DATA_PATH = BASE_DIR / "data" / "events.json"
HTML_PATH = BASE_DIR / "docs" / "index.html"

JST = timezone(timedelta(hours=9))
USER_AGENT = "Mozilla/5.0 (compatible; FanEventDashboard/1.0)"

# Google ニュース RSS 検索エンドポイント
GNEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"

# Google Custom Search API(任意)
GCS_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID", "").strip()


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)

    # --- 選択式(チェックボックス形式)の設定を展開 ---
    # event_word_selection の中で true のものだけを採用する。
    if isinstance(cfg.get("event_word_selection"), dict):
        cfg["event_words"] = [w for w, on in cfg["event_word_selection"].items() if on]

    # サッカー全般キーワード(必須)。旧形式(club_selection)が残っていても無視する。
    cfg["sport_keywords"] = cfg.get("sport_keywords") or ["サッカー"]

    if not cfg.get("event_words"):
        sys.exit("ERROR: イベント語が1つも選択されていません。config.json の event_word_selection を確認してください。")
    if not cfg.get("sport_keywords"):
        sys.exit("ERROR: sport_keywords が空です。config.json に検索の軸となるサッカー系の語を設定してください。")

    return cfg


def load_stored_events() -> dict:
    """URL をキーにした既存イベント辞書を読み込む。"""
    if DATA_PATH.exists():
        try:
            with open(DATA_PATH, encoding="utf-8") as f:
                return {e["url"]: e for e in json.load(f)}
        except (json.JSONDecodeError, KeyError):
            print("WARN: data/events.json が壊れているため作り直します")
    return {}


# ---------------------------------------------------------------- フィルタ
def domain_of(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except ValueError:
        return ""


def is_excluded_domain(url: str, exclude_domains: list) -> bool:
    d = domain_of(url)
    return any(d == ex or d.endswith("." + ex) for ex in exclude_domains)


def passes_filters(title: str, snippet: str, url: str, cfg: dict) -> bool:
    """要件どおりのノイズカットを行う。True = 採用。"""
    text = f"{title} {snippet}"

    # 1) 転売・オークション系ドメインは 100% 除外
    if is_excluded_domain(url, cfg["exclude_domains"]):
        return False

    # 2) 転売っぽいワードを含むものを除外
    if any(w in text for w in cfg.get("exclude_words", [])):
        return False

    # 3) イベント系ワードを最低 1 つ含むこと
    if not any(w in text for w in cfg["event_words"]):
        return False

    # 4) サッカー系ワードを最低 1 つ含むこと(クラブ限定はしない)
    if not any(k.lower() in text.lower() for k in cfg["sport_keywords"]):
        return False

    # 5) 地域フィルターが ON のときだけ、地域名で絞り込む
    if cfg.get("use_region_filter", True):
        if not any(r in text for r in cfg.get("regions", [])):
            return False

    return True


# ---------------------------------------------------------------- 収集
def search_google_news(sport_kw: str, cfg: dict) -> list:
    """Google ニュース RSS で サッカー語×イベント語 を検索する。"""
    results = []
    # クエリ例: サッカー (サイン会 OR 公開練習 OR ...) -site:mercari.com ...
    event_part = " OR ".join(cfg["event_words"])
    minus_part = " ".join(f"-site:{d}" for d in cfg["exclude_domains"][:8])
    query = f'{sport_kw} ({event_part}) {minus_part}'
    url = GNEWS_RSS.format(query=urllib.parse.quote(query))

    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except (requests.RequestException, ET.ParseError) as e:
        print(f"WARN: RSS取得失敗 ({sport_kw}): {e}")
        return []

    for item in root.iter("item"):
        if len(results) >= cfg.get("max_results_per_query", 20):
            break
        title = html.unescape(item.findtext("title", default=""))
        link = (item.findtext("link", default="") or "").strip()
        snippet = re.sub(r"<[^>]+>", "", item.findtext("description", default=""))
        pub_iso = None
        pub_raw = item.findtext("pubDate")
        if pub_raw:
            try:
                pub_iso = parsedate_to_datetime(pub_raw).astimezone(JST).isoformat()
            except (ValueError, TypeError):
                pass
        results.append(
            {
                "title": title,
                "url": link,
                "snippet": html.unescape(snippet)[:300],
                "published": pub_iso,
                "source": "GoogleニュースRSS",
            }
        )
    return results


def search_custom_search(sport_kw: str, cfg: dict) -> list:
    """Google Custom Search API(キーがある場合のみ)。無料枠: 100クエリ/日。"""
    if not (GOOGLE_API_KEY and GOOGLE_CSE_ID):
        return []

    event_part = " OR ".join(cfg["event_words"][:5])
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": f"{sport_kw} ({event_part})",
        "num": 10,
        "lr": "lang_ja",
        "dateRestrict": "m1",  # 直近1か月
    }
    try:
        r = requests.get(GCS_ENDPOINT, params=params, timeout=20)
        r.raise_for_status()
        items = r.json().get("items", [])
    except requests.RequestException as e:
        print(f"WARN: Custom Search API 失敗 ({sport_kw}): {e}")
        return []

    return [
        {
            "title": it.get("title", ""),
            "url": it.get("link", ""),
            "snippet": it.get("snippet", "")[:300],
            "published": None,
            "source": "Google検索",
        }
        for it in items
    ]


def detect_matched_keyword(text: str, cfg: dict) -> str:
    """本文中に登場したサッカー系ワードを1つ返す(一覧の分類ラベル用)。"""
    for k in cfg["sport_keywords"]:
        if k.lower() in text.lower():
            return k
    return "サッカー"


def collect(cfg: dict) -> dict:
    """全サッカー系ワードを検索し、フィルタ済みイベントを URL キーの辞書で返す。"""
    now_iso = datetime.now(JST).isoformat()
    found = {}

    for sport_kw in cfg["sport_keywords"]:
        raw = []
        raw += search_google_news(sport_kw, cfg)
        raw += search_custom_search(sport_kw, cfg)
        time.sleep(1)  # 連続アクセスを控えめに

        accepted = 0
        for item in raw:
            if not item["url"]:
                continue
            if not passes_filters(item["title"], item["snippet"], item["url"], cfg):
                continue
            if item["url"] in found:
                continue
            label = detect_matched_keyword(f'{item["title"]} {item["snippet"]}', cfg)
            found[item["url"]] = {
                "url": item["url"],
                "title": item["title"],
                "snippet": item["snippet"],
                "keyword": label,
                "source": item["source"],
                "published": item["published"],
                "first_seen": now_iso,
            }
            accepted += 1
        print(f"  {sport_kw}: 取得 {len(raw)} 件 → 採用 {accepted} 件")

    return found


# ---------------------------------------------------------------- 保存
def merge_and_prune(stored: dict, new: dict, cfg: dict) -> list:
    """既存データに新規分を追加し、保持期間を過ぎたものを削除して返す。"""
    for url, ev in new.items():
        if url not in stored:  # 既存は first_seen を維持
            stored[url] = ev

    cutoff = datetime.now(JST) - timedelta(days=cfg.get("retention_days", 60))
    merged = [
        ev
        for ev in stored.values()
        if datetime.fromisoformat(ev["first_seen"]) >= cutoff
    ]
    merged.sort(key=lambda e: e["first_seen"], reverse=True)  # 新しい順
    return merged


# ---------------------------------------------------------------- HTML 生成
def fmt_jst(iso_str: str) -> str:
    try:
        return datetime.fromisoformat(iso_str).astimezone(JST).strftime("%Y/%m/%d %H:%M")
    except (ValueError, TypeError):
        return "-"


def build_html(events: list, cfg: dict) -> str:
    updated = datetime.now(JST).strftime("%Y/%m/%d %H:%M")
    site_title = html.escape(cfg.get("site_title", "サッカーイベント ウォッチャー"))
    region_note = "関東エリア" if cfg.get("use_region_filter", True) else "全国"
    keywords_label = f"サッカー全般({region_note})"

    rows = []
    for ev in events:
        rows.append(f"""
        <tr>
          <td class="text-nowrap detected">{fmt_jst(ev["first_seen"])}</td>
          <td><span class="badge club-badge">{html.escape(ev["keyword"])}</span></td>
          <td>
            <a href="{html.escape(ev["url"], quote=True)}" target="_blank" rel="noopener noreferrer" class="event-link">
              {html.escape(ev["title"])}
            </a>
            <div class="snippet">{html.escape(ev["snippet"])}</div>
          </td>
          <td class="text-nowrap source">{html.escape(ev["source"])}</td>
        </tr>""")

    table_body = "".join(rows) if rows else """
        <tr><td colspan="4" class="empty">まだイベント情報が見つかっていません。次回の自動更新をお待ちください。</td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{site_title}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  :root {{
    --pitch: #1d6b3f;
    --pitch-dark: #14502e;
    --line: #e9e4d8;
  }}
  body {{
    background: #f7f6f2;
    font-family: "Hiragino Kaku Gothic ProN", "Yu Gothic", Meiryo, sans-serif;
    color: #22301f;
  }}
  .hero {{
    background: linear-gradient(135deg, var(--pitch) 0%, var(--pitch-dark) 100%);
    color: #fff;
    padding: 2.2rem 0 1.8rem;
    border-bottom: 6px solid #ffffff;
    box-shadow: inset 0 -12px 0 rgba(255,255,255,.12);
  }}
  .hero h1 {{ font-size: 1.6rem; font-weight: 700; letter-spacing: .04em; margin: 0; }}
  .hero .meta {{ opacity: .85; font-size: .85rem; margin-top: .4rem; }}
  .card-table {{
    background: #fff; border: 1px solid var(--line); border-radius: .75rem;
    overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,.05);
  }}
  thead th {{
    background: #f2f0ea; font-size: .8rem; letter-spacing: .05em;
    border-bottom: 2px solid var(--pitch) !important;
  }}
  .club-badge {{ background: var(--pitch); font-weight: 600; }}
  .event-link {{ color: #14502e; font-weight: 600; text-decoration: none; }}
  .event-link:hover {{ text-decoration: underline; }}
  .snippet {{ font-size: .8rem; color: #6b6f66; margin-top: .2rem; }}
  .detected, .source {{ font-size: .85rem; color: #4a4f45; }}
  .empty {{ text-align: center; color: #8a8f83; padding: 3rem 1rem !important; }}
  footer {{ font-size: .78rem; color: #8a8f83; padding: 1.5rem 0 2.5rem; }}
</style>
</head>
<body>
  <header class="hero">
    <div class="container">
      <h1>⚽ {site_title}</h1>
      <div class="meta">
        対象: {keywords_label}<br>
        最終更新: {updated}(毎日自動更新)/ 掲載件数: {len(events)} 件
      </div>
    </div>
  </header>

  <main class="container my-4">
    <div class="card-table">
      <table class="table table-hover align-middle mb-0">
        <thead>
          <tr>
            <th style="width:11rem">検出日時</th>
            <th style="width:10rem">区分</th>
            <th>イベント概要(クリックで元ページへ)</th>
            <th style="width:9rem">情報源</th>
          </tr>
        </thead>
        <tbody>{table_body}
        </tbody>
      </table>
    </div>
  </main>

  <footer class="container">
    このページは GitHub Actions により毎日自動生成されています。
    リンク先の内容(開催日時・参加条件など)は必ず公式サイトでご確認ください。
    購入・オークション系サイトの情報は自動的に除外しています。
  </footer>
</body>
</html>
"""


# ---------------------------------------------------------------- メイン
def main() -> int:
    cfg = load_config()
    print(f"== 収集開始: {datetime.now(JST).strftime('%Y/%m/%d %H:%M')} JST ==")
    if GOOGLE_API_KEY and GOOGLE_CSE_ID:
        print("Custom Search API: 有効")
    else:
        print("Custom Search API: 未設定(GoogleニュースRSSのみで動作します)")

    stored = load_stored_events()
    new = collect(cfg)
    events = merge_and_prune(stored, new, cfg)

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=1)

    HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(build_html(events, cfg))

    print(f"== 完了: 掲載 {len(events)} 件(新規 {sum(1 for u in new if u not in stored or stored[u]['first_seen'] == new[u]['first_seen'])} 件前後) ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
    "東京", "埼玉", "さいたま", "神奈川", "横浜", "千葉",
    "茨城", "栃木", "群馬", "関東"
  ],

  "exclude_domains": [
    "mercari.com",
    "jp.mercari.com",
    "auctions.yahoo.co.jp",
    "paypayfleamarket.yahoo.co.jp",
    "shopping.yahoo.co.jp",
    "fril.jp",
    "rakuma.rakuten.co.jp",
    "item.rakuten.co.jp",
    "search.rakuten.co.jp",
    "amazon.co.jp",
    "ebay.com",
    "aucfan.com",
    "snkrdunk.com",
    "magi.camp",
    "otamart.com",
    "suruga-ya.jp",
    "bookoff.co.jp",
    "2ndstreet.jp"
  ],

  "exclude_words": [
    "落札", "出品中", "即決価格", "送料無料", "買取", "転売"
  ],

  "_保持日数": "★この日数より古い情報は毎日の実行時に自動削除されます(容量削減)。",
  "retention_days": 3,

  "max_results_per_query": 30,
  "site_title": "サッカーイベント ウォッチャー"
}
