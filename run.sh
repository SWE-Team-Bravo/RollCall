#!/bin/bash

pkill streamlit
cd ~/rollcall
git pull
nohup streamlit run Home.py --server.port 15084 --server.address 0.0.0.0 2>&1 out &
mongod --dbpath ~/mongodb/data --logpath ~/mongodb/logs/mongod.log --port 27017 --fork
