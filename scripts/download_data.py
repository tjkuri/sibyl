"""Download historical bar data and save as parquet files."""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import AppSettings
from src.alpaca_client import AlpacaClient
from src.data.live_provider import LiveDataProvider


async def download(symbols: list[str], start: str, end: str, timeframe: str, data_dir: str) -> None:
    settings = AppSettings()
    client = AlpacaClient(settings.alpaca)
    provider = LiveDataProvider(client)

    os.makedirs(data_dir, exist_ok=True)

    df = await provider.get_bars(symbols, timeframe, start, end)

    for symbol in symbols:
        try:
            symbol_df = df.loc[symbol]
        except KeyError:
            print(f"WARNING: no data returned for {symbol}")
            continue

        path = os.path.join(data_dir, f"{symbol}_{timeframe}.parquet")
        symbol_df.to_parquet(path)
        print(f"Saved {len(symbol_df)} rows to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download historical bar data from Alpaca")
    parser.add_argument("--symbols", nargs="+", required=True, help="Ticker symbols, e.g. AAPL SPY")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--timeframe", default="1Day", help="Bar timeframe (default: 1Day)")
    parser.add_argument("--data-dir", default=None, help="Output directory (default: AppSettings.data_dir)")
    args = parser.parse_args()

    data_dir = args.data_dir if args.data_dir else AppSettings().data_dir
    asyncio.run(download(args.symbols, args.start, args.end, args.timeframe, data_dir))


if __name__ == "__main__":
    main()
