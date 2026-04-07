#!/bin/bash -l
source ~/.bashrc

pkill streamlit || true
pkill mongod || true
cd ~/rollcall
git pull
pip install -r requirements.txt
nohup /home/rollcall/.local/bin/streamlit run Home.py --server.port 15084 --server.address 0.0.0.0 > out 2>&1 &
/home/rollcall/.local/bin/mongod --dbpath ~/mongodb/data --logpath ~/mongodb/logs/mongod.log --port 27017 --fork
