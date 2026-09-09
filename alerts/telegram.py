# alerts/telegram.py
import logging
import os
from datetime import datetime, timezone

import requests

log = logging.getLogger(__name__)

SIDE_STYLES = {
    "BUY": "🟢 Bullish",
    "SELL": "🔴 Bearish",
}


class TelegramAlert:
    def __init__(self, bot_token: str, chat_id: str):
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", bot_token)
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", chat_id)
        token = (bot_token or "").strip()
        self.chat_id = str(chat_id).strip()
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._configured = bool(token) and bool(self.chat_id)
        if not self._configured:
            log.warning("Telegram NOT configured (missing token/chat_id) "
                        "— signals will log but never send")

    def send(self, signal) -> bool:
        """Send one alert. Returns True only if Telegram accepted the message."""
        if not self._configured:
            log.error(f"Cannot send (unconfigured): {signal.side} {signal.symbol} "
                      f"{signal.timeframe} @ {signal.price}")
            return False

        try:
            r = requests.post(self.url, json={
                "chat_id": self.chat_id,
                "text": self._format(signal),
                "disable_web_page_preview": True,
            }, timeout=10)
            r.raise_for_status()
        except Exception as e:
            log.error(f"Telegram send failed: {e}")
            return False

        log.info(f"Telegram sent: {signal.side} {signal.symbol} {signal.timeframe} @ {signal.price}")
        return True

    def _format(self, signal) -> str:
        style = SIDE_STYLES.get(signal.side, "⚪ Signal")
        strategy = getattr(signal, "strategy", "pinbar")
        price = f"{signal.price:,.2f}"
        ts = signal.timestamp.strftime("%Y-%m-%d %H:%M UTC")

        # candle age — tolerant of naive timestamps
        tsdt = signal.timestamp
        if tsdt.tzinfo is None:
            tsdt = tsdt.replace(tzinfo=timezone.utc)
        age_min = (datetime.now(timezone.utc) - tsdt).total_seconds() / 60
        age = f"{age_min / 60:.1f}h old" if age_min >= 60 else f"{age_min:.0f}m old"

        return (
            f"{style} {strategy}\n"
            f"Symbol: {signal.symbol}\n"
            f"Timeframe: {signal.timeframe}\n"
            f"Price: {price}\n"
            f"Candle: {ts} ({age})"
        )
