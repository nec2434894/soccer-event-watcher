{
  "_使い方": "★このシステムは『サッカー全般』のイベント情報を集めます。特定クラブへの限定はしません。",

  "_検索の軸": "★sport_keywords(サッカー系の言葉)の いずれか と、event_word_selection(イベント系の言葉)の いずれか を両方含むページを集めます。",
  "sport_keywords": [
    "サッカー",
    "soccer",
    "football",
    "フットボール",
    "Jリーグ",
    "J1",
    "J2",
    "J3"
  ],

  "_キーワード選択": "★どのイベントを対象にするかを true / false で選びます(要件どおり従来のまま保持)。",
  "event_word_selection": {
    "サイン会": true,
    "公開練習": true,
    "ファンサ": true,
    "トークショー": true,
    "握手会": true,
    "お渡し会": true,
    "交流会": true,
    "ファン感謝": true,
    "イベント": true,
    "ファンミーティング": false,
    "サイン対応": false,
    "撮影会": false,
    "出陣式": false,
    "優勝報告会": false
  },

  "_地域フィルター": "★use_region_filter を true にすると、下の地域名を含むものだけに絞り込みます。全国の情報が欲しい場合は false にしてください。",
  "use_region_filter": true,
  "regions": [
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
