# Emotion Recognition
## Description

## Requirements
  * Python==3.7.7
  * PyTorch==1.4.0

## Setup

For training the model, go to config.py to set the required parameters 

```

python train.py

```
For evalutaion run the below code with "eval" mode. The other modes are "retrain" and "explain" which are in progress.

```

python eval.py -r <model path> -m <mode>

```
## Credits

This application uses Open Source components. You can find the source code of their open source projects along with license information below. We acknowledge and are grateful to these developers for their contributions to open source.

Project: Text-Classification-Pytorch <https://github.com/prakashpandey9/Text-Classification-Pytorch>  
License <https://github.com/prakashpandey9/Text-Classification-Pytorch/blob/master/LICENSE.txt>

Project:EmpatheticDialogues <https://github.com/facebookresearch/EmpatheticDialogues>
License <https://github.com/facebookresearch/EmpatheticDialogues/blob/master/LICENSE>

Project:MoEL <https://github.com/HLTCHKUST/MoEL>
License <https://github.com/HLTCHKUST/MoEL/blob/master/LICENSE>


## References

[BERT Text Classification Using Pytorch](https://towardsdatascience.com/bert-text-classification-using-pytorch-723dfb8b6b5b)
