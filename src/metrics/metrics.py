import torch
import torch.nn.functional as F
import numpy as np
import random
import json
import hydra
from sklearn.svm import SVC
from torch.utils.data.sampler import SubsetRandomSampler
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


def compute_predictions(model, loader):
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    y_true = list()
    y_pred = list()
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            y = y.to(device)
            logits = model(x)
            _, preds = torch.max(logits, 1)
            y_true.extend(y.cpu().numpy())
            y_pred.extend(preds.cpu().numpy())
    return y_true, y_pred


def compute_classification_metrics(model, test_loader, num_classes, forgetting_subset):
    print("Starting metrics computation")
    y_true, y_pred = compute_predictions(model, test_loader)

    # compute metrics three times (on whole dataset, on the forgetting subset, on the retaining subset)
    metrics = dict()
    # whole dataset
    metrics['accuracy'] = accuracy_score(y_true, y_pred)
    # forgetting subset
    y_true_forgetting = [y_true[i] for i in range(len(y_true)) if y_true[i] in forgetting_subset]
    y_pred_forgetting = [y_pred[i] for i in range(len(y_pred)) if y_true[i] in forgetting_subset]
    metrics['accuracy_forgetting'] = accuracy_score(y_true_forgetting, y_pred_forgetting)
    # retaining subset
    y_true_retaining = [y_true[i] for i in range(len(y_true)) if y_true[i] not in forgetting_subset]
    y_pred_retaining = [y_pred[i] for i in range(len(y_pred)) if y_true[i] not in forgetting_subset]
    metrics['accuracy_retaining'] = accuracy_score(y_true_retaining, y_pred_retaining)
    return metrics

def compute_metrics(model, test_loader, num_classes, forgetting_subset):
    classification_metrics = compute_classification_metrics(model, test_loader, num_classes, forgetting_subset)
    mia_metrics = None # TODO implement MIA metrics
    #metrics = {**classification_metrics, **mia_metrics}
    print("classification_metrics")
    metrics = {**classification_metrics}
    return metrics


def get_case(data, dataset, unlearning_method, forgetting_set):
    """
    Restituisce il caso specifico per un metodo di unlearning e un forgetting_set, nel dataset specificato.
    """
    if dataset not in data["datasets"]:
        return None

    dataset_data = data["datasets"][dataset]

    if unlearning_method == "original_model":
        for case in dataset_data["original_model"]:
            if str(case["forgetting_set"]) == forgetting_set:
                return case
    else:
        for method in dataset_data["unlearning_methods"]:
            if method["method_name"] == unlearning_method:
                for case in method["cases"]:
                    if str(case["forgetting_set"]) == forgetting_set:
                        return case

    return None

def update_case(data, dataset, unlearning_method, forgetting_set, new_accuracy_retain, new_accuracy_forget):
    """
    Aggiorna un caso esistente con nuovi valori di accuracy_retain e accuracy_forget nel dataset specificato.
    """
    if dataset not in data["datasets"]:
        return False

    dataset_data = data["datasets"][dataset]

    if unlearning_method == "original_model":
        for caso in dataset_data["original_model"]:
            if caso["forgetting_set"] == forgetting_set:
                caso["accuracy_retain"] = new_accuracy_retain
                with open("src/metrics/metrics.json", "w") as file:
                    json.dump(data, file, indent=2)
                return True
    else:
        for method in dataset_data["unlearning_methods"]:
            if method["method_name"] == unlearning_method:
                for caso in method["cases"]:
                    if str(caso["forgetting_set"]) == forgetting_set:
                        caso["accuracy_retain"] = new_accuracy_retain
                        caso["accuracy_forget"] = new_accuracy_forget
                        with open("src/metrics/metrics.json", "w") as file:
                            json.dump(data, file, indent=2)
                        return True

    return False

def add_case(data, dataset, unlearning_method, forgetting_set, accuracy_retain, accuracy_forget):
    """
    Aggiunge un nuovo caso al metodo di unlearning specificato nel dataset specificato.
    """
    if dataset not in data["datasets"]:
        return False

    dataset_data = data["datasets"][dataset]

    if unlearning_method == "original_model":
        # Controlla se il caso esiste già
        for caso in dataset_data["original_model"]:
            if caso["forgetting_set"] == forgetting_set:
                return False  # Caso già esistente
        # Aggiungi il nuovo caso
        dataset_data["original_model"].append({
            "forgetting_set": forgetting_set,
            "accuracy_retain": accuracy_retain
        })
        with open("src/metrics/metrics.json", "w") as file:
            json.dump(data, file, indent=2)
        return True
    else:
        for method in dataset_data["unlearning_methods"]:
            if method["method_name"] == unlearning_method:
                # Controlla se il caso esiste già
                for case in method["cases"]:
                    if str(case["forgetting_set"]) == forgetting_set:
                        return False  # Caso già esistente
                # Aggiungi il nuovo caso
                method["cases"].append({
                    "forgetting_set": forgetting_set,
                    "accuracy_retain": accuracy_retain,
                    "accuracy_forget": accuracy_forget
                })
                with open("src/metrics/metrics.json", "w") as file:
                    json.dump(data, file, indent=2)
                return True

    return False


def calculate_aus(data, dataset, unlearning_method, forgetting_set):
    if dataset not in data["datasets"]:
        raise ValueError(f"Dataset '{dataset}' non trovato.")
    dataset_data = data["datasets"][dataset]
    original = get_case(dataset_data, "original_model", forgetting_set)
    unl = get_case(dataset_data, unlearning_method, forgetting_set)
    if not original:
        raise ValueError(f"Original model case non trovato per il forgetting_set {forgetting_set}.")
    if not unl:
        raise ValueError(f"Case non trovato per il metodo '{unlearning_method}' e il forgetting_set {forgetting_set}.")
    return (1 - (original["accuracy_retain"] - unl["accuracy_retain"])) / (1 + abs(unl["accuracy_forget"]))


    

@hydra.main(config_path='../../config', config_name='config', version_base=None)
def main(cfg):
    
    for method in ["icus", "scrub", "ssd", "badT"]:
        aus=calculate_aus(method, str(cfg.forgetting_set))
        print("Method: "+method+" AUS: "+str(aus))
    """
    #CODICI USATI PER TESTARE CHE ANDASSE
    print("Modifica test")
    with open("src/metrics/metrics.json", "r") as file:
        data = json.load(file)
    done = update_case(data, "ssd", str(cfg.forgetting_set), 0.6, 0.1)
    print("Modifica test 2")
    done = add_case(data, "ssd", "[2, 3, 4]", 0.01, 0.1)
    print(done)
    """


if __name__ == '__main__':
    main()
