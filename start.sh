#!/bin/sh

if [ -f twistd.pid ]
then
    sudo kill -9 $(sudo cat twistd.pid)
    sudo twistd -y pranky.py
else
    sudo twistd -y pranky.py
fi
