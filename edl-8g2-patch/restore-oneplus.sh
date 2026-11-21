#!/bin/bash


for i in 0 1 2 3 4 5 ; do python3 edl --loader=firehose --memory=UFS qfil $1/wipe_rawprogram_PHY$i.xml $1/qpatch$i.xml $1 --debugmode; done;
for i in 0 1 2 3 4 5 ; do python3 edl --loader=firehose --memory=UFS qfil $1/rawprogram$i_BLANK_GPT.xml $1/patch$i.xml $1 --debugmode; done;
for i in 0 1 2 3 4 5 ; do python3 edl --loader=firehose --memory=UFS qfil $1/rawprogram$i_WIPE_PARTITIONS.xml $1/patch$i.xml $1 --debugmode; done;
for i in 0 1 2 3 4 5 ; do python3 edl --loader=firehose --memory=UFS qfil $1/rawprogram$i.xml $1/patch$i.xml $1 --debugmode; done;
#for i in 0 1 2 3 4 5 ; do python3 edl --loader=firehose printgpt --memory=UFS --lun=$i; done;
