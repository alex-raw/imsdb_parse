#!/usr/bin/env python
import re
import sys
import logging
import readline # changes behavior of input()
from html import unescape
from textwrap import dedent
from itertools import pairwise
import xml.etree.ElementTree as et

# pre compile regex for readability and performance in loop
WS      = re.compile(r'\s+')
NON_WS  = re.compile(r'\S')
PAR     = re.compile(r'^[\(\{].+[\)\}]$')
EMPTY   = re.compile(r'^\W+$')
NUM     = re.compile(r'^\D?\d{1,3}\D{0,2}(\s\d*)?\s*$')
OMIT    = re.compile(r'\b(OMIT.*|DELETED)\b')

# catch: 1st WOMAN, 2nd FLOOR, ... McCAMERON, NAME (lower case par), CROW's
SLUG          = re.compile(r"^([^a-z]*(Mc|\d(st|nd|rd|th)|'s)?)?[^a-z]+(\(.*?\))?$")
INT_EXT       = re.compile(r'\b(INT|EXT)(ERIOR)?\b|\b(I\/E|E\/I)\b')
PAR_PATTERN   = re.compile(r'^\([^\)]+$|^[^\(]+\)$')
HEADINGS      = r'(FADE|CUT|THE END|POV|SCREEN|CREDITS?|TITLES|INTERCUT)'
MISC_HEADINGS = re.compile(fr'(?<!^I):|^{HEADINGS}\b|\b{HEADINGS}$')

# Catching page headers/footers
DATES        = r'\d+?[\./]\d+?[\./]\d+'
MORE         = r'[\(\-]\W*\bM[\sORE]{2,}?\b\W*[\)\-]'
CONT         = r'\bCO\W?N\W?[TY](\W?D|INU\W?(ED|ING|ES))?\s*\b'
IDS          = r'\D?\d+\D?\d*\.?'
NUMBERED     = re.compile(fr'^{IDS}|{IDS}$')
PAGE_HEADERS = re.compile(r'\b(rev(\.|isions?)?|draft|screenplay|shooting|progress|scene deleted|pdf)\b', re.I)
CONTINUED    = re.compile(CONT)
CONT_MORE    = re.compile(fr'^({IDS})?[\W\d]*({CONT}|{MORE})[\W\d]*({IDS})?$', re.I)
DATE_HEADERS = re.compile(fr'{DATES}\s{IDS}$')
PAGE         = re.compile(r'\b(PAGE|pg)\b[\s\.]?\d')
PAIRED_NUM   = re.compile(fr'^({IDS}).{{3,}}?\1$')
DATE         = re.compile(DATES)
IDS          = re.compile(IDS)

CLUTTER  = ['remove', 'date', 'cont']
PRE_TAGS = CLUTTER + ['unc', 'slug']


class Line:
    def  __init__(self, raw, ind=0):
        self.raw    = raw
        self.ind    = ind
        self.break_after = False
        self.clean  = WS.sub(' ', raw).strip()
        self.slug   = SLUG.search(self.clean)
        self.tag    = 'slug' if self.slug else 'unc'
        indent      = NON_WS.search(raw)
        self.indent = indent.span()[1] if indent else 0

    def __str__(self):
        return f'{self.ind}\t{self.tag}\t\t{self.raw}'

    def pre_tag(self):
        patterns = (('remove', EMPTY), ('remove', NUM), ('remove', OMIT),
                    ('hdg', INT_EXT),
                    ('date', DATE),
                    ('cont', CONTINUED),
                    ('par', PAR),
                    ('slug', SLUG)
                   )

        for tag, pattern in patterns:
            if re.search(pattern, self.clean):
                self.tag = tag
                break

        if self.tag not in CLUTTER and self.slug and PAIRED_NUM.search(self.clean):
            self.tag = 'hdg'

        if self.tag in ['hdg', 'par', 'trans']:
            self.indent = 1

        return self

    # discard if empty or if not potentially part of dialogue
    def is_clutter(self, prv) -> bool:
        line = self.clean
        return not self.indent or (
            self.tag in ['remove', 'date']
            ) and (
            not prv.tag in ['char', 'par', 'dlg'] or
            not self.indent == prv.indent
        ) or bool(
            PAGE.search(line) or
            DATE_HEADERS.search(line) or
            CONT_MORE.search(line) or
            PAGE_HEADERS.search(line) and (
                NUMBERED.search(line) or DATE.search(line))
        )

    def detect_tag(self, prv, nxt):
        tag     = self.tag
        prv_dif = self.indent - prv.indent
        nxt_dif = self.indent - nxt.indent
        start   = prv.break_after
        end     = self.break_after
        ispar   = PAR.search(self.clean)

        if tag in PRE_TAGS and self.slug:
            # reserve some unambiguous slugs as trans to prevent them from being overridden
            if MISC_HEADINGS.search(self.clean):
                tag = 'trans'
            elif nxt.tag == 'par' or nxt_dif and not ispar and (
                prv_dif or start and not end):
                tag = 'char'

        # remove date and cont tags when likely part of block to prevent deletion
        if tag in ['date', 'cont'] and (not start or not self.slug):
            if ispar:
                tag = 'par'
            elif abs(prv_dif) < 5:
                if prv.tag == 'hdg':
                    tag = 'act'
                else:
                    tag = prv.tag

        # infer from previous tags
        if tag in PRE_TAGS:
            if prv.tag == 'char':
                tag = 'dlg'
            elif prv.tag in ['hdg', 'trans', 'slug']:
                tag = 'act'
            elif prv.tag in ['dlg', 'act']:
                if not self.slug and prv_dif:
                    tag = 'act'

        # catch some pars with missing open or close pars
        if tag in PRE_TAGS and PAR_PATTERN.search(self.clean):
            tag = 'par'

        if tag == 'par' and not start and prv.tag not in ['dlg', 'char', 'slug']:
            tag = prv.tag

        # tolerate slight difference in indentation
        if tag in PRE_TAGS + ['act'] and abs(prv_dif) <= 1 and (
            prv.tag == 'act' or prv.tag == 'dlg' and not start):
            tag = prv.tag

        # reset trans to general slug
        if tag in ['trans', 'act'] and self.slug:
            tag = 'slug'

        if tag not in ['dlg', 'par'] and prv.tag == 'char':
            prv.tag = 'unc'

        # carry over tags in dialogue blocks
        if nxt.tag in PRE_TAGS:
            if tag == 'par':
                if prv.tag == 'char':
                    nxt.tag = 'dlg'
                elif abs(nxt.indent - prv.indent) <= 1:
                    nxt.tag = prv.tag
            if tag == 'act' and prv.tag == 'dlg' and nxt.indent == prv.indent and (
                not start and not end):
                nxt.tag = 'dlg'

        self.tag = tag


class Screenplay:
    def __init__(self, data, name):
        self.name = name
        self.raw = data
        self.lines = []
        self.unc = self.rm = 0

    def __len__(self):
        return len(self.lines)

    def parse_lines(self):
        self.lines = [Line(x, i).pre_tag() for i, x in enumerate(self.raw.splitlines())]
        return self

    def pre_format(self):
        data = re.sub(r'<!--.*?-->|<.*?>|\(.?\)', '', self.raw, flags=re.S)

        # streamline brackets and latex-style quotes, remove some sporadic characters
        # fix mixed spacing,
        data = data.translate(data.maketrans('{}`', "()'", '\r*_|~\\')) \
            .expandtabs().replace('&nbsp;', ' ') \
            .replace('&emdash;', '---').replace('&EMDASH;', '---') \
            .replace('&igrave;', "'").replace('&iacute;', "'").replace('&icirc;', "'")
            # Optional: issue in X-men only; consider removal

        # translate remaining html strings
        data = unescape(data)

        # remove stray opening brackets
        data = re.sub(r'\)\w\(', '', data)
        data = re.sub(r'[\(](\s*?\n[^\)]*?\n)', r'\1', data)

        # join lines with pars; conservative limits in case of unpaired
        for _ in range(5):
            data = re.sub(r'(\([^\)]*?)\n\s*([^\(\)]*\))', r'\1 \2', data, flags=re.M)

        self.raw = data
        return self


def _annotate(prv, cur, nxt, ln, force):
    prompt = dedent(f'''\
    ---------->\t\t{cur.raw}
    {str(nxt)}

    Leave blank to discard line;
    type 'start' to exit force mode; type 'exit' to continue in auto mode
    ({cur.ind}/{ln}) Enter tag: ''')

    print(prv, file=sys.stderr)
    if force or cur.tag == 'unc':
        print(prompt, file=sys.stderr)
        user_tag = input()
        return user_tag
    return cur.tag


def tag_screenplay(script, interactive=False, force=False):
    interactive = interactive or force
    script.lines = [Line('PAD')] + script.lines + [Line('PAD')]
    ln = len(script.lines)
    inds = list(range(ln))
    i = 0

    while i+3 <= len(inds):
        prv, cur, nxt = [script.lines[j] for j in inds[i:i+3]]

        if not force and nxt.is_clutter(cur):
            nxt.tag = 'RM1'
            script.rm += 1
            cur.break_after = not nxt.indent
            del inds[i+2]
            continue

        cur.detect_tag(prv, nxt)

        if not force and (cur.tag in CLUTTER or not cur.indent):
            cur.tag = 'RM2'
            script.rm += 1
            del inds[i+1]
            continue

        if interactive:
            user_tag = _annotate(prv, cur, nxt, ln, force)
            if not user_tag:
                cur.tag = 'RM_USER'
                script.rm += 1
                del inds[i+1]
                continue
            if user_tag == 'start':
                force = False
            elif user_tag == 'exit':
                interactive = False
            else:
                cur.tag = user_tag

        script.unc += prv.tag == 'unc'
        i += 1

    # Remove padding
    del script.lines[0]
    del script.lines[-1]


def _join_blocks(script):
    line = script.lines[0].clean
    for a, b in pairwise(script.lines):
        if a.tag == b.tag:
            line += '\n' + b.clean
        else:
            yield a.tag, line
            line = b.clean


def screenplay2xml(script, path):
    root = et.Element('')
    root = et.SubElement(root, "screenplay",path=path)

    current_level = root
    scene = None
    for tag, line in _join_blocks(script):
        if 'RM' in tag:
            continue

        if tag == 'hdg':
            n = IDS.findall(line)
            scene = et.SubElement(root, 'scene',
                id = n[0] if n else '',
                heading = IDS.sub('', line)
            )
            hdg = et.SubElement(scene, 'hdg')
            hdg.text = line
            current_level = scene

        elif tag == 'char':
            par = re.findall(r'\((.*)\)', line)
            turn = et.SubElement(scene or root, 'turn',
                char = re.sub(r'\s?\(.*\)', '', line),
                ext = par[0] if par else ''
            )
            char = et.SubElement(turn, 'char')
            char.text = line
            current_level = turn

        elif tag == 'slug':
            current_level = scene or root
            slug = et.SubElement(current_level, 'slug')
            slug.text = line

        else:
            content = et.SubElement(current_level, tag)
            content.text = line

    et.indent(root, '')
    return et.ElementTree(root)


def _import_screenplay(path):
    with open(path, 'rb') as f:
        x = f.read()
    try:
        return x.decode('utf-8')
    except UnicodeDecodeError:
        return x.decode('iso-8859-1')


def _main(path, interactive=False, force=False, xml=False):
    raw = _import_screenplay(path)

    try:
        raw = re.findall(r'(?<=<pre>).*(?=</pre>)', raw, re.S)[0]
    except IndexError:
        logging.warning('No <pre> tags found in %s', path)

    screenplay = Screenplay(raw, path).pre_format().parse_lines()

    if len(screenplay) < 50:
        logging.error('File appears to be empty or incomplete: %s', screenplay.name)
        sys.exit(1)

    tag_screenplay(screenplay, interactive, force)

    logging.debug('\n%s', '\n'.join([str(line) for line in screenplay.lines]))

    unc = screenplay.unc
    ln = len(screenplay.lines) - screenplay.rm
    logging.info('%.3f unclassified: %d/%d in %s', unc/ln, unc, ln, screenplay.name)

    if xml:
        tree = screenplay2xml(screenplay, path)
        out_path = path.replace('.html', '') + '.xml'
        tree.write(out_path, encoding ='utf-8')
        logging.info('created %s', out_path)


if __name__ == '__main__':
    import argparse
    from signal import signal, SIGPIPE, SIG_DFL
    signal(SIGPIPE, SIG_DFL)

    p = argparse.ArgumentParser()
    p.add_argument('path', help='path to html file')
    p.add_argument('-a', '--annotate', action='store_true',
                   help='interactively annotate unclassifiable lines')
    p.add_argument('-f', '--force', action='store_true',
                   help='force interactive annotation')
    p.add_argument('-d', '--debug', action='store_const', const='DEBUG',
                   help='print tagged lines to stderr')
    p.add_argument('-q', '--quiet', action='store_true',
                   help='do print any logging information')
    p.add_argument('-x', '--xml', action='store_true',
                   help='create an xml representation of the parsed file')
    args = p.parse_args()

    if not args.quiet:
        logging.basicConfig(format = '%(levelname)s: %(message)s',
                            level = args.debug or 'INFO')

    _main(args.path, args.annotate, args.force, args.xml)
