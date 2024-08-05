import pickle
import numpy as np
import pandas as pd
import time
import numpy as np
import os 
import random
import logging
from typing import Any, List, Optional, Tuple, ClassVar
from RLenv.SimulationEntities.Entity import Entity
from RLenv.Exceptions import *
from RLenv.SimulationEntities.TradingAgent import TradingAgent
from RLenv.Stochastic_Processes.Arrival_Models import ArrivalModel, HawkesArrival
from RLenv.Orders import *
from RLenv.Messages.ExchangeMessages import *

logger=logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
class Exchange(Entity):
    def __init__(self, symbol: str ="AAPL", ticksize: float =0.01, LOBlevels: int=2, numOrdersPerLevel: int =10, Arrival_model: ArrivalModel=None, agents: List[TradingAgent]=None):
        super().__init__(type="Exchange", seed=1, log_events=True, log_to_file=False)
        self.ticksize=ticksize
        self.LOBlevels=LOBlevels
        if Arrival_model is None:
            raise ValueError("Please specify Arrival_model for Exchange")
        else:
            logger.debug(f"Arrival_model of Exchange specified as {self.Arrival_model.__class__.__name__}")
            self.Arrival_model=Arrival_model
        if not agents:
            raise ValueError("Please provide a list of Trading Agents")
        else:
            self.agentIDs=[j.id for j in agents]
            self.agents={j.id: j for j in agents}
            self.agentcount=len(agents)
            #Keep a registry of which agents have a subscription to trade notifs
            self.agentswithTradeNotifs=[j.id for j in agents if j.on_trade==True]
        self.kernel=None
        self.symbol=symbol
        
        self.levels = [f"Ask_L{i}" for i in range(1, self.LOBlevels + 1)]+[f"Bid_L{i}" for i in range(1, self.LOBlevels + 1)]
        self.LOBhistory=[] #History of an order book is an array of the form (t, LOB, spread)
        self.numOrdersPerLevel=numOrdersPerLevel
    
    def initialize_exchange(self, priceMid0: int=20, spread0: int =4): 
        """
        The initialize_exchange method is called by the simulation kernel. By this time, the exchange should be linked to the kernel.
        """
        if self.kernel is None:
            raise ValueError("Exchange is initialized but is not linked to a simulation kernel")
        #Initialize prices
        self.priceMid=priceMid0
        self.spread=spread0

        self.askprices={}
        self.bidprices={}
        for i in range(self.LOBlevels):
            key="Ask_L"+str(i+1)
            val=self.priceMid+np.floor(self.spread/2)*self.ticksize + i*self.ticksize
            self.askprices[key]=val
            key="Bid_L"+str(i+1)
            val=self.priceMid-np.floor(self.spread/2)*self.ticksize - i*self.ticksize
            self.bidprices[key]=val   
        self.askprice=self.askprices["Ask_L1"]
        self.bidprice=self.bidprices["Bid_L1"]
        self.bids={} #holding list of pricelevels which are in the form of (key, value)=(price, [list of orders])
        self.asks={} 
        #Initialize order sizes
        for k in self.levels:
            queue=self.Arrival_model.generate_orders_in_queue(loblevel=k, numorders=self.numOrdersPerLevel)
            if "Ask" in k:
                self.asks[self.askprices[k]]=queue
            elif "Bid" in k:
                self.asks[self.bidprices[k]]=queue
            else:
                raise AssertionError(f"Level is not an ASK or BID string")
        logger.debug("Stock Exchange initalized at time")
        #Send a message to agents to begin trading
        message=BeginTradingMsg(time=self.current_time)
        self.sendbatchmessage(recipientIDs=self.agentIDs, message=message, current_time=self.current_time)
        
    def generate_orders_in_queue(self, loblevel) -> List[LimitOrder]:
        assert self.Arrival_model is not None, "Arrival_model is not provided"
        queue=self.Arrival_model.generate_orders_in_queue(loblevel=loblevel, numorders=self.numOrdersPerLevel)
        side=loblevel[0:3]
        price=0
        if side=="Ask":
            price=self.askprices[loblevel]
        else:
            price=self.bidprices[loblevel]
        orderqueue=[]
        for size in queue:
            order=LimitOrder(time_placed=self.current_time, side=side, size=size, symbol=self.symbol, agent_id=-1)
            orderqueue.append(order)
        return orderqueue
           

    def generate_ordersize(self, loblevel):
        """
        generate ordersize
        loblevel: one of the possible levels in the LOB as a string
        Returns: qsize the size of the order
        """
        #use generaeordersize method in hawkes arrival
        if self.Arrival_model is not None:
            return self.Arrival_model.generate_ordersize(loblevel)
        else:
            raise ValueError("Arrival_model is not provided")      

    def nextarrival(self):
        """
        Automatically generates the next arrival and passes the order to the kernel to check for validity.
        """
        order=None
        tmp=self.Arrival_model.get_nextarrival()
        if tmp is None:
            return None
        else:
            time, side, order_type, level, size=tmp
        if order_type=="lo":
            if level=="Ask_inspread": #inspread ask
                price=self.askprices["Ask_L1"]-self.ticksize
            elif level=="Bid_inspread": #inspread bid
                price=self.bidprices["Bid_L1"]+self.ticksize
            else:    
                if side=="Ask":
                    price=self.askprices[level]
                else:
                    price=self.bidprices[level]
            order=LimitOrder(time_placed=time, side=side, size=size, symbol=self.symbol, agent_id=-1, price=price)
            
        elif order_type=="mo":
            #marketorder
            order=MarketOrder(time_placed=time, side=side, size=size, symbol=self.symbol, agent_id=-1)
        else:
            #cancelorder
            if side=="Ask":
                price=self.askprices[level]
            else:
                price=self.bidprices[level]
            order=CancelOrder(time_placed=time, side=side, size=-1, symbol=self.symbol, agent_id=-1, loblevel=level)
        order._level=level
        self.processorder(order=order)
        
        
    def processorder(self, order: Order):
        """
        Called by the kernel: Takes an order in the form (t, k, s) and processes it in the limit order book, performing the correct matching as necessary. It also updates the arrival_model history
        """
        self.current_time=order.time_placed
        #process the order
        order_type=None
        trade_happened=False
        side=order.side
        if isinstance(order, LimitOrder):
            #Limit_order
            self.processLimitOrder(order=order)
            order_type="lo"
        elif isinstance(order, MarketOrder): #market order
            totalvalue=self.processMarketOrder(order)
            order.total_value=totalvalue
            if order.agent_id==-1:
                tmp=TradeNotificationMsg()
                self.sendbatchmessage(recipientIDs=self.agentswithTradeNotifs, message=tmp)
            else:
                #Agent doesn't get a chance to trade again
                notif=OrderExecutedMsg(order=order)
                self.sendmessage(recipientID=order.agent_id, message=notif)
            trade_happened=True
            order_type="mo"
        elif isinstance(order, CancelOrder): #Cancel Order completed
            self.processCancelOrder(order=order)
            order_type="co"
        else:
            raise InvalidOrderType(f"Invalid Order type with ID {order.order_id} passed to exchange")
            pass
        if order.agent_id==-1:
            pass
        else:
            self.update_model_state(order)
        
        #update spread and notify agents if a trade has happened:
        newspread=abs(self.askprice-self.bidprice)
        test=self.checkLOBValidity()
        if test:
            pass
        else:
            raise LOBProcessingError("LOB in Exchange processed incorrectly")
        if self.spread==newspread:
            pass
        if trade_happened==False:
            pass
        if self.spread!=newspread:
            self.spread=newspread
            #Send Batch message to agents
            message=SpreadNotificationMsg()
            self.sendbatchmessage(recipientIDs=self.agentIDs, message=message)
        else:
            if trade_happened==True:
                message=TradeNotificationMsg()
                self.sendbatchmessage(recipientIDs=self.agentIDs, message=message)
        #log event:
        self._logevent(event=[order.current_time, order.ordertype(), order.agent_id, order.order_id])
        self.updatehistory()
    
    
    def processLimitOrder(self, order: LimitOrder):
        #Limit_order
        side=order.side
        price=order.price
        if side=="Ask":
            queue=self.asks.get(key=price)
        else:
            queue=self.bids.get(key=price)
        if queue is not None:
            queue.append(order)
        else: #Inspread
            #Need to implement auto order cancellation
            lastlvl=side+"_L"+str(self.LOBlevels)
            if side=="Ask":
                if order.price==self.askprice-self.ticksize:
                    pass
                else:
                    raise InvalidOrderType(f"Order {order.order_id} is an invalid inspread limit order")
                
                todelete=self.asks[self.askprices[lastlvl]]
            else:
                if order.price==self.bidprice+self.ticksize:
                    pass
                else:
                    raise InvalidOrderType(f"Order {order.order_id} is an invalid inspread limit order")
                todelete=self.bids[self.bidprices[lastlvl]]
            agentorders=[order for order in todelete if order.agent_id!=-1]
            logger.info(f"Autocancelling agent orders{[j.order_id for j in agentorders]} due to LOB inspread shift")
            self.autocancel(agentorders)
            if side=="Ask":
                del self.asks[self.askprices[lastlvl]]
                self.askprice=order.price
                new_askprices = {}
                new_asks = {}  
                new_askprices["Ask_L1"]=self.askprice
                new_asks[self.askprice]=order
                for i in range(2, self.LOBlevels + 1):
                    new_key= f"Ask_L{i}"
                    old_key=f"Ask_L{i-1}"
                    new_askprices[new_key]=self.askprices[old_key]
                    new_asks[new_askprices[new_key]]=self.asks[new_askprices[new_key]]
                self.askprices = new_askprices
                self.asks = new_asks  
            else:
                del self.bids[self.bidprices[lastlvl]]
                self.bidprice=order.price
                new_bidprices = {}
                new_bids = {}  
                new_bidprices["Ask_L1"]=self.bidprice
                new_bids[self.askprice]=order
                for i in range(2, self.LOBlevels + 1):
                    new_key= f"Ask_L{i}"
                    old_key=f"Ask_L{i-1}"
                    new_bidprices[new_key]=self.bidprices[old_key]
                    new_bids[new_bidprices[new_key]]=self.bids[new_bidprices[new_key]]
                self.bidprices = new_bidprices           
    def processMarketOrder(self, order: MarketOrder)-> int:
        side=order.side
        remainingsize=order.size
        totalvalue=0
        if side=="Ask":
            level=1
            while remainingsize>0:
                pricelvl=self.bidprices[side+"_L"+str(level)]
                while len(self.bids)>0:
                    item: LimitOrder=self.bids[pricelvl][0]
                    if remainingsize<item.size:
                        totalvalue+=pricelvl*remainingsize
                        remainingsize=0
                        order.fill_time=self.current_time
                        order.filled=True
                        if item.agent_id==-1:
                            pass
                        else:
                            notif=PartialOrderFill(order=item)
                            self.sendmessage(recipientID=item.agent_id, message=notif)
                        return totalvalue
                    else:
                        filled_order: Order=self.bids[pricelvl].pop(0)
                        remainingsize-=filled_order.size
                        totalvalue+=filled_order.size*pricelvl
                        filled_order.fill_time=self.current_time
                        filled_order.filled=True
                        notif=OrderExecutedMsg(order=filled_order)
                        self.sendmessage(recipientID=filled_order.agent_id, message=notif)
                #Touch level has been depleted
                del self.bids[self.bidprices[pricelvl]]
                new_bidprices = {}
                new_bids = {}  
                for i in range(1, self.LOBlevels):
                    new_key= f"Bid_L{i}"
                    old_key=f"Bid_L{i+1}"
                    new_bidprices[new_key]=self.bidprices[old_key]
                    new_bids[new_bidprices[new_key]]=self.bids[new_bidprices[new_key]]
                new_bidprices[f"Bid_L{self.LOBlevels}"]=new_bidprices[f"Bid_L{self.LOBlevels-1}"] - self.ticksize
                new_bids[new_bidprices[f"Bid_L{self.LOBlevels}"]]=self.generate_orders_in_queue(loblevel=f"Bid_L{self.LOBlevels}")
                self.bidprices = new_bidprices
                self.bids = new_bids  
                self.bidprice=self.bidprices["Bid_L1"]
        else:
            level=1
            while remainingsize>0:
                pricelvl=self.askprices[side+"_L"+str(level)]
                while len(self.asks)>0:
                    item: LimitOrder=self.asks[pricelvl][0]
                    if remainingsize<item.size:
                        totalvalue+=pricelvl*remainingsize
                        remainingsize=0
                        order.fill_time=self.current_time
                        order.filled=True
                        if item.agent_id==-1:
                            pass
                        else:
                            notif=PartialOrderFill(order=item)
                            self.sendmessage(recipientID=item.agent_id, message=notif)
                        if order.agent_id==-1:
                            pass
                        else:
                            notif=OrderExecutedMsg(order=order)
                            self.sendmessage(recipientID=order.agent_id, message=notif)
                    else:
                        filled_order: Order=self.asks[pricelvl].pop(0)
                        remainingsize-=filled_order.size
                        totalvalue+=filled_order.size*pricelvl
                        filled_order.fill_time=self.current_time
                        filled_order.filled=True
                        notif=OrderExecutedMsg(order=filled_order)
                        self.sendmessage(recipientID=filled_order.agent_id, message=notif)
                #Touch level has been depleted
                del self.asks[self.askprices[pricelvl]]
                new_askprices = {}
                new_asks = {}  
                for i in range(1, self.LOBlevels):
                    new_key= f"Ask_L{i}"
                    old_key=f"Ask_L{i+1}"
                    new_askprices[new_key]=self.askprices[old_key]
                    new_asks[new_askprices[new_key]]=self.asks[new_askprices[new_key]]
                new_askprices[f"Ask_L{self.LOBlevels}"]=new_askprices[f"Ask_L{self.LOBlevels-1}"] + self.ticksize
                new_asks[new_askprices[f"Ask_L{self.LOBlevels}"]]=self.generate_orders_in_queue(loblevel=f"Ask_L{self.LOBlevels}")
                self.askprices = new_askprices
                self.asks = new_asks  
                self.askprice=self.askprices["Ask_L1"]
        return totalvalue
    def processCancelOrder(self, order: CancelOrder):
        cancelID=order.cancelID
        tocancel: Order=Order._get_order_by_id(cancelID)
        side=tocancel.side
        price=tocancel.price    
        if tocancel.agent_id==-1:
            public_cancel_flag=True
        else:
            public_cancel_flag=False
            #test if it's a valid agent_id
            if tocancel.agent_id in self.agentIDs:
                pass
            else:
                raise AgentNotFoundError(f"Agent ID {order.agent_ID} is not listed in Exchange book")
            #Check that the cancel order came from the same agent who placed the order
            if tocancel.agent_id==order.agent_id:
                pass
            else:
                raise InvalidOrderType(f"Agent {order.agent_id} wants to cancel order {order.cancelID} but order was placed by {tocancel.agent_id}")
        queue=[]        
        if side=="Ask":
            queue=self.asks[price]
        else:
            queue=self.bids[price]
        validcancels=[]
        if public_cancel_flag==True:
            validcancels=[item for item in queue if item.agent_id==-1]
            if len(validcancels)==0:
                logger.info(f"Random cancel order issued, but only existing orders in queue are private agent orders so cancel order at time {order.time_placed} ignored.")  
            else:
                cancelled=validcancels.pop(random.randrange(0, len(validcancels)))
                queue=[item for item in queue if item.order_id != cancelled.order_id]
        else: #Cancel order from an agent
            queue=[item for item in queue if item.order_id!=cancelID]
            assert len(queue)>0, f"Agent {order.agent_id} attemptd to place cancel orders wihout pre-existing limit orders in the book at the same price"
        #non-empty queue for order cancellation, public and private           
        if order.side=="Ask":
            self.asks[price]=queue
        else:
            self.bids[price]=queue
        tocancel.cancelled=True
        if public_cancel_flag==False:
            notif=OrderExecutedMsg(order=order)
            self.sendmessage(recipientID=order.agent_id, message=notif)
        self.regeneratequeuedepletion()   
        
    def autocancel(self, orderIDs: List[int]):
        for orderID in orderIDs:
            order=Order._get_order_by_id(orderID)
            if isinstance(order, LimitOrder):
                pass
            else:
                raise InvalidOrderType(f"Expected Limit Order for autocancelling, received {order.ordertype()}")
            price=order.price
            side=order.side
            order.cancelled=True
            if side=="Ask":
                oldqueue=order.asks[price]
            else:
                oldqueue=order.bids[price]
            queue=[j for j in oldqueue if j.order_id!=orderID]
            oldqueue=queue
            notif=OrderAutoCancelledMsg(order=order)
            self.sendmessage(recipientID=order.agent_id, message=notif)
    def regeneratequeuedepletion(self): #to be implemented
        """
        Regenerates LOB from queue depletion and updates prices as necessary
        """
        if len(self.asks[self.askprices["Ask_L1"]])==0:
            del self.asks[self.askprices["Ask_L1"]]
            self.askprices["Ask_L1"]=self.askprices["Ask_L2"]
            self.askprices["Ask_L2"]=self.askprices["Ask_L1"]+self.ticksize
            self.asks[self.askprices["Ask_L2"]]=self.generate_orders_in_queue(loblevel="Ask_L2")
            
            
        elif len(self.bids[self.bidprices["Bid_L1"]])==0:
            del self.bids[self.bidprices["Bid_L1"]]
            self.bidprices["Ask_L1"]=self.bidprices["Bid_L2"]
            self.bidprices["Bid_L2"]=self.bidprices["Bid_L1"]-self.ticksize
            self.bids[self.bidprices["Bid_L2"]]=self.generate_orders_in_queue(loblevel="Bid_L2")
        
        elif len(self.asks[self.askprices["Ask_L2"]])==0:
            del self.asks[self.askprices["Ask_L2"]]
            self.askprices["Ask_L2"]=self.askprices["Ask_L1"]+self.ticksize
            self.asks[self.askprices["Ask_L2"]]=self.generate_orders_in_queue(loblevel="Ask_L2")
        
        elif len(self.bids[self.bidprices["Bid_L2"]])==0:
            del self.bids[self.bidprices["Bid_L2"]]
            self.bidprices["Bid_L2"]=self.bidprices["Bid_L1"]-self.ticksize
            self.bids[self.bidprices["Bid_L2"]]=self.generate_orders_in_queue(loblevel="Bid_L2")
        else:
            #queue is not depleted
            pass
    
    def checkLOBValidity(self) -> bool:
        condition1= self.askprice==self.askprices["Ask_L1"]
        condition2=self.askprice==min(self.asks.keys())       
        condition3=self.bidprice==self.bidprices["Bid_L1"]
        condition4=self.bidprice==min(self.bids.keys())
        return condition1 and condition2 and condition3 and condition4
        
        
    #information getters and setters
    def lob0(self)-> dict: 
        rtn={
            "Ask_L2": (self.askprices["Ask_L2"], sum(self.asks[self.askprices["Ask_L2"]])),
            "Ask_L1": (self.askprices["Ask_L1"], sum(self.asks[self.askprices["Ask_L1"]])),
            "Bid_L1": (self.bidprices["Bid_L1"], sum(self.bids[self.bidprices["Bid_L1"]])),
            "Bid_L2": (self.bidprices["Bid_L1"], sum(self.bids[self.bidprices["Bid_L1"]]))
        }
        return rtn

    def lobl3(self):
        rtn={
            "Ask_L2": (self.askprices["Ask_L2"], self.asks[self.askprices["Ask_L2"]]),
            "Ask_L1": (self.askprices["Ask_L1"], self.asks[self.askprices["Ask_L1"]]),
            "Bid_L1": (self.bidprices["Bid_L1"], self.bids[self.bidprices["Bid_L1"]]),
            "Bid_L2": (self.bidprices["Bid_L1"], self.bids[self.bidprices["Bid_L1"]])
        }
        return rtn

    def getlob(self):
        return [[self.askprices["Ask_L2"], self.asks[self.askprices["Ask_L2"]]], [self.askprices["Ask_L1"], self.asks[self.askprices["Ask_L1"]]], [self.bidprices["Bid_L1"], self.bids[self.bidprices["Bid_L1"]]], [self.bidprices["Bid_L2"], self.bids[self.bidprices["Bid_L2"]]], self.spread]
        
    def updatehistory(self):
        #data=[order book, spread]
        data=(self.current_time, self.getlob(), self.spread)
        self.LOBhistory.append(data)

    def update_model_state(self, order: Order):
        """
        Adds a point to the arrival model, updates the spread
        """
        time=order.time_placed
        side=order.side
        order_type=order_type
        level=order._level
        size=order.size
        self.Arrival_model.update(time=time, side=side, order_type=order_type, level=level, size=size)
        