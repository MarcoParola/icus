# icus

[![license](https://img.shields.io/static/v1?label=OS&message=Linux&color=green&style=plastic)]()
[![Python](https://img.shields.io/static/v1?label=Python&message=3.10&color=blue&style=plastic)]()

Supported machine unlearning methods:
- Icus
- SCRUB
- BadT
- SSD


## **Installation**

To install the project, simply clone the repository and get the necessary dependencies. Then, create a new project on [Weights & Biases](https://wandb.ai/site). Log in and paste your API key when prompted.
```sh
# clone repo
git clone https://github.com/MarcoParola/icus.git
cd icus
mkdir data

# Create virtual environment and install dependencies 
python -m venv env
. env/bin/activate
python -m pip install -r requirements.txt 

# Weights&Biases login 
wandb login 
```

## **Usage**
To create golden model: 
```sh
python train_without_forgetting.py golden_model=True dataset.name=dataset_name dataset.classes= numer_of_classes forgetting_set_size= size_fs forgetting_set=[...]
``` 
To execute finetuning
```sh
python train_without_forgetting.py unlearning_method=finetuning dataset.name=dataset_name dataset.classes=numer_of_classes forgetting_set_size=size_fs forgetting_set=[...]
``` 

TODO
