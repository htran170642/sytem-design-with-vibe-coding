#!/bin/bash

sudo systemctl stop postgresql
docker compose -f /home/hieptt/dev/practice/python/vide_coding_python/real_time_chat/docker-compose.yaml up -d
source venv/bin/activate