# -*- coding: utf-8 -*-
"""reponse_question

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1JAlgj6RW3BASxhjyF0Rhw2pwd7blYvC6

## Import
"""

import torch

from torch.utils.data import dataloader
from torch.utils.data import Dataset

import torchvision.transforms as transforms

from PIL import Image

import pandas as pd

from typing import Any, Callable, Optional, Tuple

#!pip install transformers
#!pip install datasets
#!pip install sentencepiece

import torch
torch.__version__

"""## Load Data"""

class VQADataset(Dataset):
  """
    This class loads a shrinked version of the VQA dataset (https://visualqa.org/)
    Our shrinked version focus on yes/no questions. 
    To load the dataset, we pass a descriptor csv file. 
    
    Each entry of the csv file has this form:

    question_id ; question_type ; image_name ; question ; answer ; image_id

  """
  def __init__(self, path : str, dataset_descriptor : str, image_folder : str, transform : Callable) -> None:
    """
      :param: path : a string that indicates the path to the image and question dataset.
      :param: dataset_descriptor : a string to the csv file name that stores the question ; answer and image name
      :param: image_folder : a string that indicates the name of the folder that contains the images
      :param: transform : a torchvision.transforms wrapper to transform the images into tensors 
    """
    super(VQADataset, self).__init__()
    self.descriptor = pd.read_csv(path + '/' + dataset_descriptor, delimiter=';')
    self.path = path 
    self.image_folder = image_folder
    self.transform = transform
    self.size = len(self.descriptor)
  
  def __len__(self) -> int:
    return self.size

  def __getitem__(self, idx : int) -> Tuple[Any, Any, Any]:
    """
      returns a tuple : (image, question, answer)
      image is a Tensor representation of the image
      question and answer are strings
    """
    image_name = self.path + '/' + self.image_folder + '/' + self.descriptor["image_name"][idx]

    image = Image.open(image_name).convert('RGB')

    image = self.transform(image)

    question = self.descriptor["question"][idx]

    answer = self.descriptor["answer"][idx]

    return (image, question, answer)

#from google.colab import drive
#drive.mount('/content/drive')

from torch.utils.data import DataLoader

# Précisez la localisation de vos données sur Google Drive
#path = "/content/drive/MyDrive/InAction_Donnee200"
#image_folder = "boolean_answers_dataset_images_200"
#descriptor = "boolean_answers_dataset_200.csv"

path = "/home/equipe2/harispe"
image_folder = "boolean_answers_dataset_images_10000"
descriptor = "boolean_answers_dataset_10000.csv"


batch_size = 2

# exemples de transformations
transform = transforms.Compose(
    [
     transforms.Resize((224,224)),   #TOUTES LES IMAGES 224/224
     transforms.ToTensor(),     
     transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ]
)

vqa_dataset = VQADataset(path, descriptor, image_folder, transform=transform)


vqa_dataloader = DataLoader(vqa_dataset,batch_size=batch_size, shuffle=True, num_workers=0)

"""## Preparation Test + Train et "yes" -> 0 "no" -> 1"""

from transformers import AutoTokenizer, AutoModelForSequenceClassification

# List of pretrained models: https://huggingface.co/models?filter=text-classification
tokenizer_albert = AutoTokenizer.from_pretrained("textattack/albert-base-v2-yelp-polarity")
model_albert = AutoModelForSequenceClassification.from_pretrained("textattack/albert-base-v2-yelp-polarity")

"""###Préparation des données :"""



def load_next_batch(file_object, batch_size=20):
    """Lazy function (generator) to read a file piece by piece.
    Default chunk size: 1k."""
    while True:

        data = [ [], [], [] ] # [enc_images, enc_texts, labels]
        item_count = 0

        for l in file_object:

            data_split = l.split(";")


            image = [float(v) for v in data_split[0].split()]

            question = [float(v) for v in data_split[1].split()]

            label = int(data_split[2])


            #image = data[0][0]
            reshape_image = []
            for i in range(3):
              layer = []
              for j in range(224):
                line = []
                for k in range(224):
                   line.append(image[k+j*224+i*3])
                layer.append(line)
              reshape_image.append(layer)
            tensor_image = torch.FloatTensor(reshape_image)

            #question = data[1][0]
            reshape_question = []
            for i in range(16):
              layer = []
              for j in range(1536):
                layer.append(question[j+i*16])
              reshape_question.append(layer)
            tensor_question = torch.FloatTensor(reshape_question) 

            #label = data[2][0]


            #combine_form = [tensor_image,tensor_question,label]
            #print("tensor :",combine_form)

            #data[0] = torch.cat((data[0], tensor_image), 0)


            data[0].append(tensor_image)
            data[1].append(tensor_question)
            data[2].append(label)
            item_count += 1

            if item_count == batch_size:

                yield data
                data = [ [], [], [] ]
                item_count = 0
        
        if item_count != 0:
                yield data
        
        break

"""## Modele"""

data_file_train = "/content/dataset_Train.csv"
data_file_test = "/content/dataset_Test.csv"

import torch.nn.functional as F

class LeNet5(torch.nn.Module):
  
  def __init__(self, D_out):
    super(LeNet5, self).__init__()

    #Traitement image
    self.conv1     = torch.nn.Conv2d(in_channels=3, out_channels=6, kernel_size=(5,5), stride=1, padding=2)
    self.avg_pool1 = torch.nn.AvgPool2d(kernel_size=(2,2), stride=2)
    self.conv2     = torch.nn.Conv2d(in_channels=6, out_channels=16, kernel_size=(5,5), stride=1)
    self.avg_pool2 = torch.nn.AvgPool2d(kernel_size=(2,2), stride=2)
    self.conv3     = torch.nn.Conv2d(in_channels=16, out_channels=120, kernel_size=(5,5), stride=1) 
    self.avg_pool3 = torch.nn.AvgPool2d(kernel_size=(2,2), stride=2)
    self.conv4     = torch.nn.Conv2d(in_channels=120, out_channels=240, kernel_size=(5,5), stride=1)
    self.flatten   = torch.nn.Flatten() #multipli tout   240*21*21

    #Traitement image
    self.linear1   = torch.nn.Linear(240*21*21, 200)

    #Traitement question
    self.linear3   = torch.nn.Linear( 16*1536 , 200)

    #Fusion Traitement
    self.linear2   = torch.nn.Linear( 200+200, D_out)

  def forward(self, x,y):
    
    x = F.relu(self.conv1(x) )
    x = self.avg_pool1(x)
    x = F.relu( self.conv2(x) )
    x = self.avg_pool2(x)
    x = F.relu( self.conv3(x) )
    x = self.avg_pool3(x)
    x = F.relu( self.conv4(x) )


    y = self.flatten(y) #16*1536
    x = self.flatten(x) #240*21*21


    x = F.relu( self.linear1(x) )
    y = F.relu( self.linear3(y) )


    z = torch.cat((x, y), 1)
    z = self.linear2(z)
    
    return z

"""###A partir du nouveau fichier csv"""

def train_optim_csv(model, epochs, log_frequency, device, learning_rate=1e-4):

  model.to(device) 

  loss_fn = torch.nn.CrossEntropyLoss(reduction='mean')
  optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
  
  for t in range(epochs):

      model.train()

      with open(data_file_train) as f:
          for batch in load_next_batch(f, batch_size = 20):
              #print(batch)

              images, questions, labels  = batch

              #print(questions)
              questions = torch.stack(questions)
              #questions = torch.FloatTensor(questions)

              questions = questions.to(device)

              images = torch.stack(images)
              images = images.to(device)
              labels = torch.LongTensor(labels)
              labels = labels.to(device)

              # FORWARD
              y_pred = model(images,questions)

              loss = loss_fn(y_pred, labels)

              #if batch_id % log_frequency == 0:
              print("Step epochs ",t)

              optimizer.zero_grad()
              loss.backward(retain_graph=True)
              optimizer.step()

      #ACCURACY Calcul
      model.eval()
      total = 0
      correct = 0

      with open(data_file_test) as f:
          for batch in load_next_batch(f, batch_size = 20):
              images ,questions, labels = batch

              images = torch.stack(images)
              questions = torch.stack(questions)
              labels = torch.LongTensor(labels)

              images = images.to(device)
              questions = questions.to(device)
              labels = labels.to(device)

              y_pred = model(images,questions)
              sf_y_pred = torch.nn.Softmax(dim=1)(y_pred) # softmax
              _, predicted = torch.max(sf_y_pred , 1)     # decision rule, max
        
              total += labels.size(0)
              correct += (predicted == labels).sum().item()
      
      print("[validation] accuracy: {:.3f}%\n".format(100 * correct / total))

"""## Lance modele"""

D_out = 2

model = LeNet5(D_out)

## Select the device
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

## train the model
train_optim_csv(model, epochs=10, log_frequency=60, device=device, learning_rate=1e-4)
