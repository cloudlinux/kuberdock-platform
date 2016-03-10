import gzip
import os
import re
import subprocess
import tempfile
import shutil

INDEX_PATH = 'kubedock/frontend/templates/index.html'
LOGIN_PATH = 'kubedock/frontend/templates/auth/login.html'
STATIC_PATH = 'kubedock/frontend/static'
ALMOND = 'lib/almond'
READY = 'prepared.js'
CONTENTS = []
FILES = []

def parse(login=False):
    css = re.compile(r"""<link rel="stylesheet(?:/less)?".*?filename=(?:"|')(?P<path>[^"']+)""")
    js = re.compile(r"""<script.*</script>""")
    main = re.compile(r"""data-main=.*?filename=(?:"|')(?P<path>[^"']+)""")
    inside = False
    last_css = 0
    last_js = 0
    css_indent = 0
    js_indent = 0
    path = None
    item = LOGIN_PATH if login else INDEX_PATH
    with open(item) as f:
        for line in f:
            m = css.search(line)
            if m:
                if not inside:
                    CONTENTS.append('{#\n')
                    inside = True
                FILES.append(m.group('path'))
                css_indent = line.find('<')
            else:
                if inside:
                    CONTENTS.append('#}\n')
                    inside = False
                    last_css = len(CONTENTS)
            if not inside:
                if js.search(line):
                    dm = main.search(line)
                    if dm:
                        path = dm.group('path')
                        js_indent = line.find('<')
                    CONTENTS.append('{#\n')
                    line += '#}\n'
                    last_js = len(CONTENTS)+1
            CONTENTS.append(line)
    return last_css, css_indent, last_js, js_indent, path


def insert_css(pos, indent):
    if not FILES:
        return
    lesses = [os.path.basename(i) for i in FILES if i.endswith('.less')]
    less = lesses[0].replace('.less', '', 1) if lesses else 'main'
    fmt = ("""\n{0}<link rel="stylesheet" href="{{{{ url_for('static', """
           """filename='css/{1}.min.css') }}}}">\n\n""")
    css = fmt.format(' ' * indent, less)
    CONTENTS.insert(pos, css)
    return less
    
def insert_js(pos, indent, path):
    fmt = ("""\n{0}<script src="{{{{ url_for('static', """
           """filename='{1}') }}}}" type="text/javascript"></script>\n\n""")
    CONTENTS.insert(pos, fmt.format(' ' * indent,
                                    path.replace(os.path.basename(path), READY)))


def make_build(path, patt=re.compile(r"""(?P<paths>paths:\s?\{[^}]+\})""")):
    require_path = os.path.join(STATIC_PATH, path)
    if not os.path.exists(require_path):
        return
    with open(require_path) as f:
        data = f.read()
    m = patt.search(data, re.S)
    if not m:
        return
    fmt = ("""({{\nbaseUrl: "{0}",\n{1},\nname: "{2}",\ninclude: "{3}",\n"""
           """out: "{4}",\nwrapShim: true,\nfindNestedDependencies: true\n}});\n""")
    out = os.path.join(STATIC_PATH, os.path.dirname(path), READY)
    data = fmt.format(os.path.join(STATIC_PATH, 'js'),
               m.group('paths'),
               ALMOND,
               re.sub(r"""^([^/]+)/(.*?)\.\1""", r'\2', path),
               out)
    with open('build.js', 'w') as f:
        f.write(data)
    return out


def make_static_css(name):
    ready = os.path.join(STATIC_PATH, 'css')
    path = [i for i in FILES if i.endswith('.less')][0]
    tgt = os.path.join(ready, name+'.less.css')
    try:
        subprocess.check_call(['lessc', '--clean-css', os.path.join(STATIC_PATH, path), tgt])
    except subprocess.CalledProcessError:
        return
    css_files = [os.path.join(STATIC_PATH, i) for i in FILES if not i.endswith('.less')]
    css_files.append(tgt)
    out = os.path.join(ready, name+'.min.css')
    with open(out, 'w') as outfile:
        for css in css_files:
            with open(css) as infile:
                outfile.write(infile.read())
    with open(out, 'rb') as infile, gzip.open(out+'.gz', 'wb') as outfile:
        shutil.copyfileobj(infile, outfile)


def make_static_js(path):
    try:
        subprocess.check_call(['node', 'r.js', '-o', 'build.js'])
    except subprocess.CalledProcessError:
        return
    with open(path, 'rb') as infile, gzip.open(path+'.gz', 'wb') as outfile:
        shutil.copyfileobj(infile, outfile)


def save(login=False):
    item = LOGIN_PATH if login else INDEX_PATH
    fh, path = tempfile.mkstemp(dir=os.path.dirname(item))
    with os.fdopen(fh, 'w') as f:
        for i in CONTENTS:
            f.write(i)
    os.rename(path, item)
    if os.path.exists(path):
        os.unlink(path)


if __name__ == '__main__':
    last_css, css_indent, last_js, js_indent, path = parse()
    out = make_build(path)
    insert_js(last_js, js_indent, path)
    less = insert_css(last_css, css_indent)
    make_static_css(less)
    make_static_js(out)
    save()
    
    #TODO: Rewrite the whole logic and remove the following addition
    CONTENTS = []
    FILES = []
    last_css, css_indent, last_js, js_indent, path = parse(login=True)
    insert_css(last_css, css_indent)
    save(login=True)