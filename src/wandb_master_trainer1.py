import sys
import os

# add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# add sibling directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wandb

import train_clip
from src.utils import generate_csv_file_name, cleanup_after_training

from src.config import training_hyperparameters, ClipDatasets

    


def set_sweep_config(training_hyperparameters: dict, sweep_config: dict) -> dict:
    # set correct key values from wandb

    for key in training_hyperparameters.keys():
        if key not in sweep_config['parameters']:
            sweep_config['parameters'][key] = {'value': training_hyperparameters[key]}
    return sweep_config


def main():

    
    wandb.init() 

    # print('wandb config ', wandb.config)

    # set_hypers() # no need to set hypers anymore, wandb automatically does this



    # in case train_clip.py throws error, we can still finish the run

    
    try:
        # do training
        train_clip.main()
        wandb.finish() 
    except Exception as e:
        print('Exception in training ', e)
        cleanup_after_training()
        wandb.finish()
        # delete cache batches
        return 



    # do training
    # train_clip.main()
    # wandb.finish() 

# if main 
if __name__ == "__main__":


    sweep_configuration = {
        "method": "grid",
        # "method": "bayes",
        # "method": "random",
        # "name": "Checking AGAIN whether same inputs cause modality gap or no",
        "name": "CYCLIP run, VIT/32, uniformity loss 512D, 256b, full ConCaps, val as val",
        # "metric": {"goal": "maximize", "name": "val_image_classification_accuracy"},
        "metric": {"goal": "minimize", "name": "train_intermodality_loss"},
        "parameters": {
            "temperature": {"values": [0.07]}, # learnable temperature now, so this is the starting temp

            # CUDA: 1

            # TRAINING STUFF
            'clip_projection_dim': {'values': [512]}, # 512
            'batch_size': {'values': [256]},
            'vision_model': {'values': ['VIT']}, # RN50 or VIT
            'use_scheduler': {'values': [True]},
            'n_warmup_steps': {'values': [10000]},
            'weight_decay': {'values': [0.1]},


            # LOSS STUFF
            'intra_modality_loss': {'values': [False]},
            'uniformity_loss': {'values': [True]},
            # 'weight_decay': {'min': 0.2, 'max': 0.6,},


            # "lr": {"max": 2e-4, "min": 4e-5},and
            # "lr": {'values': [0.000015]}, # 1.5e-5, optimized for 0.01 temp
            "lr": {'values': [5e-4]}, # 5e-4, from CyClip paper
            'n_epochs': {'values': [64]},
            'num_workers': {'values': [24]},

            # DATASET STUFF
            'dataset': {'values': [ClipDatasets.CONCEPTUAL_CAPTIONS.value]},
            'validation_dataset_size': {'values': [2048]},
            'validation_batch_size': {'values': [2048]},
            'use_small_trainloader': {'values': [False]}, 
            'cifar10_acc': {'values': [True]}, 
            'use_train_as_val': {'values': [False]}, # SET

            'seed': {'values': [2]},
        },
    }

    sweep_configuration = set_sweep_config(training_hyperparameters, sweep_configuration)



    sweep_id = wandb.sweep(sweep=sweep_configuration, project="clipverse")

    print()
    print('--- SWEEP ID ---')
    print(sweep_id)
    print()


    # wandb.agent(sweep_id='nrjuh2de', function=main, project="clipverse")
    wandb.agent(sweep_id=sweep_id, function=main, project="clipverse")
 


