# data/fetcher.py
import ccxt
import pandas as pd


class OHLCVFetcher:
    def __init__(self, exchange_name: str = "binance"):
        exchange_class = getattr(ccxt, exchange_name)
        self.exchange = exchange_class({"enableRateLimit": True})

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df

    @staticmethod
    def timeframe_to_seconds(tf: str) -> int:
        multipliers = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
        return int(tf[:-1]) * multipliers[tf[-1]]


def create_fetcher(name: str):
    """Factory: per-market fetcher selection."""
    if name == "fxcm":
        from data.fxcm_fetcher import FXCMFetcher
        return FXCMFetcher()
    if name == "yf_oil":
        from data.yf_oil_fetcher import YFOilFetcher
        return YFOilFetcher()
    return OHLCVFetcher(name)
