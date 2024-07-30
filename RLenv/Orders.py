from dataclasses import dataclass, field
from typing import ClassVar, Optional, Dict
@dataclass
class Order:
    time_placed: int
    order_id: int=field(init=False)
    side: str
    size: int
    symbol: Optional[str]
    agent_id: int #set to -1 for orders randomly generated by the exchange
    event_type: int #The number k from 0-11 which denotes which event it is
    filled: Optional[bool] = False
    cancelled: Optional[bool]=None
    fill_time: Optional[int] = None
    fill_price: Optional[float] = None
    _order_id_counter: ClassVar[int]=0
    _orders: ClassVar[Dict[int, "Order"]]={}
    def __post_init__(self):
        self.order_id: int=Order._order_id_counter
        Order._order_id_counter+=1
        Order._orders[self.order_id]=self
    def ordertype(self) -> str:
        return self.__class.__name__
    
    @classmethod
    def _get_order_by_id(cls, id: int) -> Optional['Order']:
        return cls._orders.get(id)
    
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
    cancelID: int=0

