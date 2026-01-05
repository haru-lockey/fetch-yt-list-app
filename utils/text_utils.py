import re
from datetime import datetime
from typing import Optional

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}")


def extract_emails(text: Optional[str]) -> str:
    """テキストからメールアドレスを抽出し、カンマ区切りで返します。"""
    if not text:
        return ""
    matches = EMAIL_PATTERN.findall(text)
    return ", ".join(sorted(set(matches)))


def parse_int(text: str, default: int, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    """整数を安全にパースし、範囲指定があればクランプします。失敗時はデフォルトを返します。"""
    try:
        value = int(text)
    except (TypeError, ValueError):
        return default
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


def to_datetime(iso_str: Optional[str]) -> Optional[datetime]:
    """ISO形式に近い文字列を datetime に変換します。失敗時は None を返します。"""
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return None
