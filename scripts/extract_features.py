import hydra
import torch
import torchvision
import os
import wandb
import tqdm
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.models.classifier import Classifier
from torch.utils.data import DataLoader 
from src.datasets.dataset import load_dataset

def extract_features(model, loader, device):
    model = model.to(device)
    features = []
    labels = []

    # Disabilitare il calcolo dei gradienti
    with torch.no_grad():
        for images, batch_labels in loader:
            images = images.to(device)
            batch_labels = batch_labels.to(device)
            batch_features = model.extract_features(images)
            features.append(batch_features)
            labels.append(batch_labels)

            # Liberiamo memoria GPU ogni tanto
            del images, batch_labels, batch_features
            torch.cuda.empty_cache()

    # Unisci tutte le caratteristiche e le etichette in un unico tensor
    features = torch.cat(features, dim=0)
    labels = torch.cat(labels, dim=0)

    return features, labels


@hydra.main(config_path='../config', config_name='config', version_base=None)
def main(cfg):
    data_dir = os.path.join(cfg.currentDir, cfg.dataset.path)
    train, val, test = load_dataset(cfg.dataset.name, data_dir, cfg.dataset.resize)

    # Crea i DataLoader per train, val, test
    train_loader = torch.utils.data.DataLoader(train, 
        batch_size=cfg.train.batch_size, 
        shuffle=False, 
        num_workers=cfg.train.num_workers)
    
    val_loader = torch.utils.data.DataLoader(val, 
        batch_size=cfg.train.batch_size, 
        shuffle=False, 
        num_workers=cfg.train.num_workers)

    test_loader = torch.utils.data.DataLoader(test, 
        batch_size=cfg.train.batch_size, 
        shuffle=False, 
        num_workers=cfg.train.num_workers)

    model = Classifier(cfg.weights_name, num_classes=cfg[cfg.dataset.name].n_classes, finetune=True)
    weights = os.path.join(cfg.currentDir, cfg.train.save_path, cfg.dataset.name + '_forgetting_size_'+str(cfg.forgetting_set_size)+'_' +cfg.unlearning_method+'_'+ cfg.model + '.pth')
    model.load_state_dict(torch.load(weights, map_location=cfg.device))
    torch.grad = False

    # Estrazione delle caratteristiche dal dataset di addestramento
    print("Current path: ", os.getcwd())
    features, labels = extract_features(model, train_loader, cfg.device)
    torch.save(features, f"data/features/{cfg.dataset.name}/train_features_{cfg.unlearning_method}_{cfg.forgetting_set_size}.pt")
    torch.save(labels, f"data/features/{cfg.dataset.name}/train_labels_{cfg.unlearning_method}_{cfg.forgetting_set_size}.pt")

    # Estrazione delle caratteristiche dal dataset di validazione
    features, labels = extract_features(model, val_loader, cfg.device)
    torch.save(features, f"data/features/{cfg.dataset.name}/val_features_{cfg.unlearning_method}_{cfg.forgetting_set_size}.pt")
    torch.save(labels, f"data/features/{cfg.dataset.name}/val_labels_{cfg.unlearning_method}_{cfg.forgetting_set_size}.pt")

    # Estrazione delle caratteristiche dal dataset di test
    features, labels = extract_features(model, test_loader, cfg.device)
    torch.save(features, f"data/features/{cfg.dataset.name}/test_features_{cfg.unlearning_method}_{cfg.forgetting_set_size}.pt")
    torch.save(labels, f"data/features/{cfg.dataset.name}/test_labels_{cfg.unlearning_method}_{cfg.forgetting_set_size}.pt")

if __name__ == '__main__':
    main()
