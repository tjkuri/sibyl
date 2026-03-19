from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.live import StockDataStream
from alpaca.trading.stream import TradingStream

from config.settings import AlpacaSettings


class AlpacaClient:
    """Thin wrapper that loads API keys and exposes Alpaca SDK clients as properties."""

    def __init__(self, settings: AlpacaSettings):
        self._settings = settings
        self._trading = TradingClient(
            api_key=settings.api_key,
            secret_key=settings.secret_key,
            paper=settings.paper,
        )
        self._stock_data = StockHistoricalDataClient(
            api_key=settings.api_key,
            secret_key=settings.secret_key,
        )
        self._stock_stream = StockDataStream(
            api_key=settings.api_key,
            secret_key=settings.secret_key,
        )
        self._trade_stream = TradingStream(
            api_key=settings.api_key,
            secret_key=settings.secret_key,
            paper=settings.paper,
        )

    @property
    def trading(self) -> TradingClient:
        return self._trading

    @property
    def stock_data(self) -> StockHistoricalDataClient:
        return self._stock_data

    @property
    def stock_stream(self) -> StockDataStream:
        return self._stock_stream

    @property
    def trade_stream(self) -> TradingStream:
        return self._trade_stream

    @property
    def is_paper(self) -> bool:
        return self._settings.paper
