# fonte: https://huggingface.co/OwenElliott/image-safety-classifier-s

from urllib.request import urlopen, Request
from PIL import Image
import timm
import torch

# URL da imagem, pode ser qualquer link de imagem da internet nesta variável que virá o url da imagem extraída
url = "https://cozinharoman.com/wp-content/uploads/2015/10/Red-Velvet-Sangrento-cozinharoman-min-1536x851.jpg"

# Usando o mozilla pra fazer o request da imagem para o domínio (não sei ainda se vai precisar dessa parte)
request = Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0"
    }
)

img = Image.open(urlopen(request))

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
