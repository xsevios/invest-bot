import enum
import logging
from dataclasses import dataclass, field
from decimal import Decimal

__all__ = ("Signal", "SignalType")

logger = logging.getLogger(__name__)


@enum.unique
class SignalType(enum.IntEnum):
    LONG = 0
    SHORT = 1
    HUGE_ORDER = 2


@dataclass(frozen=True, eq=False, repr=True)
class Signal:
    figi: str = ""
    signal_type: SignalType = 0
    take_profit_level: Decimal = field(default_factory=Decimal)
    stop_loss_level: Decimal = field(default_factory=Decimal)
    quantity: Decimal = field(default_factory=Decimal)
    prev_quantity: Decimal = field(default_factory=Decimal)
    price: Decimal = field(default_factory=Decimal)
    bid_ask: str = ""
