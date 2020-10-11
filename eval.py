import os
import time
import shutil
import time
import json
import random
import numpy as np
from easydict import EasyDict as edict
import argparse
from sklearn.metrics import classification_report,f1_score
import pickle
from torch.utils.tensorboard import SummaryWriter



## torch packages
import torch
import torch.nn.functional as F
from torch.autograd import Variable
import torch.nn as nn

## for visulisation
import matplotlib.pyplot as plt

## custom
from select_model_input import select_model,select_input
import dataset
from label_dict import emo_label_map,label_emo_map,class_names,class_indices
from xai_emo_rec import explain_model

torch.manual_seed(0)
np.random.seed(0)
random.seed(0)
torch.backends.cudnn.deterministic = False

def get_pred_softmax(logits):
    softmax_layer = nn.Softmax(dim=1)
    return softmax_layer(logits)

def eval_model(model, val_iter, loss_fn,config,mode="train",explain=False):

    confusion = config.confusion
    per_class = config.per_class
    y_true = []
    y_pred = []
    total_epoch_loss = 0
    total_epoch_acc = 0

    if confusion:
        conf_matrix = torch.zeros(config.output_size, config.output_size)
    if per_class:
           class_correct = list(0. for i in range(config.output_size))
           class_total = list(0. for i in range(config.output_size))

    model.eval()
    with torch.no_grad():
        for idx, batch in enumerate(val_iter):
            model = model.cuda()
            text, attn,target = select_input(batch,config)
            target = torch.autograd.Variable(target).long()

            if (target.size()[0] is not config.batch_size):
                continue

            if torch.cuda.is_available():
                if config.arch_name == "sl_bert" or config.arch_name=="a_bert" or config.arch_name == "asep_bert":
                    text = [text[0].cuda(),text[1].cuda()]
                elif config.arch_name == "vasep_bert":
                    text = [text[0].cuda(),text[1].cuda(),text[2].cuda()]
                else:
                    text = text.cuda()

                target = target.cuda()
                attn = attn.cuda()
            prediction = model(text,attn)
            correct = np.squeeze(torch.max(prediction, 1)[1].eq(target.view_as(torch.max(prediction, 1)[1])))
            pred_ind = torch.max(prediction, 1)[1].view(target.size()).data

            if mode == "explain":
                pred_softmax = get_pred_softmax(prediction)
                explain_model(model,text,target.data,batch["utterance_data_str"],pred_ind,pred_softmax) ## use jupyter-notebook while doing explainations
            else:
                if confusion:
                    for t, p in zip(target.data, pred_ind):
                            conf_matrix[t.long(), p.long()] += 1


                if per_class:
                    for i in range(config.batch_size):
                        label = target[i]
                        class_correct[label] += correct[i].item()
                        class_total[label] += 1

                loss = loss_fn(prediction, target)

                num_corrects = (pred_ind == target.data).sum()
                y_true.extend(target.data.cpu().tolist())
                y_pred.extend(pred_ind.cpu().tolist())

                acc = 100.0 * num_corrects/config.batch_size
                total_epoch_loss += loss.item()
                total_epoch_acc += acc.item()


        if confusion:
            import seaborn as sns
            sns.heatmap(conf_matrix, annot=True,xticklabels=list(emo_label_map.keys()),yticklabels=list(emo_label_map.keys()))
            plt.show()
        if per_class:
            for i in range(config.output_size):
                print('Test Accuracy of %5s: %2d%% (%2d/%2d)' % (
                label_emo_map[i], 100 * class_correct[i] / class_total[i],
                np.sum(class_correct[i]), np.sum(class_total[i])))

    if mode != "explain":
        f1_score_e = f1_score(y_true, y_pred, labels=class_indices,average='macro')
        return total_epoch_loss/len(val_iter), total_epoch_acc/len(val_iter),f1_score_e



def load_model(resume,model,optimizer):


    checkpoint = torch.load(resume)
    start_epoch = checkpoint['epoch']
    # for i,v in checkpoint['state_dict'].items():
    #     print(i,v.size())
    model.load_state_dict(checkpoint['state_dict'])
    model = model.cuda()
    model.eval()
    optimizer.load_state_dict(checkpoint['optimizer']) ## during retrain TODO

    return model,optimizer,start_epoch



if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Enter eval details')

    parser.add_argument('-r','--resume_path',type=str,help='Input resume path')
    parser.add_argument('-m','--mode',default='eval',type=str,help='Input resume path')
    parser.add_argument('-n','--rem_epoch',default=10,type=int,help='How much more epochs to run')
    parser.add_argument('-p','--patience',default=10,type=int,help='Early stopping patience')

    args = parser.parse_args()

    resume_path = args.resume_path
    mode = args.mode
    rem_epoch = args.rem_epoch
    patience = args.patience

    ## Load the resume model parameters
    log_path = resume_path.replace("model_best.pth.tar","log.json")
    with open(log_path,'r') as f:
        log = json.load(f)
    f.close()

    ## Initialising parameters
    learning_rate = log["param"]["learning_rate"]
    batch_size = log["param"]["batch_size"]
    input_type = log["param"]["input_type"]
    arch_name = log["param"]["arch_name"]
    hidden_size = log["param"]["hidden_size"]
    embedding_length = log["param"]["embedding_length"]
    output_size = log["param"]["output_size"]
    tokenizer = log["param"]["tokenizer"]
    embedding_type = log["param"]["embedding_type"]

    ## Loading data
    print('Loading dataset')
    start_time = time.time()
    vocab_size, word_embeddings,train_iter, valid_iter ,test_iter= dataset.get_dataloader(batch_size,tokenizer,embedding_type,arch_name)
    finish_time = time.time()
    print('Finished loading. Time taken:{:06.3f} sec'.format(finish_time-start_time))

    eval_config = edict(log["param"])
    eval_config.param = log["param"]
    eval_config.resume_path = resume_path

    if mode == "explain":
        model = select_model(eval_config,vocab_size,word_embeddings,grad_check=False)
    else:
        model = select_model(eval_config,vocab_size,word_embeddings)
    loss_fn = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()),lr=learning_rate)
    lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer,eval_config.step_size, gamma=0.5)

    model,optimizer,start_epoch = load_model(resume_path,model,optimizer)

    if mode == "retrain": ## retrain from checkpoint TODO
        from train import train_model
        eval_config.patience = patience
        eval_config.nepoch = rem_epoch
        eval_config.confusion = False
        eval_config.per_class = True
        eval_config.start_epoch = start_epoch

        data  = (train_iter,valid_iter,test_iter)
        model_run_time = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
        writer = SummaryWriter('./runs/'+input_type+"/"+arch_name+"/")
        save_home = "./save/"+input_type+"/"+arch_name+"/"+model_run_time

        train_model(eval_config,data,model,loss_fn,optimizer,lr_scheduler,writer,save_home)

    elif mode == "eval":

        print(f'Train Acc: {log["train_acc"]:.3f}%, Valid Acc: {log["valid_acc"]:.3f}%, Test Acc: {log["test_acc"]:.3f}%')

        eval_config.confusion = True
        eval_config.per_class = True

        # val_loss, val_acc = eval_model(model, valid_iter,loss_fn,eval_config) ## uncommeent if validation needed

        ## testing
        test_loss, test_acc,f1_score = eval_model(model, test_iter,loss_fn,eval_config,mode)
        log["f1_score"] = f1_score
        with open(log_path, 'w') as fp:
            json.dump(log, fp,indent=4)
        fp.close()

    elif mode == "explain":

        print(f'Train Acc: {log["train_acc"]:.3f}%, Valid Acc: {log["valid_acc"]:.3f}%, Test Acc: {log["test_acc"]:.3f}%')

        eval_config.confusion = False
        eval_config.per_class = False

        ## explaining
        eval_model(model, test_iter,loss_fn,eval_config,mode,explain=True)
