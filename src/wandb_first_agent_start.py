import sys
import os

# add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# add sibling directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.config as config
config.config_cuda_device = 'cuda:2' # SET the cuda device to be used in host4


from src.wandb_master_trainer import main

import wandb



            
sweep_id = 'w1u83b29'

# wandb.agent(sweep_id='nrjuh2de', function=main, project="clipverse")
wandb.agent(sweep_id=sweep_id, function=main, project="clipverse")
 

