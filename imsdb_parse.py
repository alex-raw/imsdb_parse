#!/usr/bin/env python
import re, sys

# pre compile regex for readability and performance in loop
# Line cleanup
non_ws      = re.compile(r'\S')
ws          = re.compile(r'\s+')
no_lower    = re.compile(r"^([^a-z]*Mc|[^a-z]*\d(st|nd|rd|th))?[^a-z]+(\(.*?\))?$")
# tried to catch: 1st WOMAN, 2nd FLOOR, ... McCAMERON, NAME (lower case par)
# pre_tag regex
int_ext     = re.compile(r'\b(INT|EXT)\b')
char_continued = re.compile("[a-z]+\s?(\(.*?\))?\s?\(CON\s?T(INUE|')D\)", re.IGNORECASE)
# discard
continued   = re.compile(r"con\s?t(inue|')d", re.IGNORECASE)
lone_num    = r'^(\d.?\.?)+\s?\1?$' # page numbers
empty       = r'^(\W+|.)?$' # non-word chars or one single char
other       = r'\b(REVISIONS?|DRAFTS?|ACT|OMITTED)\b'
skip        = re.compile('|'.join([lone_num, empty, other]))
# disambiguate caps
paired_num  = re.compile(r'^.*(\d+.*).+\1.*$')
cue         = re.compile(r':|^(FADE|CUT|END|POV)|(FADE|CUT|END|POV)$')
# pair wise patterns
par_pattern = re.compile(r'^.?\s?\(.*\)$|^\([^\)]+$|^[^\(]+\)$')
enquoted    = re.compile(r'^".*"$')
open_quote  = re.compile(r'^"[^"]+$')
end_quote   = re.compile(r'^[^"]+"$')

def pre_format(script):
    # remove html tags, comments, and other known clutter
    with open(script, 'r') as f:
        x = f.read()
    content = re.findall(r'(?<=<pre>).*(?=</pre>)', x, re.S)
    out = content[0] if content else x
    out = re.sub(r'<!--.*?-->|<.*?>|\(X\.?\)', '', out, flags = re.S)
    out = (out + '\n<BUFFER_LINE>').splitlines()  # buffer since loop will be one behind
    if len(out) < 50:
        sys.stderr.write("File appears to be empty: {}\n".format(script))
        exit()
    else:
        return out


class Line:
    def  __init__(self, x):
        self.raw = x
        self.clean = ws.sub(" ", x).strip()
        onset = non_ws.search(x)
        self.onset = onset.span()[1] if onset else 0
        self.no_lower = no_lower.search(self.clean)
        self.enquoted = enquoted.search(self.clean)
        self.tag = 'unc'

        self.break_before = False # only debug eyecandy

        if int_ext.search(self.clean):
            self.tag = 'scene'
        elif char_continued.search(self.clean):
            self.tag = 'char' # reserve early so other 'continued' lines can be discarded safely
        elif par_pattern.search(self.clean):
            self.tag = 'par'

    def discard(self):
        return self.tag in ['unc', 'par'] and (
            not self.onset
            or skip.search(self.clean)
            or continued.search(self.clean)
        )

    def disambiguate_caps(self, prv, nxt):
        if self.tag == 'unc' and self.no_lower:
            if paired_num.search(self.clean):
                self.tag = 'scene'
            elif cue.search(self.clean):
                self.tag = 'cue'
            elif (not self.enquoted
                  and self.onset > prv.onset
                  and self.onset > nxt.onset
                  ) or nxt.enquoted:
                self.tag = 'char'

    def detect_tag(self, prv, nxt):
        if self.tag != 'unc':
            return

        if prv.tag in ['char', 'par']:
            self.tag = 'dlg'
        elif prv.tag in ['scene', 'cue']:
            self.tag = 'act'
        elif (prv.tag == 'dlg'
              and prv.onset > self.onset
              and not self.no_lower):
            self.tag = 'act'

    def propagate_tags(self, prv, nxt):
        if self.tag == 'unc' and self.onset == prv.onset:
            self.tag = prv.tag
        elif end_quote.search(self.clean) and prv.tag == 'dlg':
            self.tag = prv.tag
        elif open_quote.search(prv.clean):
            self.tag = prv.tag
            if not end_quote.search(self.clean):
                nxt.tag = prv.tag
                # sub-optimal, but conservative since quotes might be missing
                # and would never find a match


def tag_script(infile, annotate=False):
    script = pre_format(infile)
    prv = cur = Line('')
    ln = len(script)
    lines, tags = [], []
    n = 0
    break_before = False # only debug eyecandy
    pre_prompt = '{i} {tag}  \t{prv}\n'
    prompt = '\
    ------->\t{cur}\n\
    \t\t{fol}\n\n\n\
    ({i}/{ln}) Enter tag, leave blank to discard line, type "exit" to finish in auto mode \n: '

    for i, x in enumerate(script):
        nxt = Line(x)
        nxt.break_before = break_before # only debug eyecandy
        if nxt.discard():
            break_before = True # only debug eyecandy
            continue

        cur.disambiguate_caps(prv, nxt)
        cur.detect_tag(prv, nxt)
        cur.propagate_tags(prv, nxt)

        # "interactive mode" TODO: factor out or move past this function
        if annotate:
            sys.stderr.write(pre_prompt.format(i=i, tag=prv.tag, prv=prv.raw))
            if cur.tag == 'unc':
                sys.stderr.write(prompt.format(i=i, ln=ln, cur=cur.raw, fol=nxt.raw))
                user_tag = input()
                if not user_tag:
                    cur = nxt
                    continue
                elif user_tag == "exit":
                    annotate = False
                else:
                    cur.tag = user_tag

        n += cur.tag == 'unc'

        out = '{tag}\t{raw}'.format(tag=cur.tag, raw=cur.raw)
        if cur.break_before: # only debug eyecandy
            print('\n' + out) # only debug eyecandy
        else:
            print(out)

        lines.append(cur.clean)
        tags.append(cur.tag)
        break_before = False # only debug eyecandy
        prv, cur = cur, nxt

    sys.stderr.write('unclassified lines: {n}/{ln} in {file}.\n'
                     .format(n=n, ln=ln, file=infile))
    return lines, tags


# TODO:
def add_xml(path):
    lines, tags = tag_script(path)
    for line, tag in zip(lines, tags):
        pass

# def tag_scene(x, first=False):
#     num = re.findall(leading_num, x)
#     num = num[0] if num else ""
#     title = ids.sub("", x)
#     out = f'<scene id="{num}" title="{title}">'
#     return out if first else '</scene>\n' + out

# def tag_u(x):
#     if "(" in x:
#         return char_cap.sub(r'<u char="\1">\n<par> \2 <par>', x)
#     else:
#         return f'<u char="{x}">'

# def add_xml(cur, prv, isfirst):
#     x = cur.clean
#     if cur.tag != prv.tag:
#         if cur.tag == "scene":
#             x = tag_scene(x, isfirst)
#         elif cur.tag == "char":
#             x = tag_u(x)
#         else:
#             x = f"<{cur.tag}>\n" + x

#         if prv.tag == "uc" and not cur.tag == "par":
#             x =  "</uc>\n</u>\n" + x
#         elif cur.tag != "pre" and not prv.tag in ["char", "scene"]:
#             x =  f"</{prv.tag}>\n" + x

#     return x

if __name__ == "__main__":
    if len(sys.argv) == 3:
        tag_script(sys.argv[2], sys.argv[1] == "-a")
    else:
        tag_script(sys.argv[1], False)


""" TODO:
- files without <pre>
- files with [speaker]: [dialogue] (subset of ^----?)
  - The Village: all dlg because no indentation
- files with semantic tags. simple search for <.*speaker|act.*>?
  - get-shorty: act, speaker, dia, spkdir (==par), slug (==scene or cue)
"""

