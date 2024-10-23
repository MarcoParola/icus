from torch.utils.data import Dataset
import torch
import random
import numpy as np
from src.utils import retrieve_weights
from transformers import BertModel, BertTokenizer


class DatasetWrapperIcus(Dataset):
    def __init__(self, infgt, model, num_classes, orig_dataset, device="cpu"):
        """
        Args:
            classi (Tensor): Tensor contenente le etichette delle classi.
            pesi (Tensor): Tensor contenente i pesi associati a ciascuna classe.
            descrizioni (Tensor): Tensor contenente le descrizioni (o embedding) delle classi.
            infgt_flags (Tensor): Tensor contenente i flag infgt per ciascuna classe (0 o 1).
            device (str): Dispositivo su cui eseguire il calcolo (default: "cpu").
        """
        self.classes = torch.arange(0, num_classes)
        self.descr = self.calculate_embeddings(orig_dataset)  # Tensor delle descrizioni
        self.weights, self.bias=retrieve_weights(model)
        self.weights = torch.cat((self.weights, self.bias.view(-1, 1)), dim=1)
        self.infgt = infgt  # Tensor dei flag infgt (1 o 0)
        self.device = device

    def __len__(self):
        return len(self.classes)

    def __getitem__(self, idx):
        # Estrai la classe, i pesi, la descrizione e il flag infgt in base all'indice
        classe = self.classes[idx]
        weigths = self.weights[idx]
        descr = self.descr[idx]
        infgt = self.infgt[idx]

        classe = classe.to(self.device)
        weigths = weigths.to(self.device)
        descr = descr.to(self.device)
        infgt = infgt.to(self.device)

        return classe, weigths, descr, infgt


    def calculate_embeddings(self, dataset_name):

        # Load BERT tokenizer and model
        tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
        model = BertModel.from_pretrained('bert-base-uncased')

        # List of words to encode
        if dataset_name=='cifar10':
            path = "data/"+dataset_name+"_classes.txt"
            classes = load_words_to_array(path)
            
        # Tokenize the list of words all together
        encoding = tokenizer.batch_encode_plus(
            classes,
            padding=True,
            truncation=True,
            return_tensors='pt',
            add_special_tokens=True
        )

        # Get token IDs and attention mask
        token_ids = encoding['input_ids']
        attention_mask = encoding['attention_mask']

        # Get word embeddings for all the words at once
        with torch.no_grad():
            outputs = model(input_ids=token_ids, attention_mask=attention_mask)
            word_embeddings = outputs.last_hidden_state  # Retrieve the last hidden states

        return word_embeddings
        
def load_words_to_array(file_path):
    # Leggi le parole dal file di testo
    with open(file_path, 'r') as f:
        # Rimuovi eventuali spazi bianchi e newline, e crea una lista di parole
        words = [line.strip() for line in f if line.strip()]
    return words    
                

