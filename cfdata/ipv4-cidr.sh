#!/bin/bash
grep ms ip.csv | awk -F. '{printf $1"."$2"."$3".0/24\n"}' | sort -u > ipv4.txt