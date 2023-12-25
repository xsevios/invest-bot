import logging
from decimal import Decimal
from typing import Optional

from tinkoff.invest import HistoricCandle, OrderBook
from tinkoff.invest.utils import quotation_to_decimal

from configuration.settings import StrategySettings
from trade_system.signal import Signal, SignalType
from trade_system.strategies.base_strategy import IStrategy

import joblib, pickle
import pandas as pd

__all__ = ("MlStrategy")

logger = logging.getLogger(__name__)

model = joblib.load('research/models/automl_model_v1.pkl')

class MlStrategy(IStrategy):
    """
    ML based trade strategy.
    """

    def analyze_all(self, orderbook: OrderBook) -> Optional[Signal]:
        pass

    def analyze_orderbooks(self, candles: list[HistoricCandle]) -> Optional[Signal]:
        pass

    # Consts for read and parse dict with strategy configuration

    __SIGNAL_VOLUME_NAME = "SIGNAL_VOLUME"
    __SIGNAL_MIN_CANDLES_NAME = "SIGNAL_MIN_CANDLES"
    __LONG_TAKE_NAME = "LONG_TAKE"
    __LONG_STOP_NAME = "LONG_STOP"
    __SHORT_TAKE_NAME = "SHORT_TAKE"
    __SHORT_STOP_NAME = "SHORT_STOP"
    __SIGNAL_MIN_TAIL_NAME = "SIGNAL_MIN_TAIL"

    def __init__(self, settings: StrategySettings) -> None:
        self.__settings = settings

        self.__signal_min_candles = int(settings.settings[self.__SIGNAL_MIN_CANDLES_NAME])

        self.__long_take = Decimal(settings.settings[self.__LONG_TAKE_NAME])
        self.__long_stop = Decimal(settings.settings[self.__LONG_STOP_NAME])

        self.__short_take = Decimal(settings.settings[self.__SHORT_TAKE_NAME])
        self.__short_stop = Decimal(settings.settings[self.__SHORT_STOP_NAME])

        self.__recent_candles = []

    @property
    def settings(self) -> StrategySettings:
        return self.__settings

    def update_lot_count(self, lot: int) -> None:
        self.__settings.lot_size = lot

    def update_short_status(self, status: bool) -> None:
        self.__settings.short_enabled_flag = status

    def analyze_candles(self, candles: list[HistoricCandle]) -> Optional[Signal]:
        """
        The method analyzes candles and returns his decision.
        """
        logger.debug(f"Start analyze candles for {self.settings.figi} strategy {__name__}. "
                     f"Candles count: {len(candles)}")

        if not self.__update_recent_candles(candles):
            return None

        if self.__is_match_long():
            logger.info(f"Signal (LONG) {self.settings.figi} has been found.")
            return self.__make_signal(SignalType.LONG, self.__long_take, self.__long_stop)

        if self.settings.short_enabled_flag and self.__is_match_short():
            logger.info(f"Signal (SHORT) {self.settings.figi} has been found.")
            return self.__make_signal(SignalType.SHORT, self.__short_take, self.__short_stop)

        return None

    def __update_recent_candles(self, candles: list[HistoricCandle]) -> bool:
        self.__recent_candles.extend(candles)

        if len(self.__recent_candles) < self.__signal_min_candles:
            logger.debug(f"Candles in cache are low than required")
            return False

        sorted(self.__recent_candles, key=lambda x: x.time)

        # keep only __signal_min_candles candles in cache
        if len(self.__recent_candles) >= self.__signal_min_candles:
            self.__recent_candles = self.__recent_candles[len(self.__recent_candles) - self.__signal_min_candles:]

        return True

    def __run_model(self, df):
        tmp = df.resample('H').mean().dropna().reset_index()[['utc', 'close', 'volume']]
        tmp['utc'] = tmp['utc'].dt.tz_convert(None)

        window_size = 10
        tmp['MA'] = tmp['close'].rolling(window=window_size).mean()
        tmp['ROC'] = tmp['close'].pct_change()
        tmp['Volatility'] = tmp['close'].pct_change().std()
        tmp['EMA'] = tmp['close'].ewm(span=10, adjust=False).mean()
        tmp['StdDev'] = tmp['close'].rolling(window=window_size).std()
        tmp['UpperBB'] = tmp['MA'] + (2 * tmp['StdDev'])
        tmp['LowerBB'] = tmp['MA'] - (2 * tmp['StdDev'])
        tmp['VolumeChange'] = tmp['volume'].pct_change()
        tmp['Momentum'] = tmp['close'].pct_change(periods=window_size)

        delta = tmp['close'].diff()
        up, down = delta.copy(), delta.copy()
        up[up < 0] = 0
        down[down > 0] = 0
        avg_gain = up.rolling(window=window_size).mean()
        avg_loss = abs(down.rolling(window=window_size).mean())
        rs = avg_gain / avg_loss
        tmp['RSI'] = 100 - (100 / (1 + rs))

        tmp['close'] = tmp['close'].shift(-1)
        # tmp['volume'] = tmp['volume'].shift(-1)
        tmp.dropna(subset=['close'], inplace=True)
        # tmp.dropna(subset=['volume'], inplace=True)

        tmp = tmp.fillna(method='bfill')

        return model.predict(tmp).data[:, 0][-1]

    def __is_match_long(self) -> bool:
        """
        Check for LONG signal. All candles in cache:
        Green candle, tail lower than __signal_min_tail, volume more that __signal_volume
        """

        candles = []

        for candle in self.__recent_candles:
            close = float(quotation_to_decimal(candle.close))
            candles.append({
                'utc': candle.time,
                'close': close,
                'volume': candle.volume,
            })

        df = pd.DataFrame(candles)
        df['utc'] = pd.to_datetime(df['utc'])
        df = df.set_index('utc')
        pred = self.__run_model(df)

        last_candle = self.__recent_candles[-1]
        if pred > float(quotation_to_decimal(last_candle.close)) * 1.01:
            return True

        return False

    def __is_match_short(self) -> bool:
        """
        Check for LONG signal. All candles in cache:
        Red candle, tail lower than __signal_min_tail, volume more that __signal_volume
        """

        candles = []

        for candle in self.__recent_candles:
            close = float(quotation_to_decimal(candle.close))
            candles.append({
                'utc': candle.time,
                'close': close,
                'volume': candle.volume,
            })

        df = pd.DataFrame(candles)
        df['utc'] = pd.to_datetime(df['utc'])
        df = df.set_index('utc')
        pred = self.__run_model(df)

        last_candle = self.__recent_candles[-1]
        if pred < float(quotation_to_decimal(last_candle.close)) * 0.99:
            return True


        return False

    def __make_signal(
            self,
            signal_type: SignalType,
            profit_multy: Decimal,
            stop_multy: Decimal
    ) -> Signal:
        # take and stop based on configuration by close price level (close for last price)
        last_candle = self.__recent_candles[len(self.__recent_candles) - 1]

        signal = Signal(
            figi=self.settings.figi,
            signal_type=signal_type,
            take_profit_level=quotation_to_decimal(last_candle.close) * profit_multy,
            stop_loss_level=quotation_to_decimal(last_candle.close) * stop_multy,
            price=quotation_to_decimal(last_candle.close)
        )

        logger.info(f"Make Signal: {signal}")

        return signal
