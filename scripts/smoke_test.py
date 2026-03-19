"""Step 1 smoke test: connect to paper account and print balance/buying power."""
import sys
import os

# Allow running from project root without installing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import AlpacaSettings
from src.alpaca_client import AlpacaClient


def main():
    settings = AlpacaSettings()
    client = AlpacaClient(settings)

    mode = "PAPER" if client.is_paper else "LIVE"
    print(f"Connected ({mode})")

    account = client.trading.get_account()
    print(f"  Cash:          ${float(account.cash):,.2f}")
    print(f"  Buying power:  ${float(account.buying_power):,.2f}")
    print(f"  Portfolio:     ${float(account.portfolio_value):,.2f}")
    print(f"  Status:        {account.status}")


if __name__ == "__main__":
    main()
