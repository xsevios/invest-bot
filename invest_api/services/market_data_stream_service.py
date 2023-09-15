import datetime
import logging
from typing import Generator

from tinkoff.invest import Client, CandleInstrument, SubscriptionInterval, InfoInstrument, TradeInstrument, \
    MarketDataResponse, Candle, AsyncClient, OrderBookInstrument
from tinkoff.invest.market_data_stream.async_market_data_stream_manager import AsyncMarketDataStreamManager
from tinkoff.invest.market_data_stream.market_data_stream_interface import IMarketDataStreamManager
from tinkoff.invest.market_data_stream.market_data_stream_manager import MarketDataStreamManager

__all__ = ("MarketDataStreamService")

logger = logging.getLogger(__name__)


class MarketDataStreamService:
    """
    The class encapsulate tinkoff market data stream (gRPC) service api
    """
    def __init__(self, token: str, app_name: str) -> None:
        self.__token = token
        self.__app_name = app_name

    async def start_async_market_data_stream(
            self,
            figies: list[str],
            trade_before_time: datetime
    ) -> Generator[MarketDataResponse, None, None]:
        """
        The method starts async gRPC stream and return candles
        """
        logger.debug(f"Starting async candles stream")

        async with AsyncClient(self.__token, app_name=self.__app_name) as client:
            async_market_data_stream: AsyncMarketDataStreamManager = client.create_market_data_stream()

            logger.info(f"Subscribe candles: {figies}")
            async_market_data_stream.candles.subscribe(
                [
                    CandleInstrument(
                        figi=figi,
                        interval=SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE
                    )
                    for figi in figies
                ]
            )

            async_market_data_stream.order_book.subscribe(
                [
                    OrderBookInstrument(
                        figi=figi,
                        depth=50,
                    )
                    for figi in figies
                ]
            )

            async for market_data in async_market_data_stream:
                logger.debug(f"market_data: {market_data}")

                # trading will stop at trade_before_time
                if datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) >= trade_before_time:
                    logger.debug(f"Time to stop candle stream")
                    self.__stop_candles_stream(async_market_data_stream)
                    break

                if market_data.candle or market_data.orderbook:
                    yield market_data

        self.__stop_candles_stream(async_market_data_stream)

    @staticmethod
    def __stop_candles_stream(stream: IMarketDataStreamManager) -> None:
        if stream:
            logger.info(f"Stopping candles stream")
            stream.stop()