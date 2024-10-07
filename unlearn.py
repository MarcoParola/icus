import hydra
import torch
import os
from torch.utils.data import DataLoader
from torch.utils.data.sampler import SubsetRandomSampler

#from src.utils import get_early_stopping, get_save_model_callback
from src.models.model import load_model
from src.datasets.dataset import load_dataset
from src.metrics.metrics import compute_metrics
from src.log import get_loggers
from src.utils import get_forgetting_subset
from src.unlearning.factory import get_unlearning_method
from omegaconf import OmegaConf
from src.utils import get_retain_and_forget_datasets
from src.dataset_wrapper import DatasetWrapper
from src.models.resnet import ResNet, ResidualBlock


@hydra.main(config_path='config', config_name='config', version_base=None)
def main(cfg):

    print("Inizio unlearning")
    # Set seed
    if cfg.seed == -1:
        random_data = os.urandom(4)
        seed = int.from_bytes(random_data, byteorder="big")
        cfg.seed = seed
    torch.manual_seed(cfg.seed)    

    # loggers
    loggers = get_loggers(cfg)

    # Load dataset
    data_dir = os.path.join(cfg.currentDir, cfg.dataset.path)
    train, val, test = load_dataset(cfg.dataset.name, data_dir, cfg.dataset.resize)
    # TODO fai il wrap con la classe custom: ImgTextDataset
    test_loader = torch.utils.data.DataLoader(test, 
        batch_size=cfg.train.batch_size, 
        shuffle=False, 
        num_workers=cfg.train.num_workers)

    train_loader = torch.utils.data.DataLoader(train, 
        batch_size=cfg.train.batch_size, 
        shuffle=False, 
        num_workers=cfg.train.num_workers)

    # Load model
    print("Carico il modello")
    #model = load_model(cfg.model, cfg.dataset.name)
    model=ResNet(ResidualBlock)
    model.load_state_dict(torch.load(os.path.join(cfg.currentDir, "checkpoints", cfg.dataset.name + '_' + cfg.model + '.pth'), map_location=cfg.device))
    model.to(cfg.device)

    print("Calcolo le metriche")
    # compute classification metrics
    num_classes = cfg[cfg.dataset.name].n_classes
    forgetting_subset = get_forgetting_subset(cfg.forgetting_set, cfg[cfg.dataset.name].n_classes, cfg.forgetting_set_size)
    #metrics = compute_metrics(model, test_loader, num_classes, forgetting_subset)
    #for k, v in metrics.items():
    #    print(f'{k}: {v}')

    #NOTA BENE: FORSE FORGETTING SUBSET NON SERVE PIU' PERCHE' LO RICAVO DIRETTAMENTE DAI DATI
    print("Wrapper datasets")
    retain_dataset, forget_dataset, forget_indices = get_retain_and_forget_datasets(train, forgetting_subset, cfg.forgetting_set_size)
    print("Indici da scordare:", forget_indices)
    retain_indices = [i for i in range(len(train)) if i not in forget_indices]
    if cfg.unlearning_method == 'icus':
        wrapped_train = DatasetWrapperIcus(train, forget_indices, cfg.icus.input_dim, cfg.icus.nclass)
    else:
        wrapped_train = DatasetWrapper(train, forget_indices)
        retain_loader = DataLoader(wrapped_train, batch_size=cfg.train.batch_size,sampler=SubsetRandomSampler(retain_indices), num_workers=4) 
        forget_loader = DataLoader(wrapped_train, batch_size=cfg.train.batch_size, sampler=SubsetRandomSampler(forget_indices), num_workers=4)
        wrapped_train_loader = DataLoader(wrapped_train, batch_size=cfg.train.batch_size, shuffle=True, num_workers=4)

    # unlearning process
    unlearning_method = cfg.unlearning_method
    unlearning = get_unlearning_method(unlearning_method, model, retain_loader, forget_loader, test_loader, train_loader, cfg)
    if unlearning_method == 'scrub':
        unlearning.unlearn(wrapped_train_loader)
    elif unlearning_method == 'badT':
        unlearning.unlearn(wrapped_train_loader, test_loader, forgetting_subset)
    elif unlearning_method == 'ssd':
        unlearning.unlearn(wrapped_train_loader, test_loader, forget_loader)
    else:
        raise ValueError(f"Unlearning method '{unlearning_method}' not recognised.")
    # recompute metrics




if __name__ == '__main__':
    main()