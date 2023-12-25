from typing import Optional

from trade_system.strategies.ml_strategy import MlStrategy
from trade_system.strategies.change_and_volume_strategy import ChangeAndVolumeStrategy
from trade_system.strategies.orderbook_signals import OrderBookSignals
from trade_system.strategies.base_strategy import IStrategy

__all__ = ("StrategyFactory")


class StrategyFactory:
    """
    Fabric for strategies. Put here new strategy.
    """
    @staticmethod
    def new_factory(strategy_name: str, *args, **kwargs) -> Optional[IStrategy]:
        match strategy_name:
            case "MlStrategy":
                return MlStrategy(*args, **kwargs)
            case "ChangeAndVolumeStrategy":
                return ChangeAndVolumeStrategy(*args, **kwargs)
            case "OrderBookSignals":
                return OrderBookSignals(*args, **kwargs)
            case _:
                return None
