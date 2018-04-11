#!/bin/bash
set -xeu -o pipefail

cd /efs

wget https://raw.githubusercontent.com/chainer/chainermn/v1.3.0/examples/mnist/train_mnist.py

mpiexec -n 3 -N 1 --display-map python3 /efs/train_mnist.py --epoch 2 --batchsize 1000 --gpu
