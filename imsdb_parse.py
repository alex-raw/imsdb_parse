#!/usr/bin/env python
import re
from sys import argv

# pre-compile regex to prevent compilation in every iteration
no_lower    = re.compile(r"^(?!.*[a-z]).+$")
non_ws      = re.compile(r"\S")
ws          = re.compile(r"\s+")
html_tag    = re.compile(r"<.*?>")
leading_num = re.compile(r"\d+[\.]*")
ids         = re.compile(r"^\d+\.?\w?\s*|\s*\d+\.?\w?\s*$")
# any matched () or unpaired at beginning or end
par_pattern = re.compile(r"^\(.*\)$|^\([^\)]+$|^[^\(]+\)$")
speaker_cap = re.compile(r"(.+)\s((\(.*?\)))")   # par after speaker
scene_cap1  = re.compile(r"(\d+)\s*(.+?)\s*\d+") # scene id at ^
scene_cap2  = re.compile(r"(.+?)\s*(\d+)")       # scene id ad $

# Regex matches for unambiguous patterns. earlier beat later patterns
patterns = [(x, re.compile(y)) for x, y in (
    ("scene", r"(INT|EXT)\."), # INT. or EXT., not INTERNAL, EXTERMINATE
    ("cue", r"^\d*\s*\d+.?\.?$"), # lone numbers
    ("cue", r"^[^\(]*CONT(INUE|')D[^\)]*$"), # not in pars, (or scene?)
    ("speaker", r"#|(1ST|2ND|3RD|\d\d?TH)"), # numbered characters
    ("scene",  r"^\d+"), # numbered scene titles or cuts
    ("cue", r":|FADE|CUT"), # all remaining caps with : are camera cues, some stray colon-less FADE/CUT
    ("empty", r"^(?!.*[A-Z]).+$")
)]

# suboptimal but hard to distunguish from other all caps lines
speaker_pattern = re.compile(r"^[A-Z\s]+([\.'-\/]\s?[A-Z\s]+)*(\(.*\))?$")

# tag and exclude pars, leave lower case for later, disambiguate all-caps lines
def pre_tag(line):
    if par_pattern.search(line):
        return "par"
    elif not no_lower.search(line):
        return "unc"

    for tag, pattern in patterns:
        if pattern.search(line):
            return tag
    return "caps"

# find indentation level, then strip whitespace, and remove html tags
class Line:
    def  __init__(self, x):
        no_html = html_tag.sub("", x)
        onset = non_ws.search(no_html)
        self.onset = onset.span()[1] if onset else 0
        self.clean = ws.sub(" ", no_html).strip()
        self.tag = pre_tag(self.clean)

def tag_speaker(current, prev):
    if (current.tag == "caps" and
        speaker_pattern.search(current.clean) and
        current.onset >= prev.onset):
        return "speaker"
    else:
        return current.tag

def post_tag(current, prev, paragraph, dif):
    if prev.tag in ["speaker", "par"]:
        return "uc"
    elif prev.tag in ["scene", "cue"]:
        return "dir"
    elif dif == 0 or not paragraph or current.tag == "empty":
        return prev.tag
    elif dif > 0:
        return "dir"

    # scrape remaining speakers and dialogues
    if re.search(speaker_pattern, current.clean):
        return "speaker"

    return "unc"

def tag_scene(x, first=False):
    num = re.findall(leading_num, x)
    num = num[0] if num else ""
    title = ids.sub("", x)
    out = f'<scene id="{num}" title="{title}">'
    if first:
        return '</pre>\n' + out
    else:
        return '</scene>\n' + out

def tag_u(x):
    if "(" in x:
        return speaker_cap.sub(r'<u speaker="\1">\n<par> \2 <par>', x)
    else:
        return f'<u speaker="{x}">'

def add_xml(current, prev, isfirst):
    x = current.clean
    if current.tag != prev.tag:
        if current.tag == "scene":
            x = tag_scene(x, isfirst)
        elif current.tag == "speaker":
            x = tag_u(x)
        else:
            x = f"<{current.tag}>\n" + x

        if prev.tag == "uc" and not current.tag == "par":
            x =  "</uc>\n</u>\n" + x
        elif current.tag != "pre" and not prev.tag in ["speaker", "scene"]:
            x =  f"</{prev.tag}>\n" + x

    return x

def parse_script(script, start = "<pre", stop = "</pre"):
    prev = Line("")
    skip = preamble = True
    paragraph = False

    with open(script, "r") as f:
        for x in f:
            if skip and not start in x: continue
            else: skip = False

            current = Line(x)
            dif = prev.onset - current.onset

            if current.onset == 0 and not stop in x:
                current = prev
                paragraph = True
                continue

            current.tag = tag_speaker(current, prev)

            if preamble and current.tag == "scene":
                preamble = False

            if preamble:
                False
                # current.tag = "pre" # breaks scripts with no discernible scene lines
            elif current.tag in ["unc", "caps"]:
                current.tag = post_tag(current, prev, paragraph, dif)

            if current.tag in ["unc", "caps"]:
                current.tag = post_tag(current, prev, paragraph, dif)
                # should probably rewrite this to proper recursive function

            tagged = add_xml(current, prev, preamble)

            if stop in x:
                tagged = f"</{prev.tag}>\n</scene>\n"

            print(tagged)

            paragraph = False
            prev = current
            if stop in x:
                break

parse_script(argv[1])

