# ⚽ サッカーイベント ウォッチャー

指定したサッカークラブ・選手の「直接サインをもらえる系イベント」(公開練習・サイン会・トークショーなど)の情報を、GitHub Actions が毎日自動でネット上から収集し、GitHub Pages の一覧ページに表示する **完全無料** のシステムです。メルカリ・ヤフオクなどの購入・転売系サイトは自動的に除外されます。

## 仕組み

毎日朝7時(日本時間)に GitHub Actions が起動し、GoogleニュースRSS(APIキー不要)からクラブ名×イベント語で検索します。転売サイトのドメインや転売系ワードを含む結果を除外し、地域名またはクラブ名を含むものだけを採用して `docs/index.html` を生成します。生成されたページは GitHub Pages でそのままWebサイトとして公開されます。過去に検出した情報も60日間は一覧に残り続けます(重複は自動排除)。

## セットアップ手順(所要時間: 約10分)

### 手順1: GitHubアカウントでリポジトリを作る

1. https://github.com にログインします(アカウントがなければ無料で作成)。
2. 右上の「+」→「New repository」をクリックします。
3. Repository name に好きな名前(例: `soccer-event-watcher`)を入力します。
4. **Public** を選びます(無料プランでGitHub Pagesを使うにはPublicが必要です。URLを知らない人が偶然たどり着くことはほぼありませんが、完全非公開にしたい場合はGitHub Pro等の有料プランでPrivate + Pagesが使えます)。
5. 「Create repository」をクリックします。

### 手順2: このフォルダの中身をアップロードする

1. 作成したリポジトリのページで「uploading an existing file」というリンクをクリックします。
2. このフォルダの中身(`build_dashboard.py`、`config.json`、`requirements.txt`、`.github` フォルダごと)をすべてドラッグ&ドロップします。
   - ※ブラウザのアップロードで `.github` フォルダがうまく上がらない場合は、「Add file」→「Create new file」でファイル名欄に `.github/workflows/deploy.yml` と入力し(スラッシュを打つと自動でフォルダになります)、deploy.yml の中身を貼り付けてください。
3. 下の「Commit changes」ボタンを押します。

### 手順3: GitHub Actionsに書き込み許可を与える

1. リポジトリの「Settings」タブ →左メニュー「Actions」→「General」を開きます。
2. 一番下の「Workflow permissions」で **「Read and write permissions」** を選び、「Save」を押します。
   (これがないと、生成したHTMLをActionsがリポジトリに保存できません)

### 手順4: 1回目を手動で実行する

1. リポジトリの「Actions」タブを開きます。
2. 「I understand my workflows, go ahead and enable them」と出たらクリックして有効化します。
3. 左の「イベント情報の収集とページ更新」→右側の「Run workflow」→緑のボタンを押します。
4. 1〜2分待つと緑のチェックマーク✅が付きます。これで `docs/index.html` が自動生成されました。

### 手順5: GitHub Pagesを有効にする(Web画面の公開)

1. 「Settings」タブ →左メニュー「Pages」を開きます。
2. 「Build and deployment」の Source が **「Deploy from a branch」** になっていることを確認します。
3. Branch のところで **`main`** を選び、フォルダは **`/docs`** を選んで「Save」を押します。
4. 1〜2分待ってからページを再読み込みすると、上部に
   `Your site is live at https://あなたのユーザー名.github.io/リポジトリ名/`
   と表示されます。このURLがあなた専用の一覧ページです。ブックマークしておきましょう。

これで完了です。以後は毎朝7時に自動で最新情報に更新されます。

## クラブ名や地域を変更したいとき

リポジトリ上で `config.json` を開き、鉛筆アイコン(Edit)で編集して保存するだけです。

| 設定項目 | 説明 |
|---|---|
| `keywords` | 追いかけたいクラブ名・選手名のリスト |
| `regions` | 絞り込みに使う地域名(関東圏の都県名など) |
| `event_words` | 「イベントらしさ」の判定に使う単語 |
| `exclude_domains` | 100%除外する転売・EC系サイトのドメイン |
| `exclude_words` | この単語を含む結果は除外(「落札」「買取」など) |
| `retention_days` | 一覧に情報を残す日数(初期値60日) |

保存した翌朝の自動実行から新しい設定が反映されます。すぐ反映したい場合は手順4と同じく「Run workflow」で手動実行してください。

## (任意)Google Custom Search APIで検索範囲を広げる

標準のGoogleニュースRSSだけでも動作しますが、ニュース以外のブログ・公式サイトも検索対象にしたい場合は、Google Custom Search API(無料枠: 1日100クエリ)を追加できます。

1. Google Cloud Console で「Custom Search API」を有効化し、APIキーを取得します。
2. https://programmablesearchengine.google.com で検索エンジンを作成し(「ウェブ全体を検索」をオン)、検索エンジンID(cx)を控えます。
3. リポジトリの「Settings」→「Secrets and variables」→「Actions」→「New repository secret」で以下の2つを登録します。
   - Name: `GOOGLE_API_KEY` / Secret: 取得したAPIキー
   - Name: `GOOGLE_CSE_ID` / Secret: 検索エンジンID

登録するだけで次回実行から自動的に併用されます。未登録でもエラーにはなりません。

## よくある質問

**Q. 本当に無料ですか?**
はい。GitHub Actions(Publicリポジトリは無制限無料)、GitHub Pages(無料)、GoogleニュースRSS(無料)のみで構成されています。Custom Search APIも無料枠内の利用です。

**Q. 更新時刻を変えたい**
`.github/workflows/deploy.yml` の `cron: "0 22 * * *"` を編集します。UTC表記なので日本時間−9時間で指定します(例: 日本時間12時 → `"0 3 * * *"`)。

**Q. 実行が失敗した(赤い×が付いた)**
Actionsタブから該当の実行を開くとログが見られます。多くの場合は手順3の権限設定漏れです。

**Q. ページに何も表示されない**
その日に条件に合う情報が見つからなかった場合は「まだイベント情報が見つかっていません」と表示されます。`config.json` の `event_words` や `regions` を増やすとヒットしやすくなります。
