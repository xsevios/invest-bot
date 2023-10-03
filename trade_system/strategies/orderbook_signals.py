import logging
import datetime
import numpy as np
from statistics import median
from decimal import Decimal
from typing import Optional

from tinkoff.invest import OrderBook, HistoricCandle, Order
from tinkoff.invest.utils import quotation_to_decimal

from configuration.settings import StrategySettings
from trade_system.signal import Signal, SignalType
from trade_system.strategies.base_strategy import IStrategy

__all__ = ("OrderBookSignals")

logger = logging.getLogger(__name__)
SIGNAL_FREQUENCY: datetime.timedelta = datetime.timedelta(milliseconds=200)

class OrderBookSignals(IStrategy):
    """
    Example of trade strategy.
    IMPORTANT: DO NOT USE IT FOR REAL TRADING!
    """

    def __init__(self, settings: StrategySettings) -> None:
        self.__settings = settings
        self.__recent_orderbooks: list[OrderBook] = []
        self.__last_time_signal: datetime = None
        self.__last_huge_order: Order = Order()

    @property
    def settings(self) -> StrategySettings:
        return self.__settings

    def update_lot_count(self, lot: int) -> None:
        self.__settings.lot_size = lot

    def update_short_status(self, status: bool) -> None:
        self.__settings.short_enabled_flag = status

    def analyze_candles(self, candles: list[HistoricCandle]) -> Optional[Signal]:
        return None

    def analyze_orderbooks(self, orderbook: OrderBook) -> Optional[Signal]:
        self.__recent_orderbooks.append(orderbook)
        now = datetime.datetime.now()

        orders = orderbook.asks + orderbook.bids
        orders.sort(key=lambda order:order.quantity)

        quantities = [order.quantity for order in orders]
        quantity_max = max(quantities)
        quantity_depth = 0
        quantity_90th = np.percentile(quantities, 90)
        bid_ask = ""

        current_huge_order = None
        for order in orders:
            if order.quantity == quantity_max:
                current_huge_order = order

        huge_buy_order = False
        huge_sell_order = False

        for i, bid in enumerate(orderbook.bids[:10]):
            if bid.quantity == quantity_max:
                quantity_depth = i
                bid_ask = "bid"
                huge_buy_order = True

        for i, ask in enumerate(orderbook.asks[:10]):
            if ask.quantity == quantity_max:
                quantity_depth = i
                bid_ask = "ask"
                huge_sell_order = True

        if current_huge_order is None:
            return None

        if quantity_90th * 5 > quantity_max:
            return None

        if huge_sell_order is False and huge_buy_order is False:
            return None

        if self.__last_huge_order is not None and self.__last_huge_order.price != current_huge_order.price:
            self.__last_huge_order = None
            return None

        # continue if current huge order has the same price and lower quantity than previous detected order
        if self.__last_huge_order is not None and (self.__last_huge_order.price == current_huge_order.price and
                                                   self.__last_huge_order.quantity <= current_huge_order.quantity):
            return None

        # continue if quantity difference is less than 10%
        if (self.__last_huge_order is not None and
                self.__last_huge_order.quantity - current_huge_order.quantity < self.__last_huge_order.quantity / 40):
            return None

        prev_huge_order: Order = self.__last_huge_order
        self.__last_time_signal = now
        self.__last_huge_order = current_huge_order
        print(f"Huge order quantity found: "
              f"{self.__settings.ticker}, "
              f"quantity={current_huge_order.quantity}, "
              f"price={quotation_to_decimal(current_huge_order.price)}, "
              f"prev_price={quotation_to_decimal(prev_huge_order.price) if prev_huge_order is not None else ''}, "
              f"depth={quantity_depth}"
          )

        if prev_huge_order is None:
            prev_orderbook = self.__recent_orderbooks[-2] if len(self.__recent_orderbooks) > 1 else None
            prev_orders = prev_orderbook.asks + prev_orderbook.bids

            for prev_order in prev_orders:
                prev_quantity = None

                if prev_order.price == current_huge_order.price:
                    prev_quantity = prev_order.quantity

                return Signal(
                    figi=orderbook.figi,
                    signal_type=SignalType.HUGE_ORDER_APPEARED,
                    quantity=Decimal(quantity_max),
                    prev_quantity=Decimal(prev_quantity),
                    price=quotation_to_decimal(current_huge_order.price),
                    bid_ask=bid_ask,
                )
        else:
            return Signal(
                figi=orderbook.figi,
                signal_type=SignalType.HUGE_ORDER_EAT,
                quantity=Decimal(quantity_max),
                prev_quantity=Decimal(prev_huge_order.quantity),
                price=quotation_to_decimal(current_huge_order.price),
                bid_ask=bid_ask,
            )

    def analyze_all(self, orderbook: OrderBook) -> Optional[Signal]:
        pass