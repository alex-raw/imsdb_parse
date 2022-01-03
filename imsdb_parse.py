#!/usr/bin/env python
import re, sys

# pre compile regex for readability and performance in loop
# Line cleanup
non_ws      = re.compile(r'\S')
ws          = re.compile(r'\s+')
no_lower    = re.compile(r"^([^a-z]*Mc|[^a-z]*\d(st|nd|rd|th))?[^a-z]+(\(.*?\))?$")
# tried to catch: 1st WOMAN, 2nd FLOOR, ... McCAMERON, NAME (lower case)
# pre_tag regex
int_ext     = re.compile(r'\b(INT|EXT)\b')
char_continued = re.compile("[a-z]+\s?(\(.*?\))?\s?\(CON\s?T(INUE|')D\)", re.IGNORECASE)
# TODO: use same logic as in no_lower
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
    x = re.findall(r'(?<=<pre>)(?s:.)*(?=</pre>)', x)[0]
    x = re.sub(r'<!--(?s:.)*?-->|<(?s:.)*?>|\(X\.?\)', '', x).splitlines()
    x.append('<BUFFER_LINE>')  # since loop will be one behind
    return x


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

    def disambiguate_caps(self, prev, following):
        if self.tag == 'unc' and self.no_lower:
            if paired_num.search(self.clean):
                self.tag = 'scene'
            elif cue.search(self.clean):
                self.tag = 'cue'
            elif (not self.enquoted
                  and self.onset > prev.onset
                  and self.onset > following.onset
                  ) or following.enquoted:
                self.tag = 'char'

    def detect_tag(self, prev, following):
        if self.tag != 'unc':
            return

        if prev.tag in ['char', 'par']:
            self.tag = 'dlg'
        elif prev.tag in ['scene', 'cue']:
            self.tag = 'dir'
        elif (prev.tag == 'dlg'
              and prev.onset > self.onset
              and not self.no_lower):
            self.tag = 'dir'

    def propagate_tags(self, prev, following):
        if self.tag == 'unc' and self.onset == prev.onset:
            self.tag = prev.tag
        elif end_quote.search(self.clean) and prev.tag == 'dlg':
            self.tag = prev.tag
        elif open_quote.search(prev.clean):
            self.tag = prev.tag
            if not end_quote.search(self.clean):
                following.tag = prev.tag
                # sub-optimal, but conservative since quotes might be missing
                # and would never find a match


def tag_script(script, annotate=False):
    script = pre_format(script)
    prev = current = Line('')
    ln = len(script)
    lines, tags = [], []
    counter = 0
    break_before = False # only debug eyecandy

    for i, x in enumerate(script):
        following = Line(x)
        following.break_before = break_before # only debug eyecandy
        if following.discard():
            break_before = True # only debug eyecandy
            continue

        current.disambiguate_caps(prev, following)
        current.detect_tag(prev, following)
        current.propagate_tags(prev, following)

        # "interactive mode" TODO: factor out or move past this function
        if annotate:
            sys.stderr.write(f'{i} {prev.tag}\t{prev.raw}\n')
            if current.tag == 'unc':
                sys.stderr.write(f'--->\t{current.raw}\n\t{following.raw}\n\n\n')
                sys.stderr.write(f'({i}/{ln}) Enter tag, leave blank to discard line, type "exit" to finish in auto mode \n: ')
                user_tag = input()
                if not user_tag:
                    current = following
                    continue
                elif user_tag == "exit":
                    annotate = False
                else:
                    current.tag = user_tag

        if current.tag == 'unc':
            counter += 1

        out = f'{current.tag}\t{current.raw}'
        if current.break_before: # only debug eyecandy
            print(f'\n{out}') # only debug eyecandy
        else:
            print(out)

        lines.append(current.clean)
        tags.append(current.tag)
        break_before = False # only debug eyecandy
        prev, current = current, following

    if counter:
        sys.stderr.write(f'Failed to classify {counter}/{ln} lines.\n')
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

# def add_xml(current, prev, isfirst):
#     x = current.clean
#     if current.tag != prev.tag:
#         if current.tag == "scene":
#             x = tag_scene(x, isfirst)
#         elif current.tag == "char":
#             x = tag_u(x)
#         else:
#             x = f"<{current.tag}>\n" + x

#         if prev.tag == "uc" and not current.tag == "par":
#             x =  "</uc>\n</u>\n" + x
#         elif current.tag != "pre" and not prev.tag in ["char", "scene"]:
#             x =  f"</{prev.tag}>\n" + x

#     return x

if __name__ == "__main__":
    if len(sys.argv) == 3:
        tag_script(sys.argv[2], sys.argv[1] == "-a")
    else:
        tag_script(sys.argv[1], False)

