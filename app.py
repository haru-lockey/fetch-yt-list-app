import io
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

from services.youtube_service import build_client, fetch_channels, fetch_recent_videos
from utils.text_utils import extract_emails, parse_int, to_datetime


def run_app() -> None:
    """Streamlit UI を描画し、YouTube チャンネル検索とフィルタリングを統括します。"""
    load_dotenv()
    api_key = os.getenv("YOUTUBE_API_KEY", "")

    st.set_page_config(page_title="YouTube チャンネル検索", layout="wide")
    st.title("YouTube チャンネル検索")
    st.caption("登録者数 2,000〜5,000 を中心に小規模チャンネルを掘り起こします。メールアドレスも概要欄から抽出します。")

    with st.sidebar:
        st.header("検索条件")

        api_key_input = st.text_input(
            "YouTube APIキー",
            type="password",
            value=api_key,
            help=".env の YOUTUBE_API_KEY を自動読込します。",
        )
        keyword = st.text_input("検索キーワード")

        st.markdown("**登録者数の範囲**")
        c1, c2 = st.columns(2)
        with c1:
            sub_min_text = st.text_input("最小", value="2000")
        with c2:
            sub_max_text = st.text_input("最大", value="10000")

        max_pages = st.number_input(
            "最大検索深さ (ページ数)", min_value=1, max_value=10, value=10, step=1,
            help="1ページ=最大50件を取得します。"
        )
        order = st.selectbox(
            "並び替え順",
            options=["relevance", "date", "viewCount"],
            format_func=lambda v: {"relevance": "関連度", "date": "日付", "viewCount": "視聴回数"}[v],
        )
        start_search = st.button("検索開始", type="primary", use_container_width=True)

    if not start_search:
        st.info("サイドバーで条件を入力して「検索開始」を押してください。")
        return

    api_key_value = api_key_input.strip()
    if not api_key_value or not keyword:
        st.warning("APIキーと検索キーワードを入力してください。")
        return

    progress_bar = st.progress(0, text="検索中...")
    status = st.empty()
    flow_status = st.status("処理フローを開始します", state="running", expanded=True)
    flow_status.write("1. キーワード検索を実行します。")
    page_info = st.empty()

    sub_min = parse_int(sub_min_text, default=0, min_value=0)
    sub_max = parse_int(sub_max_text, default=1_000_000, min_value=1)
    max_results = int(max_pages * 50)

    if sub_min > sub_max:
        st.warning("登録者数の最小値が最大値を超えています。値を見直してください。")
        return

    try:
        channels = fetch_channels(
            api_key=api_key_value,
            keyword=keyword,
            max_results=max_results,
            max_pages=int(max_pages),
            order=order,
            update_progress=lambda msg: page_info.info(msg),
        )
    except HttpError as exc:
        st.error(f"API呼び出しでエラーが発生しました: {exc}")
        flow_status.update(label="APIエラー", state="error")
        return
    except Exception as exc:  # noqa: BLE001
        st.error(f"予期しないエラーが発生しました: {exc}")
        flow_status.update(label="予期しないエラー", state="error")
        return

    total = len(channels)
    flow_status.write(f"検索結果: {total} 件のチャンネルが見つかりました。")

    with st.expander("取得したチャンネル一覧 (検索結果)", expanded=False):
        preview_rows = [
            {
                "チャンネル名": item.get("snippet", {}).get("title", ""),
                "チャンネルID": item.get("id", ""),
            }
            for item in channels
        ]
        if preview_rows:
            st.dataframe(pd.DataFrame(preview_rows), hide_index=True, use_container_width=True)
        else:
            st.write("検索結果なし")

    results = []
    filtered_out = 0
    if total == 0:
        progress_bar.empty()
        flow_status.update(label="結果なし", state="error")
        st.info("検索結果がありませんでした。キーワードや件数を変更して再試行してください。")
        return

    flow_status.write("2. チャンネル詳細と最新動画を取得してフィルタリングします。")

    youtube = build_client(api_key_value)
    recency_months = 6
    latest_threshold = datetime.now(timezone.utc) - timedelta(days=30 * recency_months)

    for idx, channel in enumerate(channels, start=1):
        stats = channel.get("statistics", {})
        snippet = channel.get("snippet", {})
        subs_str = stats.get("subscriberCount")

        try:
            subs = int(subs_str) if subs_str is not None else None
        except ValueError:
            subs = None

        description = snippet.get("description", "")
        emails = extract_emails(description)

        # チャンネルによっては登録者数が非公開の場合があるため、その場合は除外する。
        if subs is None or subs < sub_min or subs > sub_max:
            progress_bar.progress(idx / total, text=f"登録者数で除外... ({idx}/{total})")
            filtered_out += 1
            continue

        recent_videos = fetch_recent_videos(youtube, channel, max_results=1)
        latest_video_date = None
        if recent_videos:
            published_dates = [to_datetime(v.get("snippet", {}).get("publishedAt")) for v in recent_videos]
            published_dates = [d for d in published_dates if d]
            latest_video_date = max(published_dates) if published_dates else None

        if not latest_video_date or latest_video_date < latest_threshold:
            progress_bar.progress(idx / total, text=f"更新が6か月より古いので除外... ({idx}/{total})")
            filtered_out += 1
            continue

        channel_view_count = int(stats.get("viewCount", 0)) if stats.get("viewCount") else 0
        channel_id = channel.get("id", "")
        results.append(
            {
                "チャンネル名": snippet.get("title", ""),
                "チャンネルID": channel_id,
                "チャンネルURL": f"https://www.youtube.com/channel/{channel_id}" if channel_id else "",
                "登録者数": subs,
                "総再生回数": channel_view_count,
                "最新投稿日": latest_video_date.date().isoformat() if latest_video_date else "",
                "概要欄": description,
                "抽出メールアドレス": emails,
            }
        )
        progress_bar.progress(idx / total, text=f"処理中... ({idx}/{total})")
        status.write(f"処理中: {snippet.get('title', '不明')} を処理しました。")

    progress_bar.empty()

    if not results:
        st.warning("指定した登録者数の範囲に一致するチャンネルが見つかりませんでした。")
        flow_status.update(label="フィルタ結果: 0 件", state="error")
        return

    passed = len(results)
    flow_status.write(f"フィルタ通過: {passed} 件 / 除外: {filtered_out} 件")
    flow_status.update(label="処理フロー完了", state="complete")

    df = pd.DataFrame(results)
    st.subheader("抽出結果")
    st.dataframe(df, use_container_width=True, hide_index=True)

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    st.download_button(
        label="CSVダウンロード",
        data=csv_buffer.getvalue(),
        file_name="youtube_channels.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    run_app()
