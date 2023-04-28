import os
import sys
import argparse
import time
import random
import numpy as np
import torch as T
from torch import nn
from torch.nn import functional as F
import gymnasium as gym
from datetime import datetime
from dt import DecisionTransformer
from critic import Critic
from vit import ViT
from trainer import Trainer
from utils import ReplayBuffer, init_env

T.manual_seed(42)

# this probably does nothing
T.backends.cudnn.benchmark = True

T.autograd.set_detect_anomaly(True)

T.backends.cuda.matmul.allow_tf32 = True

# The flag below controls whether to allow TF32 on cuDNN. This flag defaults to True.
T.backends.cudnn.allow_tf32 = True

parser = argparse.ArgumentParser(
    prog="Train Decision Transformer", description="Does it", epilog="Made by Ashley :)"
)

parser.add_argument("-t", "--timesteps", default=100)  # option that takes a value
parser.add_argument("-lm", "--load_model", action="store_true")  # on/off flag
parser.add_argument("-sm", "--save_model", action="store_true")  # on/off flag

args = parser.parse_args()

EPOCHS = int(args.timesteps)
save_interval = 50
device = "cuda" if T.cuda.is_available() else "cpu"
dtype = T.bfloat16

# T.set_autocast_gpu_dtype(amp_dtype)
# T.set_autocast_cache_enabled(True)

# losses = torch.tensor([], device=device)
# rewards = torch.tensor([], device=device)

env_name = "CarRacing-v2"
d_state = 768
d_reward = 1
# n_positions = 8192

steps_per_action = 5

n_env = 2

env, d_obs, d_img, d_act = init_env(env_name, n_env=n_env)

model = DecisionTransformer(
    d_state=d_state,
    d_act=d_act,
    d_reward=d_reward,
    dtype=dtype,
    device=device,
)

if args.load_model:
    model.load()

vit = ViT(d_img=d_img, n_env=n_env, dtype=dtype, device=device)

trainer = Trainer(model.parameters(), epochs=EPOCHS)

replay_buffer = ReplayBuffer(
    n_env=n_env,
    d_state=d_state,
    d_act=d_act,
    d_reward=d_reward,
    dtype=dtype,
    device=device,
)

for e in range(EPOCHS):
    T.cuda.empty_cache()

    obs, _ = env.reset()
    replay_buffer.clear()

    terminated = truncated = T.tensor([False] * n_env)
    while not (terminated + truncated).all():
        s_hat, a, mu, cov, r_hat, artg_hat = replay_buffer.predict(model)

        a_np = a.detach().cpu().numpy()
        a = a.to(dtype=dtype)

        for _ in range(steps_per_action):
            obs, r, terminated, truncated, info = env.step(a_np)

        terminated, truncated = T.tensor(terminated), T.tensor(truncated)

        s = vit(obs)

        r = T.tensor(r, dtype=dtype, device=device, requires_grad=False).reshape(
            [n_env, d_reward]
        )

        replay_buffer.append(s, a, r, artg_hat)

        # print("states", hist.states.shape[1], ", ", end="")
        # delete
        # if hist.states.shape[1] == 89:
        #     terminated = True

        # if replay_buffer.states.shape[1] == 200:
        #     terminated = True

        # don't delete
        # if replay_buffer.length() == n_positions:
        #     terminated = True

    # update Rs
    total_reward, av_r = replay_buffer.artg_update()

    # train (also do it right)
    artg_loss, policy_loss = trainer.learn(replay_buffer)

    print(
        e,
        "artg loss:",
        artg_loss.item(),
        "policy loss:",
        policy_loss.item(),
        "total_reward:",
        total_reward.item(),
        "average return",
        av_r.item(),
    )

    if e % save_interval == 0:
        if args.save_model:
            model.save()
