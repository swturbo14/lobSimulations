from RLenv.SimulationEntities.Entity import Entity
from RLenv.SimulationEntities.TradingAgent import TradingAgent
import numpy as np

class RLAgent(TradingAgent):
    """RLTrader implements a simple Q-learning agent. """
    def __init__(self, id, cash, inventory, seed, tau=0.05):
        super().__init__(id, cash, seed)
        self.inventory=inventory
        self.tau=tau
        self._orderhistory=[]
    
    def get_action(self, observations):
        return super().get_action(observations)
    
    def update_state(self, kernelmessage):
        #to be implemented
        pass
        
    def resetseed(self, seed):
        np.random.seed(seed)