import os
import time
import shutil
import time
import json
import random
import time
import argparse
import numpy as np

## torch packages
import torch
import torch.nn.functional as F
from torch.autograd import Variable
from torch.utils.tensorboard import SummaryWriter
import torch.nn as nn
from transformers import get_linear_schedule_with_warmup

## for visualisation
import matplotlib.pyplot as plt

## custom
from eval import eval_model
from select_model_input import select_model,select_input
import dataset
import config as train_config
from label_dict import label_emo_map

np.random.seed(0)
random.seed(0)
torch.manual_seed(0)
torch.cuda.manual_seed(0)
torch.cuda.manual_seed_all(0)



def save_checkpoint(state, is_best,filename='checkpoint.pth.tar'):
	torch.save(state,filename)
	if is_best:
		shutil.copyfile(filename,filename.replace('checkpoint.pth.tar','model_best.pth.tar'))

def clip_gradient(model, clip_value):
	params = list(filter(lambda p: p.grad is not None, model.parameters()))
	for p in params:
		p.grad.data.clamp_(-clip_value, clip_value)



def train_epoch(model, train_iter, epoch,loss_fn,optimizer,config):

	total_epoch_loss = 0
	total_epoch_acc = 0
	model.cuda()
	steps = 0
	model.train()
	start_train_time = time.time()
	for idx, batch in enumerate(train_iter):

		text, attn, target = select_input(batch,config,arch_name)

		target = torch.autograd.Variable(target).long()

		if (target.size()[0] is not config.batch_size):# Last batch may have length different than config.batch_size
			continue

		if torch.cuda.is_available():
			if arch_name =="electra" or arch_name == "bert":
				text = text.cuda()
			else:
				text = [text[0].cuda(),text[1].cuda(),text[2].cuda(),text[3].cuda()]

			attn = attn.cuda()
			target = target.cuda()


		## model prediction
		model.zero_grad()
		optimizer.zero_grad()
		# print("Prediction")
		prediction = model(text,attn)
		# print("computing loss")
		loss = loss_fn(prediction, target)

		## evaluation
		num_corrects = (torch.max(prediction, 1)[1].view(target.size()).data == target.data).float().sum()
		acc = 100.0 * num_corrects/config.batch_size
		# print("Loss backward")
		startloss = time.time()
		loss.backward()
		# print(time.time()-startloss,"Finish loss")
		clip_gradient(model, 1e-1)
		# torch.nn.utils.clip_grad_norm_(model.parameters(),1)
		optimizer.step()
		# print("=====================")
		steps += 1
		if steps % 100 == 0:
			print (f'Epoch: {epoch+1:02}, Idx: {idx+1}, Training Loss: {loss.item():.4f}, Training Accuracy: {acc.item(): .2f}%, Time taken: {((time.time()-start_train_time)/60): .2f} min')
			start_train_time = time.time()

		total_epoch_loss += loss.item()
		total_epoch_acc += acc.item()

	return total_epoch_loss/len(train_iter), total_epoch_acc/len(train_iter)

def train_model(config,data,model,loss_fn,optimizer,lr_scheduler,writer,save_home):

	best_acc1 = 0
	patience_flag = 0
	train_iter,valid_iter,test_iter = data[0],data[1],data[2] # data is a tuple of three iterators

	# print("Start Training")
	for epoch in range(config.start_epoch,config.nepoch):

		## train and validation
		train_loss, train_acc = train_epoch(model, train_iter, epoch,loss_fn,optimizer,config)

		val_loss, val_acc ,val_f1_score,val_w_f1_score,val_top3_acc= eval_model(model, valid_iter,loss_fn,config,arch_name)
		print(f'Epoch: {epoch+1:02}, Train Loss: {train_loss:.3f}, Train Acc: {train_acc:.2f}%, Val. Loss: {val_loss:3f}, Val. Acc: {val_acc:.2f}%')
		## testing
		test_loss, test_acc,test_f1_score,test_w_f1_score,test_top3_acc = eval_model(model, test_iter,loss_fn,config,arch_name)
		print(f'Test Loss: {test_loss:.3f}, Test Acc: {test_acc:.2f}% Test F1 score: {test_f1_score:.4f}')

		## save best model
		is_best = val_acc > best_acc1
		os.makedirs(save_home,exist_ok=True)
		save_checkpoint({'epoch': epoch + 1,'arch': arch_name,'state_dict': model.state_dict(),'train_acc':train_acc,"val_acc":val_acc,'param':log_dict["param"],'optimizer' : optimizer.state_dict(),},is_best,save_home+"/checkpoint.pth.tar")

		best_acc1 = max(val_acc, best_acc1)
		if config.step_size != None:
			lr_scheduler.step()

		## tensorboard runs
		writer.add_scalar('Loss/train',train_loss,epoch)
		writer.add_scalar('Accuracy/train',train_acc,epoch)
		writer.add_scalar('Loss/val',val_loss,epoch)
		writer.add_scalar('Accuracy/val',val_acc,epoch)

		## save logs
		if is_best:


			patience_flag = 0
			log_dict["train_acc"] = train_acc
			log_dict["test_acc"] = test_acc
			log_dict["valid_acc"] = val_acc
			log_dict["test_f1_score"] = test_f1_score
			log_dict["valid_f1_score"] = val_f1_score
			log_dict["top3_acc"] = test_top3_acc
			log_dict["train_loss"] = train_loss
			log_dict["test_loss"] = test_loss
			log_dict["valid_loss"] = val_loss
			log_dict["epoch"] = epoch+1
			log_dict["note"] = note
			log_dict["weighted_test_f1_score"] = test_w_f1_score
			log_dict["weighted_valid_f1_score"] = val_w_f1_score


			with open(save_home+"/log.json", 'w') as fp:
				json.dump(log_dict, fp,indent=4)
			fp.close()
		else:
			patience_flag += 1

		## early stopping
		if patience_flag == config.patience or epoch == config.nepoch-1:
			print(log_dict)
			break


if __name__ == '__main__':

	# note = "without dom" ## to note any changes
	log_dict = {}
	log_dict["param"] = train_config.param
	print(train_config.learning_rate)
	print(train_config.arch_name)
	print(train_config.batch_size)
	## Loading data
	print('Loading dataset')
	start_time = time.time()
	vocab_size, word_embeddings,train_iter, valid_iter ,test_iter= dataset.get_dataloader(train_config.batch_size,train_config.tokenizer,train_config.dataset,train_config.arch_name)

	data = (train_iter,valid_iter,test_iter)
	finish_time = time.time()
	print('Finished loading. Time taken:{:06.3f} sec'.format(finish_time-start_time))

	if train_config.tuning:

	## Initialising parameters from train_config

		for lr in [3e-05]: ## for tuning

			np.random.seed(0)
			random.seed(0)
			torch.manual_seed(0)
			torch.cuda.manual_seed(0)
			torch.cuda.manual_seed_all(0)

			learning_rate = lr
			arch_name = train_config.arch_name
			log_dict["param"]["learning_rate"] = lr
			log_dict["param"]["arch_name"] = arch_name
			note = "Tuning learning_rate:"+str(lr)

			# learning_rate = train_config.learning_rate
			input_type = train_config.input_type

			## Initialising model, loss, optimizer, lr_scheduler
			model = select_model(train_config,arch_name,vocab_size,word_embeddings)
			loss_fn = nn.CrossEntropyLoss()
			total_steps = len(train_iter) * train_config.nepoch

			optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()),lr=learning_rate)
			if train_config.step_size != None:
				lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer,train_config.step_size, gamma=0.5)


			## Filepaths for saving the model and the tensorboard runs
			model_run_time = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
			writer = SummaryWriter('./runs/'+input_type+"/"+arch_name+"/")
			save_home = "./save/"+train_config.dataset+"/"+input_type+"/"+arch_name+"/"+model_run_time


			train_model(train_config,data,model,loss_fn,optimizer,lr_scheduler,writer,save_home)
	else:
		learning_rate = train_config.learning_rate

		arch_name = train_config.arch_name

		input_type = train_config.input_type

		## Initialising model, loss, optimizer, lr_scheduler
		model = select_model(train_config,arch_name,vocab_size,word_embeddings)

		if train_config.dataset != "goemotions":
			loss_fn = nn.CrossEntropyLoss()
		else:
			loss_fn = nn.BCEWithLogitsLoss()

		total_steps = len(train_iter) * train_config.nepoch

		optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()),lr=learning_rate)


		lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer,train_config.step_size, gamma=0.5)



		## Filepaths for saving the model and the tensorboard runs
		model_run_time = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
		writer = SummaryWriter('./runs/'+input_type+"/"+arch_name+"/")
		save_home = "./save/"+train_config.dataset+"/"+input_type+"/"+arch_name+"/"+model_run_time

		train_model(train_config,data,model,loss_fn,optimizer,lr_scheduler,writer,save_home)
