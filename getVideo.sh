#!/bin/bash

aws s3 cp s3://fvideo-encoded/$1 ./encode
