# fetch-yt-list-app

YouTube Data API v3 を使い、登録者 2,000〜5,000 人の小規模チャンネルを掘り起こし、メールアドレスを抽出して CSV ダウンロードできる Streamlit アプリです。

## セットアップ

```bash
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

## 開発サーバーの起動

```bash
. venv/bin/activate
streamlit run app.py
```

サイドバーに API キーと検索条件を入力し、「検索開始」で処理を実行します。結果は表で表示され、「CSVダウンロード」から `utf-8-sig` で保存できます。

### 主な検索条件
- 検索キーワード（必須）
- 登録者数の範囲（デフォルト 2,000〜5,000）
- 最大検索深さ（ページ数）1〜10（1ページ=最大50件、最大500件）
- 並び替え順（関連度 / 日付 / 視聴回数）
- 最新投稿日が 6 か月以内のチャンネルのみ抽出
- 概要欄のメールアドレス抽出結果を表示（フィルタには未使用）

### .env について
`YOUTUBE_API_KEY` を `.env` に置くと自動で読み込まれ、サイドバーの API キー入力欄に初期表示されます。
