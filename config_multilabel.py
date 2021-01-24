tokenizer = ""
input_type = "speaker+listener"
embedding_type = "bert"
arch_name = "kbert_bilstm"
dataset = "semeval"

learning_rate = 5e-05

batch_size = 10

if dataset == "goemotions":
    output_size = 27
elif dataset == "semeval":
    output_size = 11

hidden_size = 768 # for bert-based models, cannot change as fine-tuning

embedding_length = None

step_size = 2
start_epoch = 0 # for start training
nepoch = 5
patience = 30

# Accuracy display
confusion = False #confusion matrix
per_class = False # per class accuracy


param = {"input_type":input_type,"tokenizer":tokenizer,"embedding_type":embedding_type,"arch_name":arch_name,"learning_rate":learning_rate,"batch_size":batch_size,"hidden_size":hidden_size,"embedding_length":embedding_length,"output_size":output_size,"step_size":step_size,"freeze":False,"dataset":dataset}

tuning = False