import torch
import time, copy
import torch.nn as nn
import tqdm
import numpy as np
import torch.optim as optim
from torch.utils.data import DataLoader
from torch.nn import functional as F
from src.unlearning_methods.base import BaseUnlearningMethod

class Scrub(BaseUnlearningMethod):

    def __init__(self, opt, model, retain_loader, forget_loader, test_loader, val_loader, logger, maximize=False, alpha=0.1, kd_T=4.0):
        super().__init__(opt, model)
        print("Inizializzazione di Scrub")
        self.og_model = copy.deepcopy(model)  # original model copy
        self.criterion = nn.CrossEntropyLoss()
        self.logger = logger
        self.epoch = 0
        self.val_loader = val_loader
        self.retain_loader = retain_loader
        self.forget_loader = forget_loader
        self.test_loader = test_loader
        self.maximize = maximize
        self.alpha = alpha
        self.kd_T = kd_T
        #self.msteps = opt.train_iters // 2  
        self.msteps = 50
        self.save_files = {"train_time_taken": 0, "val_top1": []}
        self.curr_step = 0  

    def unlearn(self, train_loader):
        print("Start unlearning process")
        self.maximize=False
        while self.curr_step < self.opt.train_iters:
            if self.curr_step < self.msteps:
                self.maximize = True
                self._train_one_phase(loader=self.forget_loader, train_loader=train_loader)
            else:
                #self.curr_step += 1
                self.maximize = False
                self._train_one_phase(loader=train_loader, train_loader=train_loader)
            if self.val_loader is not None:
                self.validate(self.val_loader)
            

    def distill_kl_loss(self, student_output, teacher_output, temperature):
        """Calculate the KL-divergence loss for knowledge distillation."""
        student_output = F.log_softmax(student_output / temperature, dim=1)
        teacher_output = F.softmax(teacher_output / temperature, dim=1)
        return F.kl_div(student_output, teacher_output, reduction='batchmean') * (temperature ** 2)

    def _train_one_phase(self, loader, train_loader):
        time_start = time.process_time()
        self.train_one_epoch(loader=loader)
        self.save_files['train_time_taken'] += time.process_time() - time_start
        #self.eval(self.test_loader)

    def forward_pass(self, inputs, target, infgt):
        
        inputs, target = inputs.to(self.opt.device), target.to(self.opt.device)        
        # Forward pass (with gradients)
        output = self.model(inputs)
        # Forward pass (without gradienti)
        with torch.no_grad():
            logit_t = self.og_model(inputs)
        # Calculate loss: standard (cross-entropy) + distillation (KL-divergence)
        loss = F.cross_entropy(output, target)
        loss += self.alpha * self.distill_kl_loss(output, logit_t, self.kd_T)
        if self.maximize:
            loss = -loss
        
        return output, loss


    