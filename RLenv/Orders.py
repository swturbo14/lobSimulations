from dataclasses import dataclass, field
from typing import ClassVar, Optional
@dataclass
class Order:
    time_placed: int
    order_id: int=field(init=False)
    side: str
    size: int
    symbol: Optional[str]
    agent_id: int #set to -1 for orders randomly generated by the exchange
    event_type: int #The number k from 0-11 which denotes which event it is
    filled: bool = False
    fill_time: Optional[int] = None
    fill_price: Optional[float] = None
    _order_id_counter: ClassVar[int]=0
    
    def __post_init__(self):
        self.order_id: int=Order._order_id_counter
        Order._order_id_counter+=1
    def ordertype(self) -> str:
        return self.__class.__name__
        
    
@dataclass
class LimitOrder(Order):
    price: float=0
    loblevel: str=None
        
@dataclass
class MarketOrder(Order):
    pass
@dataclass
class CancelOrder(Order):
    price: float=0
    loblevel: str=None

