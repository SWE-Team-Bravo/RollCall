#!/bin/bash

pkill streamlit
cd ~/rollcall
git pull
pip install -r requirements.txt
nohup streamlit run Home.py --server.port 15084 --server.address 0.0.0.0 > out 2>&1 &
mongod --dbpath ~/mongodb/data --logpath ~/mongodb/logs/mongod.log --port 27017 --fork
