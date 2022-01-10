#!/usr/bin/env python
import re
import sys
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE, SIG_DFL)

# join lines with quotes and pars, preserve indentation
def _join_unpaired(x, o, e):
    return re.sub(r'^(\s*%s[^%s]*$)\n\s*' % (o, e), r'\1 ', x, flags = re.M)

def pre_format(script):
    with open(script, 'rb') as f:
        x = f.read()
    try:
        x = x.decode('utf-8').replace('\r', '')
    except UnicodeDecodeError:
        x = x.decode('iso-8859-1').replace('\r', '')

    # grab, what's in pre tags, if none are found, warn
    content = re.findall(r'(?<=<pre>).*(?=</pre>)', x, re.S)
    if not content:
        sys.stderr.write('Info: no <pre> tags found in %s\n' % script)
    else:
        x = content[0]

    # remove html tags, comments, and other known clutter
    x = re.sub(r'<!--.*?-->|<.*?>|\(.?\)', '', x, flags = re.S)

    # streamline brackets and latex-style quotes, remove some sporadic characters
    # fix mixed spacing
    x = x.translate(x.maketrans('{[]}`', "(())'", '*_|~\\')) \
        .replace('&nbsp;', ' ').expandtabs()

    # conservative limits in case of unpaired
    for _ in range(5):
        x = _join_unpaired(x, '"', '"')
    for _ in range(2):
        x = _join_unpaired(x, r'\(', r'\)')

    if len(x) < 50:
        sys.stderr.write('File appears to be empty: {}\n'.format(script))
        sys.exit()
    else:
        # buffer lines since loop will be 2 behind
        return (x + '\n<BUFFER>\n<BUFFER>').splitlines()


# pre compile regex for readability and performance in loop
ws       = re.compile(r'\s+')
non_ws   = re.compile(r'\S')
par      = re.compile(r'^\(.+\)$')
enquoted = re.compile(r'^".*"$')
empty    = re.compile(r'^\W+$')
num      = re.compile(r'^\s*\D?\d{1,3}\D{0,2}(\s\d*)?\s*$')
omit     = re.compile(r'\bOMIT.*\b')

# tried to catch: 1st WOMAN, 2nd FLOOR, ... McCAMERON, NAME (lower case par)
slug     = re.compile(r"^([^a-z]*(Mc|\d(st|nd|rd|th)|'s)?)?[^a-z]+(\(.*?\))?$")
int_ext  = re.compile(r'\b(INT|EXT)(ERIOR)?\b')
misc_headings = re.compile(r'(?<!^I):|^{x}|{x}$'.format(x='(FADE|CUT|THE END|POV|SCREEN|CREDITS?|TITLES|INTERCUT)'))

# 'CONTINUED' and 'MORE' in all sorts of spellings.
more        = r'\(\W*\bM[\sORE]{2,}?\b\W*\)'
continued_r = r'\bCO\W?N\W?[TY](\W?D|INU\W?(ED|ING|ES))?\s*\b'
cont_more_r = r'^[\W\d]*(%s|%s)[\W\d]*$' % (continued_r, more)

cont_more   = re.compile(cont_more_r, re.I)
continued   = re.compile(continued_r, re.I)

# Catching page headers/footers
dates_pattern = r'\d+?[\./-]\d+?[\./-]\d+'
numbering = r'[A-Za-z]?\d+[A-Za-z]?\.?' # TODO: unused
date_headers = re.compile(r'%s\s%s$' % (dates_pattern, numbering)) # TODO: unused
page_headers = re.compile(r'\b((rev\.?)|draft|script|shooting|progress)\b', re.I)

date = re.compile(dates_pattern)


untagged = ['unc', 'cont', 'omit', 'num', 'date', 'slug', 'empty']

class Line:
    def  __init__(self, raw):
        self.raw         = raw
        self.clean       = ws.sub(' ', raw).strip()
        self.slug        = slug.search(self.clean)
        self.enquoted    = enquoted.search(self.clean)
        self.par         = par.search(self.clean)
        self.break_after = False
        self.tag         = 'slug' if self.slug else 'unc'
        indent = non_ws.search(raw)
        self.indent = indent.span()[1] if indent else 0

    def debug(self, raw=False):
        x = self.tag + '\t%s' % self.raw if raw else self.clean
        return x + ('\n' if self.break_after else '')

    def pre_tag(self):
        patterns = (('scene', int_ext),
                    ('empty', empty),
                    ('num', num),
                    ('date', date),
                    ('omit', omit),
                    ('cont', continued),
                    ('par', par)
                   )

        for tag, pattern in patterns:
            if pattern.search(self.clean):
                self.tag = tag
                break

    # discard if empty or if not potentially part of dialogue
    def discard(self, prv):
        return not self.indent or not (
            prv.tag in ['dlg', 'char'] or
            # prv.break_after or
            prv.tag == 'par' or
            self.indent == prv.indent
            ) and (
            self.tag == 'date' or
            self.tag == 'empty' or
            num.search(self.clean) or
            omit.search(self.clean) or
            cont_more.search(self.clean)
        ) or (
            date_headers.search(self.clean) or
            page_headers.search(self.clean) and date.search(self.clean)
        )

    def detect_tag(self, prv, nxt):
        if self.tag in untagged and self.slug and misc_headings.search(self.clean):
            self.tag = 'trans'
            # slug whose tag that cannot be overridden

        if self.tag in untagged and self.slug and not self.enquoted:
            if (nxt.enquoted or
                nxt.tag == 'par' or
                self.indent > prv.indent and self.indent > nxt.indent):
                self.tag = 'char'

        if self.tag in ['date', 'cont'] and (not prv.break_after or not self.slug):
            if self.par:
                self.tag = 'par'
            if prv.indent == self.indent:
                self.tag = prv.tag

        # infer from previous tags
        if self.tag in untagged:
            if prv.tag == 'char':
                self.tag = 'dlg'
            elif prv.tag in ['scene', 'slug', 'trans']:
                self.tag = 'act'
            elif prv.tag == 'dlg':
                if (prv.enquoted or
                    not self.slug and self.indent < prv.indent):
                    self.tag = 'act'

        # propagate tags with same formatting
        if self.tag in untagged:
            if self.indent == prv.indent:
                if prv.tag == 'act' or not prv.break_after and prv.tag == 'dlg':
                    self.tag = prv.tag

        # carry over tag past pars
        if nxt.tag in untagged and self.tag == 'par':
            if prv.tag == 'char':
                nxt.tag = 'dlg'
            elif nxt.indent == prv.indent:
                nxt.tag = prv.tag

        # reset some impossible combinations
        if prv.tag == 'char' and self.tag not in ['dlg', 'par']:
            prv.tag = 'unc'
        if self.tag == 'par' and prv.tag == 'act' and not prv.break_after:
            self.tag = 'act'

        if self.tag == 'act' and self.slug or self.tag == 'trans':
            self.tag = 'slug'

def _annotate_tag(prv, cur, nxt, i, ln):
    # TODO: list and number choices, make option for all dlg
    pre_prompt = '{i} {tag}  \t{prv}\n'
    prompt = '\
    ------->\t{cur}\n\
    \t\t{fol}\n\n\n({i}/{ln}) Leave blank to discard line, type "sys.exit" to finish in auto mode \nEnter tag: '

    sys.stderr.write(pre_prompt.format(i=i, tag=prv.tag, prv=prv.raw))
    if cur.tag == 'unc':
        sys.stderr.write(prompt.format(i=i, ln=ln, cur=cur.raw, fol=nxt.raw))
        return input()


def tag_script(infile, interactive=False, debug=True):
    script = pre_format(infile)
    prv = cur = nxt = Line('')
    ln = len(script)
    lines, tags = [], []
    n = 0

    for i, x in enumerate(script):
        nxt = Line(x)
        nxt.pre_tag()

        # reset indentation level for one-line tags, (fix right aligned slugs and clutter)
        if nxt.tag in ['scene', 'par']:
            nxt.indent = 1

        if nxt.discard(cur):
            if debug and nxt.indent:
                sys.stderr.write('%d removed\t%s\n' % (ln, nxt.raw))
            cur.break_after = not nxt.indent
            ln -= 1
            continue

        cur.detect_tag(prv, nxt)

        # clean up remaining clutter after making sure, it's not relevant
        if cur.tag in ['cont', 'omit', 'num', 'date', 'empty']:
            if debug:
                sys.stderr.write('%d removed2\t%s\n' % (ln, cur.raw))
            cur = nxt
            ln -= 1
            continue

        if interactive:
            user_tag = _annotate_tag(prv, cur, nxt, i, ln)
            if not user_tag:
                cur = nxt
                continue
            if user_tag == 'exit':
                interactive = False
            else:
                cur.tag = user_tag

        if debug:
            print(prv.debug(raw=True))

        lines.append(cur.clean)
        tags.append(cur.tag)
        n += prv.tag == 'unc'
        prv, cur = cur, nxt

    sys.stderr.write('{perc:.2f} unclassified: {n}/{ln} in {file}.\n\n'
                     .format(perc=n/ln, n=n, ln=ln, file=infile))
    return lines, tags


# # TODO:
# def add_xml(path):
#     lines, tags = tag_script(path)
#     for line, tag in zip(lines, tags):
#         pass

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
