#!/bin/sh

if [ -f twistd.pid ]
then
    sudo kill -9 $(sudo cat twistd.pid) 2>/dev/null
    sudo twistd -y pranky.py
else
    sudo twistd -y pranky.py
fi
