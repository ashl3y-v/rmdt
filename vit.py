import torch as T
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.distributions import Normal
import transformers


class ViT(nn.Module):
    def __init__(self, image_dim=[3, 96, 96], dtype=T.float32, device="cpu"):
        super().__init__()
        self.dtype = dtype
        self.device = device

        model_ckpt = "microsoft/beit-base-patch16-224-pt22k-ft22k"
        self.image_dim = image_dim
        self.image_processor = transformers.AutoImageProcessor.from_pretrained(
            model_ckpt, do_resize=True, device=device
        )
        self.vit = transformers.BeitModel.from_pretrained(model_ckpt)

        self.to(dtype=dtype, device=device)

    def forward(self, o):
        with T.cuda.amp.autocast():
            self.eval()
            with T.inference_mode():
                o = (
                    T.from_numpy(o)
                    .to(dtype=self.dtype, device=self.device)
                    .reshape(self.image_dim)
                )
                o = self.image_processor(o, return_tensors="pt").pixel_values.to(
                    dtype=self.dtype, device=self.device
                )
                e = self.vit(o).to_tuple()
                e = e[1].unsqueeze(0)

            # needed
            return e.clone()


if __name__ == "__main__":
    vit = ViT()
    print(vit.forward)
