from fastcore.all import *
from fastdownload import download_url
from fastai.vision.all import *
from time import sleep

# Script for training CV model 
searches = 'ok hand sign real', 'peace hand sign real'
path = Path('ok_or_peace')

dls = DataBlock(
    blocks=(ImageBlock, CategoryBlock),
    get_items=get_image_files,
    splitter=RandomSplitter(valid_pct=0.2, seed=42),
    get_y=parent_label,
    item_tfms=[Resize(192, method='squish')]
).dataloaders(path, bs=32)

learn = vision_learner(dls, resnet18, metrics=error_rate)
learn.fine_tune(10)

learn.export('ok_peace_model.pkl')
