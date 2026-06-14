FROM pytorch/pytorch:2.2.1-cuda12.1-cudnn8-runtime

# For GPU support, please choose the proper tag from https://hub.docker.com/r/pytorch/pytorch/tags

RUN apt-get clean && apt-get update && apt-get install -y \  
    curl \  
    vim \  
    git \  
    build-essential \
    coreutils \
    && rm -rf /var/lib/apt/lists/* 

# [FORK] use our sibling qlib fork (ybwbqg9379/qlib) instead of upstream pinned to an
# old commit (2fb9380b, 2026-02). Our fork's base is d5379c52 (2026-04) which our US
# us_data is verified to work with; the upstream pin's qlib mis-parsed RD-Agent's
# generated US handler config ("instrument: {freq dict} does not contain data for day").
# Our fork's qlib core == upstream@d5379c52 (we only added examples/collectors). FORK.md §6/§9.6.
RUN git clone https://github.com/ybwbqg9379/qlib.git

WORKDIR /workspace/qlib

RUN python -m pip install --upgrade cython
RUN python -m pip install -e .

RUN pip install catboost
RUN pip install xgboost
RUN pip install tables

# [FORK] Newer MLflow refuses the file-store tracking backend (./mlruns) and aborts
# qrun unless this opt-out is set. qlib's backtest uses the file store. See FORK.md §6.
ENV MLFLOW_ALLOW_FILE_STORE=true
