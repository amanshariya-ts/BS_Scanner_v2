from data.fetcher import OHLCVFetcher

f = OHLCVFetcher("binance")
df = f.fetch_ohlcv("BTC/USDT", "15m", 10)
print(df)
print("\n✅ Success! Latest BTC price:", df.iloc[-1]["close"])
