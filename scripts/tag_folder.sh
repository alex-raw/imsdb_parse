#!/usr/bin/env bash

for file in "${1}"/*; do
  python imsdb_parse.py -dx "${file}" 2> "${file}.log" &
done; wait

cat "${1}"/*.log | grep -v '^INFO' > tagged.log &
cat "${1}"/*.log | grep '^WARN' > warnings.log &
cat "${1}"/*.log | grep '^INFO: [^c]' | sort -g > results.log &
grep -P "\tRM." "${1}"/*.log | grep -Pv "\tRM.\s*$" > removed.log
rm "${1}"/*.log
