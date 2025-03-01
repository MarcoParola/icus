import hydra
import torch
import os
from torch.optim import AdamW
from torch.utils.data import DataLoader
from torch.utils.data import Dataset
from src.utils import get_forgetting_subset
import wandb
from torch.utils.data import Subset
from tqdm import tqdm

from src.datasets.dataset import load_dataset
from src.models.classifier import Classifier
from src.metrics.metrics import compute_metrics
from src.loss.loss import NegGradLoss, NegGradPlusLoss
from src.log import get_loggers
from omegaconf import OmegaConf


@hydra.main(config_path='config', config_name='config')
def main(cfg):
    # Set seed
    if cfg.seed == -1:
        random_data = os.urandom(4)
        seed = int.from_bytes(random_data, byteorder="big")
        cfg.seed = seed
    torch.manual_seed(cfg.seed)    

    wandb_logger = get_loggers(cfg) # loggers

    # Load dataset
    data_dir = os.path.join(cfg.currentDir, cfg.dataset.path)
    train, val, test = load_dataset(cfg.dataset.name, data_dir, cfg.dataset.resize)
    # retrieving forgetting set for filtering
    forgetting_set = get_forgetting_subset(cfg.forgetting_set, cfg.dataset.classes, cfg.forgetting_set_size)
    print("Forgetting set: "+str(forgetting_set))

    
    model = Classifier(cfg.weights_name, num_classes=cfg.dataset.classes, finetune=True)
    model.to(cfg.device)


    optimizer = AdamW(model.parameters(), lr=cfg.train.lr)
    criterion = None

    

    if cfg.unlearning_method == 'retrain' or cfg.unlearning_method == 'finetuning':
        criterion = torch.nn.CrossEntropyLoss()
        # Crea una lista di indici che non appartengono al forgetting_set
        idx_train = [i for i, t in enumerate(train.targets) if t not in forgetting_set]
        idx_val = [i for i, t in enumerate(val.targets) if t not in forgetting_set]
        idx_test = [i for i, t in enumerate(test.targets) if t not in forgetting_set]
        train = Subset(train, idx_train)
        val = Subset(val, idx_val)
        test = Subset(test, idx_test)

    if cfg.unlearning_method != 'retrain':
        weights = os.path.join(cfg.currentDir, cfg.train.save_path, cfg.dataset.name + '_' + cfg.model + '.pth')
        model.load_state_dict(torch.load(weights, map_location=cfg.device))

    if cfg.unlearning_method == 'neggrad':
        criterion = NegGradLoss()
        idx_train = [i for i, t in enumerate(train.targets) if t in forgetting_set]
        idx_val = [i for i, t in enumerate(val.targets) if t in forgetting_set]
        idx_test = [i for i, t in enumerate(test.targets) if t in forgetting_set]
        train = Subset(train, idx_train)
        val = Subset(val, idx_val)
        test = Subset(test, idx_test)
        criterion = NegGradLoss()
    if cfg.unlearning_method == 'neggradplus':
        criterion = NegGradPlusLoss(cfg[cfg.dataset.name].n_classes, forgetting_set)


    # dataloader of filtered dataset
    train_loader = DataLoader(train, batch_size=cfg.train.batch_size, shuffle=True, num_workers=cfg.train.num_workers)
    val_loader = DataLoader(val, batch_size=cfg.train.batch_size, shuffle=False, num_workers=cfg.train.num_workers)
    test_loader = DataLoader(test, batch_size=cfg.train.batch_size, shuffle=False, num_workers=cfg.train.num_workers)


    # Early stopping
    if cfg.unlearning_method != 'finetuning':
        for epoch in range(cfg.train.max_epochs):
            print(f"Epoch {epoch+1}/{cfg.train.max_epochs}")
            model.train()
            train_loss = 0
            for x, y in tqdm(train_loader):
                optimizer.zero_grad()
                x = x.to(cfg.device)
                y = y.to(cfg.device)
                y_pred = model(x)
                loss = criterion(y_pred, y)
                train_loss += loss.item()
                loss.backward()
                optimizer.step()

            train_loss /= len(train_loader)
            wandb_logger.log_metrics({"train_loss": train_loss})

            model.eval()
            with torch.no_grad():
                val_loss = 0
                correct = 0
                total = 0
                for i, (x, y) in enumerate(tqdm(val_loader)):
                    x = x.to(cfg.device)
                    y = y.to(cfg.device)
                    y_pred = model(x)
                    loss = criterion(y_pred, y)
                    val_loss += loss.item()
                    _, predicted = y_pred.max(1)
                    total += y.size(0)
                    correct += predicted.eq(y).sum().item()

                val_loss /= len(val_loader)
                val_acc = 100 * correct / total

                wandb_logger.log_metrics({"val_loss": val_loss, "val_acc": val_acc})

        # test
        model.eval()
        with torch.no_grad():
            test_loss = 0
            correct = 0
            total = 0
            for i, (x, y) in enumerate(tqdm(test_loader)):
                x = x.to(cfg.device)
                y = y.to(cfg.device)
                y_pred = model(x)
                loss = criterion(y_pred, y)
                test_loss += loss.item()
                _, predicted = y_pred.max(1)
                total += y.size(0)
                correct += predicted.eq(y).sum().item()

            test_loss /= len(test_loader)
            test_acc = 100 * correct / total

            wandb_logger.log_metrics({"test_loss": test_loss, "test_acc": test_acc})
    else:
        for epoch in range(cfg.train.max_epochs):
            print(f"Epoch {epoch+1}/{cfg.train.max_epochs}")
            model.train()
            train_loss = 0
            for x, y in tqdm(train_loader):
                optimizer.zero_grad()
                x = x.to(cfg.device)
                y = y.to(cfg.device)
                y_pred = model(x)
                loss = criterion(y_pred, y)
                train_loss += loss.item()
                loss.backward()
                optimizer.step()

            train_loss /= len(train_loader)
            wandb_logger.log_metrics({"train_loss": train_loss})

            model.eval()
            with torch.no_grad():
                val_loss = 0
                correct_ret = 0
                total_ret = 0
                correct_for = 0
                total_for = 0

                for i, (x, y) in enumerate(tqdm(val_loader)):
                    x = x.to(cfg.device)
                    y = y.to(cfg.device)

                    # Predizioni
                    y_pred = model(x)
                    loss = criterion(y_pred, y)
                    val_loss += loss.item()

                    # Predizioni e classi predette
                    _, predicted = y_pred.max(1)

                    # Itera su ciascun campione
                    for label, pred in zip(y, predicted):
                        if label.item() in cfg.forgetting_set:
                            # Classi dimenticate
                            total_for += 1
                            correct_for += (label == pred).item()
                        else:
                            # Classi conservate
                            total_ret += 1
                            correct_ret += (label == pred).item()

                # Calcolo medie
                val_loss /= len(val_loader)
                retain_acc = 100 * correct_ret / total_ret if total_ret > 0 else 0
                forget_acc = 100 * correct_for / total_for if total_for > 0 else 0
                wandb_logger.log_metrics({"val_loss": val_loss, "retain_acc": retain_acc, "forget_acc": forget_acc})
        
        # test
        correct_ret = 0
        total_ret = 0
        correct_for = 0
        total_for = 0
        for i, (x, y) in enumerate(tqdm(test_loader)):
            x = x.to(cfg.device)
            y = y.to(cfg.device)

            # Predictions
            y_pred = model(x)

            # Predictions and predicted classes
            _, predicted = y_pred.max(1)

            for label, pred in zip(y, predicted):
                if label.item() in cfg.forgetting_set:
                    # Forget classes
                    total_for += 1
                    correct_for += (label == pred).item()
                else:
                    # Retain classes
                    total_ret += 1
                    correct_ret += (label == pred).item()

        # Compute averages
        retain_acc = 100 * correct_ret / total_ret if total_ret > 0 else 0
        forget_acc = 100 * correct_for / total_for if total_for > 0 else 0
        wandb_logger.log_metrics({"retain_test_acc": retain_acc, "forget_test_acc": forget_acc})
        


    #create folder if not exist and save torch model
    os.makedirs(os.path.join(cfg.currentDir, cfg.train.save_path), exist_ok=True)
    if cfg.unlearning_method == 'finetuning':
        metrics=compute_metrics(model, test_loader, cfg.dataset.classes, cfg.forgetting_set)
        torch.save(model.state_dict(), os.path.join(cfg.currentDir, cfg.train.save_path, cfg.dataset.name + '_forgetting_set_'+ str(cfg.forgetting_set) +'_finetuning_'+ cfg.model + '.pth'))
    else:
        torch.save(model.state_dict(), os.path.join(cfg.currentDir, cfg.train.save_path, cfg.dataset.name + '_' + cfg.model + '_only_retain_set'+str(cfg.forgetting_set)+'.pth'))



if __name__ == '__main__':
    print('main')
    main()
