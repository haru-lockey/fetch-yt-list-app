from typing import Callable, List

from googleapiclient.discovery import build


def build_client(api_key: str):
    """APIキーから YouTube Data API クライアントを生成して返します。"""
    return build("youtube", "v3", developerKey=api_key)


def fetch_channels(
    youtube,
    keyword: str,
    max_results: int,
    max_pages: int,
    order: str,
    update_progress: Callable[[str], None],
) -> List[dict]:
    """ページネーションでチャンネル検索を行い、指定件数までの詳細をまとめて返します。"""
    channels: List[dict] = []
    next_page_token = None
    page = 1

    while len(channels) < max_results and page <= max_pages:
        remaining = max_results - len(channels)
        update_progress(f"現在 {page} ページ目を検索中...（{len(channels)} 件ヒット）")
        search_response = (
            youtube.search()
            .list(
                q=keyword,
                type="channel",
                part="id",
                maxResults=min(50, remaining),
                pageToken=next_page_token,
                order=order,
            )
            .execute()
        )

        channel_ids = [item["id"]["channelId"] for item in search_response.get("items", [])]
        if not channel_ids:
            break

        for i in range(0, len(channel_ids), 50):
            batch_ids = channel_ids[i : i + 50]
            details_response = (
                youtube.channels()
                .list(part="snippet,statistics,contentDetails", id=",".join(batch_ids))
                .execute()
            )
            channels.extend(details_response.get("items", []))

        next_page_token = search_response.get("nextPageToken")
        if not next_page_token:
            break
        page += 1

    return channels[:max_results]


def fetch_recent_videos(youtube, channel: dict, max_results: int = 1) -> List[dict]:
    """チャンネルの最近の動画を取得し、最新投稿日などを評価するために返します。"""
    uploads_playlist = (
        channel.get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads")
    )
    if not uploads_playlist:
        return []

    playlist_items = (
        youtube.playlistItems()
        .list(
            playlistId=uploads_playlist,
            part="contentDetails",
            maxResults=max_results,
        )
        .execute()
    ).get("items", [])

    video_ids = [item["contentDetails"]["videoId"] for item in playlist_items if item.get("contentDetails")]
    if not video_ids:
        return []

    videos_response = (
        youtube.videos()
        .list(part="statistics,snippet", id=",".join(video_ids))
        .execute()
    )
    return videos_response.get("items", [])
