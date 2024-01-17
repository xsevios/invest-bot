import logging

from tinkoff.invest import HistoricCandle
from tinkoff.invest.utils import quotation_to_decimal

from trade_system.strategies.base_strategy import IStrategy
from history_tests.test_results import TestResults

__all__ = ("StrategyTester")

logger = logging.getLogger(__name__)


class StrategyTester:
    """
    Class encapsulate test logic on historical candles
    """
    def __init__(self, strategy: IStrategy) -> None:
        self.__strategy = strategy

    def test(
            self,
            hour_candles: list[HistoricCandle],
            min_candles: list[HistoricCandle],
            portion: int = 1
    ) -> TestResults:
        logger.info(f"Start test: {self.__strategy}, portion {portion}, "
                    f"hour candles count: {len(hour_candles)}, min candles count: {len(min_candles)}")

        test_result = TestResults()
        test_candles_pack = []

        for i, candle in enumerate(hour_candles):
            logger.info(f"Progress: {round(i / len(hour_candles) * 100.0, 2)}%")

            filtered_candles = [cur_candle for cur_candle in min_candles
                                if cur_candle.time.date() == candle.time.date() and cur_candle.time.hour == candle.time.hour]
            for min_candle in filtered_candles:

                # Check price from candle for take or stop price level
                for signal_status in test_result.get_proposed_signals():
                    high = quotation_to_decimal(min_candle.high)
                    low = quotation_to_decimal(min_candle.low)

                    price = signal_status.signal.price
                    take = signal_status.signal.take_profit_level

                    # Logic is:
                    # if stop or take price level is between high and low, then stop or take will be executed
                    if low <= signal_status.signal.stop_loss_level <= high:
                        signal_status.stop_loss_executed()

                        logger.info("Test STOP LOSS executed")
                        logger.info(f"CANDLE: {min_candle}")
                        logger.info(f"Signal: {signal_status.signal}")

                        test_result.add_profit(-abs(price - take))

                    elif low <= signal_status.signal.take_profit_level <= high:
                        signal_status.take_profit_executed()

                        logger.info("Test TAKE PROFIT executed")
                        logger.info(f"CANDLE: {min_candle}")
                        logger.info(f"Signal: {signal_status.signal}")

                        test_result.add_profit(abs(price - take))

            test_candles_pack.append(candle)

            if len(test_candles_pack) >= portion:
                signal = self.__strategy.analyze_candles(test_candles_pack)
                test_candles_pack = []

                if signal:
                    logger.info(f"New Signal: {signal}")

                    if test_result.get_proposed_signals():
                        logger.info("Signal skipped. Old still alive")
                    else:
                        test_result.add_signal(signal)

        logger.info(f"Tests completed")

        return test_result
