## Features

Currently this repo includes two command line tools to download imsdb movie and
tv scripts and tag the contents as heading, character, parentheticals, dialogue,
and slug lines. The parsed data can be accessed as python class `Screenplay`
and/or saved in xml-format.

`imsdb_parse.py` provides an interactive cmdline interface for semi-automatic
or fully manual tagging via the `-a --annotate` and `-f --force` options
resectively.

The intended purpose of this module is to pre-process data for the compilation
of a linguistic corpus. One of the main goals, therefore, is to minimize false
positives in dialogue detection. Ambiguous lines are parsed as `unc`
"unclassified", which also provides an indicator for how good

## Links

- [Internet Movie Script Database](https://imsdb.com)

## Todos

- crawl meta-data: title, authors, genre
- include different websites as sources
- detect and handle files with different styles, such as title case characters, or "character: dialogue"
- further modularize, isolate xml formatting, further isolate cmdline features

## Dependencies

- For imsdb_crawl.py: `aiohttp, bs4`
