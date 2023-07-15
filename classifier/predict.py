from fastcore.all import *
from fastdownload import download_url
from fastai.vision.all import *
from time import sleep

learn = load_learner('ok_peace_model.pkl')

is_ok, _, probs = learn.predict(PILImage.create('peacealina.jpg'))
print(f"This is a: {is_ok}.")
print(f"Probability it's an ok sign: {probs[0]:.4f}")

