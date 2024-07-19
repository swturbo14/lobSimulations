import numpy as np
from abc import ABC, abstractmethod 
from typing import Any, List, Optional, Tuple
import pandas as pd
import logging
from Messages.Message import Message
from RLenv.OrderBook import LimitOrderBook

logger = logging.getLogger(__name__)
class Agent:
    """
    Base Agent class

    Agent Attributes:
        id: Must be a unique number (usually autoincremented).
        type: For machine aggregation of results, should be same for all agents
            following the same strategy (incl. parameter settings).
        seed: Every agent is given a random seed for stochastic purposes.
        cash: cash of an agent
        Inventory: Initial inventory of an agent
        log_events: flag to log or not the events during the simulation 
            Logging format:
                time: time of event
                event_type: label of the event (e.g., Order submitted, order accepted, last trade etc....)
                event: actual event to be logged (co_deep_Ask, lo_deep_Ask...)
                size: size of the order (if applicable)
        log_to_file: flag to write on disk or not the logged events
    """
    def __init__(self, id: int, type: str = None, seed=1, cash: int=10000, inventory: int=500, log_events: bool = True, log_to_file: bool = False) -> None:
        self.id=id
        self.type=type
        self.cash=cash
        self.inventory=inventory
        self.log_events=log_events
        self.log_to_file=log_events & log_to_file
        self.seed=seed
        self.resetseed(self.seed)
        # Simulation attributes
        
        self.kernel=None
        self.exchange=None
        #What time does the agent think it is?
        self.current_time: int = 0 
        
        #Agents will maintain a log of their activities, events will likely be stored in the format of (time, event_type, eventname, size)
        self.log: List[Tuple[int, str, str, int]]
        
        if self.log_to_file:
            self.filename=None
    
    def kernel_start(self, start_time: int) -> None:
        assert self.kernel is not None
        logger.debug(
            "Agent {} ({}) requesting kernel wakeup at time {}".format( self.id, start_time))
    
    def kernel_terminate(self) -> None:
        if self.log and self.log_to_file:
            df_log=pd.DataFrame(self.log, columns=("EventTime", "Event Type", "Event", "Size"))
            self.write_log(df_log)
    
    
    
    """Methods for communication with the exchange, kernel, or other agents"""
    def _sendmessage(self, recipient: Any, message: Message) -> None:
        #Called each time 
        if rec
        
        
        
    def _receivemessage(self, current_time, sender: Any, message: Message):
        """
        Called each time a message destined for this agent reaches the front of the
        kernel's priority queue.
        Arguments:
            current_time: The simulation time at which the kernel is delivering this message -- the agent should treat this as "now".
            sender: The object that send this message(can be the exchange, another agent or the kernel).
            message: An object guaranteed to inherit from the Message.Message class.
        """
        assert self.kernel is not None
        self.current_time=current_time
        #Check identity of the sender
        if isinstance(sender, Agent):
            #Empty for now since it's a single-agent simulation
            pass
        elif isinstance(sender, LimitOrderBook):
            pass
        elif sender is self.kernel:
            pass
        else:
            raise TypeError(f"Unexpected sender type: {type(sender)}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("At {}, agent {} ({}) received: {}".format(self.current_time, self.id, message))
        
            
    """Private Methods for Internal use by agents"""   
    def _logevent(self, event: Tuple[int, str, str, int]):
        """Adds an event to this agents log"""
        if not self.log_events:
            return
        self.log.append(event)

        
        
    #    
    @abstractmethod    
    def get_action(self, observations):
        pass
          
    @abstractmethod        
    def update_state(self, kernelmessage): #update internal agentstate given a kernel message
        pass
    
    def resetseed(self, seed):
        np.random.seed(1)
        return None
        
    
        
