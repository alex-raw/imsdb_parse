#!/usr/bin/env python
import re
import sys
from html import unescape
from collections import namedtuple

Screenplay = namedtuple('Screenplay', ('path', 'data'))

def _import_screenplay(path):
    with open(path, 'rb') as f:
        x = f.read()
    try:
        x = x.decode('utf-8')
    except UnicodeDecodeError:
        x = x.decode('iso-8859-1')
    return Screenplay(path, x.replace('\r', ''))


def _grab_content(x):
    content = re.findall(r'(?<=<pre>).*(?=</pre>)', x.data, re.S)
    if not content:
        data = x.data
        sys.stderr.write('Info: no <pre> tags found in %s\n' % x.path)
    else:
        data = content[0]
    if data.count('\n') < 50:
        sys.stderr.write('File appears to be empty: %s\n' % data.path)
        sys.exit()
    return data


def _join_unpaired(x, o, e, n): # TODO:
    for _ in range(n):
        x = re.sub(r'^(\s*{o}[^{e}{o}]*)\n\s*'.format(o=o, e=e), r'\1 ', x, flags = re.M)
    return x


def pre_format(data):
    # remove html tags, comments, and some clutter
    data = re.sub(r'<!--.*?-->|<.*?>|\(.?\)', '', data, flags = re.S)

    # streamline brackets and latex-style quotes, remove some sporadic characters
    # fix mixed spacing,
    data = data.translate(data.maketrans('{[]}`', "(())'", '*_|~\\')) \
        .replace('&nbsp;', ' ').expandtabs()

    # Optional: issue in X-men only; consider removal
    data = data.replace('&igrave;', "'").replace('&iacute;', "'").replace('&icirc;', "'")

    # translate html strings, issue in some otherwise also janked up files; consider removal
    data = unescape(data).replace('&emdash;', '---').replace('&EMDASH;', '---')

    # join lines with quotes and pars, preserve indentation
    # conservative limits in case of unpaired
    data = _join_unpaired(data, '"', '"', 5)
    data = _join_unpaired(data, r'\(', r'\)', 3)

    # buffer lines since loop will be 2 behind
    return (data + '\n<BUFFER>\n<BUFFER>').splitlines()


# pre compile regex for readability and performance in loop
ws       = re.compile(r'\s+')
non_ws   = re.compile(r'\S')
par      = re.compile(r'^\(.+\)$')
enquoted = re.compile(r'^".*"$')
empty    = re.compile(r'^\W+$')
num      = re.compile(r'^\s*\D?\d{1,3}\D{0,2}(\s\d*)?\s*$')
omit     = re.compile(r'\bOMIT.*\b')

# catch: 1st WOMAN, 2nd FLOOR, ... McCAMERON, NAME (lower case par), CROW's
slug     = re.compile(r"^([^a-z]*(Mc|\d(st|nd|rd|th)|'s)?)?[^a-z]+(\(.*?\))?$")
int_ext  = re.compile(r'\b(INT|EXT)(ERIOR)?\b')
misc_headings = '(FADE|CUT|THE END|POV|SCREEN|CREDITS?|TITLES|INTERCUT)'
misc_headings = re.compile(r'(?<!^I):|^{x}|{x}$'.format(x=misc_headings))

# Catching page headers/footers
dates_pattern = r'\d+?[\./-]\d+?[\./-]\d+'
numbering     = r'[A-Za-z]?\d+[A-Za-z]?\.?'
date_headers  = re.compile(r'%s\s%s$' % (dates_pattern, numbering))
page_headers  = re.compile(r'\b((rev\.?)|draft|screenplay|shooting|progress)\b', re.I)
date          = re.compile(dates_pattern)

# 'CONTINUED' and 'MORE' in all sorts of spellings.
more        = r'[\(\-]\W*\bM[\sORE]{2,}?\b\W*[\)\-]'
continued_r = r'\bCO\W?N\W?[TY](\W?D|INU\W?(ED|ING|ES))?\s*\b'
cont_more_r = r'^({n})?[\W\d]*({}|{})[\W\d]*({n})?$'.format(continued_r, more, n=numbering)

numbering   = re.compile(numbering)
cont_more   = re.compile(cont_more_r, re.I)
continued   = re.compile(continued_r, re.I)

preliminary = ['unc', 'cont', 'omit', 'num', 'date', 'slug', 'empty']


class Line:
    def  __init__(self, raw: str):
        self.raw         = raw
        self.clean       = ws.sub(' ', raw).strip()
        self.slug        = slug.search(self.clean)
        self.enquoted    = enquoted.search(self.clean)
        self.par         = par.search(self.clean)
        self.break_after = False
        self.tag         = 'slug' if self.slug else 'unc'
        indent = non_ws.search(raw)
        self.indent = indent.span()[1] if indent else 0

    def debug(self, raw=False) -> str:
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
        return not self.indent or (
            not prv.tag in ['dlg', 'char', 'par'] or
            not self.indent == prv.indent
            ) and (
            self.tag in ['date', 'empty', 'num'] or
            omit.search(self.clean) or
            cont_more.search(self.clean)
        ) or (
            date_headers.search(self.clean) or
            page_headers.search(self.clean) and date.search(self.clean)
        )

    def detect_tag(self, prv, nxt, last_dlg_indent):
        # remove date and cont tags when likely part of block to prevent deletion
        if self.tag in ['date', 'cont'] and (not prv.break_after or not self.slug):
            if self.par:
                self.tag = 'par'
            elif prv.indent == self.indent:
                self.tag = prv.tag

        # reserve some unambiguous slugs as trans to prevent them from being overridden
        if self.tag in preliminary and self.slug:
            if misc_headings.search(self.clean):
                self.tag = 'trans'
            elif not self.enquoted and nxt.enquoted or (
                nxt.tag == 'par' or
                self.indent > prv.indent and self.indent > nxt.indent):
                self.tag = 'char'

        # infer from previous tags
        if self.tag in preliminary:
            if prv.tag == 'char':
                self.tag = 'dlg'
            elif prv.tag in ['scene', 'slug', 'trans']:
                self.tag = 'act'
            elif prv.tag == 'dlg':
                if (prv.enquoted or
                    not self.slug and self.indent < prv.indent):
                    self.tag = 'act'

        # propagate tags with same formatting
        if self.tag in preliminary:
            # if abs(self.indent - prv.indent) <= 1:
            if abs(self.indent - prv.indent) <= 0:
                if prv.tag == 'act' or not prv.break_after and prv.tag == 'dlg':
                    self.tag = prv.tag

        # carry over tag past pars
        if nxt.tag in preliminary and self.tag == 'par':
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

        # if self.tag in preliminary and self.indent == last_dlg_indent and self.indent > 10:
        #     self.tag = 'dlg'


def _annotate_tag(prv, cur, nxt, i, ln):
    pre_prompt = '{i} {tag}  \t{prv}\n'
    prompt = '\
    ------->\t{cur}\n\
    \t\t{fol}\n\n\n({i}/{ln}) Leave blank to discard line, type "sys.exit" to finish in auto mode \nEnter tag: '

    sys.stderr.write(pre_prompt.format(i=i, tag=prv.tag, prv=prv.raw))
    if cur.tag == 'unc':
        sys.stderr.write(prompt.format(i=i, ln=ln, cur=cur.raw, fol=nxt.raw))
        out = input()

    return out if out else ''


def tag_screenplay(data, name, interactive=False, debug=True):
    prv = cur = nxt = Line('')
    lines, tags = [], []
    n, ln = 0, len(data)
    last_dlg_indent = 0

    for i, x in enumerate(data):
        nxt = Line(x)
        nxt.pre_tag()

        if nxt.discard(cur):
            if debug and nxt.indent:
                sys.stderr.write('%d removed\t%s\n' % (ln, nxt.raw))
            cur.break_after = not nxt.indent
            ln -= 1
            continue

        cur.detect_tag(prv, nxt, last_dlg_indent)

        # reset indentation level for one-line tags, (fix right aligned slugs and clutter)
        if nxt.tag in ['scene', 'par', 'trans']:
            nxt.indent = 1

        # clean up remaining clutter after making sure, it's not relevant
        if cur.tag in ['cont', 'omit', 'num', 'date', 'empty']:
            if debug:
                sys.stderr.write('%d removed2\t%s\n' % (ln, cur.raw))
            nxt.break_after = cur.break_after
            cur = nxt
            ln -= 1
            continue

        if cur.tag == 'dlg':
            last_dlg_indent = cur.indent

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

    sys.stderr.write('{perc:.2f} unclassified: {n}/{ln} in {name}.\n\n'
                     .format(perc=n/ln, n=n, ln=ln, name=name))
    return lines, tags


def main(path, interactive=False, debug=True):
    script = _import_screenplay(path)
    screenplay = pre_format(_grab_content(script))
    tag_screenplay(screenplay, script.path, interactive, debug)


# # TODO:
# def add_xml(path):
#     lines, tags = tag_screenplay(path)
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

if __name__ == '__main__':
    import argparse
    from signal import signal, SIGPIPE, SIG_DFL
    signal(SIGPIPE, SIG_DFL)

    parser = argparse.ArgumentParser()
    parser.add_argument('path', help='path to html file')
    parser.add_argument('-a', '--annotate', action='store_true',
                        help='interactively annotate unclassifiable lines')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='disable debugging information printed to stderr')
    args = parser.parse_args()
    main(args.path, args.annotate, not args.quiet)
