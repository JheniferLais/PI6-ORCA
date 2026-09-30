# fonte: https://huggingface.co/OwenElliott/image-safety-classifier-s

from PIL import Image
import timm
import torch

img = Image.open("testImages/sexywoman.jpg")

model = timm.create_model(
    "hf-hub:OwenElliott/image-safety-classifier-s",
    pretrained=True
)

model = model.eval()

data_config = timm.data.resolve_model_data_config(model)
transforms = timm.data.create_transform(**data_config, is_training=False)

with torch.no_grad():
    output = model(transforms(img).unsqueeze(0)).softmax(dim=-1).cpu()

class_names = model.pretrained_cfg["label_names"]
print("Probabilities:", output[0])
print("Class:", class_names[output[0].argmax()])
