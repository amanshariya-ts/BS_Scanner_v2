# data/candle_poller.py
import time
import logging
from data.fetcher import OHLCVFetcher

log = logging.getLogger(__name__)

class CandlePoller:
    """Emits each confirmed (closed) candle exactly once."""

    def __init__(self, fetcher: OHLCVFetcher, symbol: str, timeframe: str,
                 interval: int = 5, lookback: int = 200):
        self.fetcher = fetcher
        self.symbol = symbol
        self.timeframe = timeframe
        self.interval = interval
        self.lookback = lookback
        self._last_seen_close_ts = None

    def poll_forever(self):
        tf_secs = OHLCVFetcher.timeframe_to_seconds(self.timeframe)
        while True:
            try:
                df = self.fetcher.fetch_ohlcv(self.symbol, self.timeframe, self.lookback)
                # Exclude the still-open candle; last closed candle:
                closed = df.iloc[:-1]
                if len(closed):
                    latest = closed.iloc[-1]
                    if self._last_seen_close_ts is None or latest.timestamp > self._last_seen_close_ts:
                        if self._last_seen_close_ts is not None:  # skip first-run replay
                            yield latest
                        self._last_seen_close_ts = latest.timestamp
            except Exception as e:
                log.error(f"Poll error: {e}")
            time.sleep(self.interval)
