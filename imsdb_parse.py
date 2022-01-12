#!/usr/bin/env python
import re
import sys
import readline
from html import unescape
from collections import namedtuple

Screenplay = namedtuple('Screenplay', ('path', 'data'))

def _import_screenplay(path) -> Screenplay:
    with open(path, 'rb') as f:
        x = f.read()
    try:
        x = x.decode('utf-8')
    except UnicodeDecodeError:
        x = x.decode('iso-8859-1')
    return Screenplay(path, x.replace('\r', ''))


def _grab_content(x) -> str:
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


def pre_format(data) -> list[str]:
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

    # remove stray opening brackets
    data = re.sub(r'\)\w\(', '', data)
    data = re.sub(r'[\(](\s*?\n[^\)]*?\n)', r'\1', data)

    # join lines with pars, preserve indentation; conservative limits in case of unpaired
    for _ in range(5):
        data = re.sub(r'(\([^\)]*?)\n\s*([^\(\)]*\))', r'\1 \2', data, flags = re.M)

    # buffer lines since loop will be 2 behind
    return (data + '\n<BUFFER>\n<BUFFER>').splitlines()


# pre compile regex for readability and performance in loop
ws       = re.compile(r'\s+')
non_ws   = re.compile(r'\S')
par      = re.compile(r'^\(.+\)$')
empty    = re.compile(r'^\W+$')
num      = re.compile(r'^\D?\d{1,3}\D{0,2}(\s\d*)?\s*$')
omit     = re.compile(r'\b(OMIT.*|DELETED)\b')

# catch: 1st WOMAN, 2nd FLOOR, ... McCAMERON, NAME (lower case par), CROW's
slug     = re.compile(r"^([^a-z]*(Mc|\d(st|nd|rd|th)|'s)?)?[^a-z]+(\(.*?\))?$")
int_ext  = re.compile(r'\b(INT|EXT)(ERIOR)?\b|\b(I\/E|E\/I)\b')
misc_headings = '(FADE|CUT|THE END|POV|SCREEN|CREDITS?|TITLES|INTERCUT)'
misc_headings = re.compile(r'(?<!^I):|^{x}\b|\b{x}$'.format(x=misc_headings))

# Catching page headers/footers
dates_pattern = r'\d+?[\./-]\d+?[\./-]\d+'
ids     = r'\D?\d+\D?\d*\.?'
date_headers  = re.compile(r'%s\s%s$' % (dates_pattern, ids))
page_headers  = re.compile(r'\b((rev\.?)|draft|screenplay|shooting|progress|scene deleted|pdf)\b', re.I)
page          = re.compile(r'\b(PAGE|pg)\b[\s\.]?\d')
date          = re.compile(dates_pattern)

# 'CONTINUED' and 'MORE' in all sorts of spellings.
more        = r'[\(\-]\W*\bM[\sORE]{2,}?\b\W*[\)\-]'
continued_r = r'\bCO\W?N\W?[TY](\W?D|INU\W?(ED|ING|ES))?\s*\b'
cont_more_r = r'^({n})?[\W\d]*({}|{})[\W\d]*({n})?$'.format(continued_r, more, n=ids)

numbered    = re.compile(r'^{n}|{n}$'.format(n=ids))
cont_more   = re.compile(cont_more_r, re.I)
continued   = re.compile(continued_r)

par_pattern = re.compile(r'^\([^\)]+$|^[^\(]+\)$')
paired_num = re.compile(r'^(%s).{3,}?\1$' % ids)

clutter = ['cont', 'omit', 'num', 'date', 'empty']
pre_tags = clutter + ['unc', 'slug']

class Line:
    def  __init__(self, raw):
        self.raw         = raw
        self.clean       = ws.sub(' ', raw).strip()
        self.slug        = slug.search(self.clean)
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
                    ('par', par),
                    ('slug', slug)
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
            self.tag in ['date', 'empty', 'num', 'omit'] or
            date_headers.search(self.clean) or
            cont_more.search(self.clean)
        ) or (
            page.search(self.clean) or
            page_headers.search(self.clean) and (
                date.search(self.clean) or numbered.search(self.clean)
        ))

    def detect_tag(self, prv, nxt):
        prv_dif = self.indent - prv.indent
        nxt_dif = self.indent - nxt.indent

        if self.slug and self.tag not in clutter and paired_num.search(self.clean):
            self.tag = 'scene'

        # TODO: inspect leading and trailing numbers

        # remove date and cont tags when likely part of block to prevent deletion
        if self.tag in ['date', 'cont'] and (not prv.break_after or not self.slug):
            if self.par:
                self.tag = 'par'
            elif abs(prv_dif) < 5:
                if prv.tag == 'scene':
                    self.tag = 'act'
                else:
                    self.tag = prv.tag

        if self.tag in pre_tags and self.slug:
            # reserve some unambiguous slugs as trans to prevent them from being overridden
            if misc_headings.search(self.clean):
                self.tag = 'trans'
            elif nxt.tag == 'par' or nxt_dif > 0 and (
                prv_dif > 0 or prv.break_after and not self.break_after):
                self.tag = 'char'

        # infer from previous tags
        if self.tag in pre_tags:
            if prv.tag == 'char':
                self.tag = 'dlg'
            elif prv.tag in ['scene', 'slug', 'trans']:
                self.tag = 'act'
            elif prv.tag == 'dlg':
                if not self.slug and prv_dif < 0:
                    self.tag = 'act'

        # catch some pars with missing open or close pars
        if self.tag in pre_tags and par_pattern.search(self.clean):
            self.tag = 'par'

        # propagate tags with same formatting, tolerate slight difference in indentation
        if self.tag in pre_tags + ['act']:
            if abs(prv_dif) <= 1:
                if prv.tag == 'act' or (not prv.break_after and prv.tag == 'dlg'):
                    self.tag = prv.tag

        # carry over tag past pars
        if nxt.tag in pre_tags and self.tag == 'par':
            if prv.tag == 'char':
                nxt.tag = 'dlg'
            elif abs(nxt.indent - prv.indent) <= 1:
                nxt.tag = prv.tag

        # reset some impossible combinations
        if self.tag == 'par' and prv.tag not in ['dlg', 'char', 'slug'] and not prv.break_after:
            self.tag = prv.tag
        elif self.tag not in ['dlg', 'par'] and prv.tag == 'char':
            prv.tag = 'unc'

        # reset trans to general slug
        if self.slug and self.tag == 'act' or self.tag == 'trans':
            self.tag = 'slug'


prompt_msg = """Leave blank to discard line;
type 'start' to exit force mode; type 'exit' to continue in auto mode
Enter tag: """

def tag_screenplay(screenplay,
                   interactive=False,
                   force=False,
                   debug=True) -> tuple[list[str], list[str]]:
    prv = cur = Line('')
    lines, tags = [], []
    n, ln = 0, len(screenplay.data)

    pre_prompt = '{i} {tag}  \t{prv}\n'
    prompt = """\
    ----------> {cur}
    \t\t{fol}\n\n({i}/{ln}) {msg}"""

    for i, x in enumerate(screenplay.data):
        nxt = Line(x)
        nxt.pre_tag()

        if nxt.discard(cur):
            if debug and nxt.indent:
                sys.stderr.write('%d REMOVED_1\t%s\n' % (ln, nxt.raw))
            cur.break_after = not nxt.indent
            ln -= 1
            continue

        cur.detect_tag(prv, nxt)

        # reset indentation level for one-line tags, (fix right aligned slugs and clutter)
        if nxt.tag in ['scene', 'par', 'trans']:
            nxt.indent = 1

        # clean up clutter after making sure, it's not valid part of block
        if cur.tag in clutter:
            if debug:
                sys.stderr.write('%d REMOVED_2\t%s\n' % (ln, cur.raw))
            cur = nxt
            ln -= 1
            continue

        if interactive or force:
            sys.stderr.write(pre_prompt.format(i=i, tag=prv.tag, prv=prv.raw,
                                               msg=prompt_msg))
            if force or cur.tag == 'unc':
                sys.stderr.write(prompt.format(i=i, ln=ln, cur=cur.raw, fol=nxt.raw,
                                           msg=prompt_msg))
                user_tag = input()
            if not user_tag:
                cur = nxt
                ln -=1
                continue
            if user_tag == 'start':
                force = False
                interactive = True
            elif user_tag == 'exit':
                interactive = False
            else:
                cur.tag = user_tag

        if debug:
            print(prv.debug(raw=True))

        lines.append(cur.clean)
        tags.append(cur.tag)
        n += prv.tag == 'unc'
        prv, cur = cur, nxt

    sys.stderr.write('{perc:.2f} unclassified: {n}/{ln} in {path}.\n\n'
                     .format(perc=n/ln, n=n, ln=ln, path=screenplay.path))
    return lines, tags

# ids_r = re.compile(ids)
# def tag_scene(x):
#     n = re.findall(ids_r, x)
#     n = n[0] if n else ''
#     title = ids_r.sub('', x)
#     out = f'<scene id="{n}" title="{title}">'
#     return out

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

        # if prv.tag == "uc" and not cur.tag == "par":
        #     x =  "</uc>\n</u>\n" + x
        # elif cur.tag != "pre" and not prv.tag in ["char", "scene"]:
        #     x =  f"</{prv.tag}>\n" + x

    # return x


def main(path, interactive=False, force=False, debug=True):
    script = _import_screenplay(path)
    data = pre_format(_grab_content(script))
    data = tag_screenplay(Screenplay(script.path, data), interactive, force, debug)
    # TODO: scenes could be two lines long (with par)
    # gather same tags first
    # for line, tag in zip(data[0], data[1]):
    #     if tag == 'scene':
    #         print(tag_scene(line))


if __name__ == '__main__':
    import argparse
    from signal import signal, SIGPIPE, SIG_DFL
    signal(SIGPIPE, SIG_DFL)

    parser = argparse.ArgumentParser()
    parser.add_argument('path', help='path to html file')
    parser.add_argument('-a', '--annotate', action='store_true',
                        help='interactively annotate unclassifiable lines')
    parser.add_argument('-f', '--force', action='store_true',
                        help='force manual annotation')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='disable debugging information printed to stderr')
    args = parser.parse_args()
    main(args.path, args.annotate, args.force, not args.quiet)
