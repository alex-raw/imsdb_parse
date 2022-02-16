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
"unclassified", which also provides an indicator for how well the sections were
detected.

## Usage

```
git clone https://github.com/alex-raw/imsdb_parse
cd imsdb_parse
python imsdb_parse -h

# create xml file with tagged results in same directory as input file
python imsdb_parse -x INFILE.html

# annotate semi-automatically and save results as xml file
python imsdb_parse -xa INFILE.html

# parse automatically and save raw tagging information for debugging
python imsdb_parse -xd INFILE.html 2> debug.log
```

### Bash wrapper to work with entire folder

`scripts/tag_folder` creates xml output for each file in folder and creates
seperate files containing simple statistics, raw tags in tsv format, warnings, and removed lines.

```
# parse entire folder and wrangle debugging information
sh scripts/tag_folder FOLDER_WITH_HTML_FILES

```

## Links

- [Internet Movie Script Database](https://imsdb.com)

## Todos

- include different websites as sources
- detect and handle files with different styles, such as title case characters, or "character: dialogue"
- further modularize, isolate xml formatting, further isolate cmdline features

## Dependencies

- For imsdb_crawl.py: `aiohttp, bs4`
