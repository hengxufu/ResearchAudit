"""TEST DATA ONLY: two-layer neural network; no downloaded dataset or framework.

Explicitly run this file through the executor. It writes to managed output only.
This validates a numerical training/replay pipeline, not PyTorch/CUDA equivalence.
"""
import os
from pathlib import Path
import numpy as np

def main():
    rng=np.random.default_rng(7)
    x=rng.normal(size=(128,3));target=np.sin(x[:,0:1])+0.3*x[:,1:2]
    w1=rng.normal(scale=.2,size=(3,8));b1=np.zeros((1,8));w2=rng.normal(scale=.2,size=(8,1));b2=np.zeros((1,1))
    folder=Path(os.environ['RESEARCHAUDIT_OUTPUT_DIR'])
    with (folder/'metrics.csv').open('w',encoding='utf-8') as f:
        f.write('loss\n')
        for epoch in range(40):
            hidden=np.tanh(x@w1+b1);prediction=hidden@w2+b2;error=prediction-target
            loss=float(np.mean(error**2));f.write(str(loss)+'\n');f.flush()
            output_gradient=2*error/len(x);hidden_gradient=(output_gradient@w2.T)*(1-hidden**2)
            w2-=.05*hidden.T@output_gradient;b2-=.05*output_gradient.sum(axis=0,keepdims=True)
            w1-=.05*x.T@hidden_gradient;b1-=.05*hidden_gradient.sum(axis=0,keepdims=True)
    np.savez(folder/'checkpoint.npz',w1=w1,b1=b1,w2=w2,b2=b2)
    print('TEST DATA: neural network training complete; final MSE',loss)
if __name__=='__main__':main()
