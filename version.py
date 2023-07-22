#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2022-2023 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

__version__ = '0.3.7'
__author__ = 'Mike McKerns'
__contact__ = 'mmckerns@uqfoundation.org'


def get_license_text(filepath):
    "open the LICENSE file and read the contents"
    try:
        LICENSE = open(filepath).read()
    except:
        LICENSE = ''
    return LICENSE


def get_readme_as_rst(filepath):
    "open the README file and read the markdown as rst"
    try:
        fh = open(filepath)
        name, null = fh.readline().rstrip(), fh.readline()
        tag, null = fh.readline(), fh.readline()
        tag = "%s: %s" % (name, tag)
        split = '-'*(len(tag)-1)+'\n'
        README = ''.join((null,split,tag,split,'\n'))
        skip = False
        for line in fh:
            if line.startswith('['):
                continue
            elif skip and line.startswith('    http'):
                README += '\n' + line
            elif line.startswith('* with'): #XXX: don't indent
                README += line
            elif line.startswith('* '):
                README += line.replace('* ','    - ',1)
            elif line.startswith('-'):
                README += line.replace('-','=') + '\n'
            elif line.startswith('!['): # image
                alt,img = line.split('](',1)
                if img.startswith('docs'): # relative path
                    img = img.split('docs/source/',1)[-1] # make is in docs
                README += '.. image:: ' + img.replace(')','')
                README += '   :alt: ' + alt.replace('![','') + '\n'
            #elif ')[http' in line: # alt text link (`text <http://url>`_)
            else:
                README += line
                skip = line.endswith(':\n')
        fh.close()
    except:
        README = ''
    return README


def write_info_file(dirpath, modulename, **info):
    """write the given info to 'modulename/__info__.py'

    info expects:
        doc: the module's long_description
        version: the module's version string
        author: the module's author string
        license: the module's license contents
    """
    import os
    infofile = os.path.join(dirpath, '%s/__info__.py' % modulename)
    header = '''#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2023 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/%s/blob/master/LICENSE
''' % modulename #XXX: author and email are hardwired in the header
    doc = info.get('doc', None)
    version = info.get('version', None)
    author = info.get('author', None)
    license = info.get('license', None)
    with open(infofile, 'w') as fh:
        fh.write(header)
        if doc is not None: fh.write("'''%s'''\n\n" % doc)
        if version is not None: fh.write("__version__ = %r\n" % version)
        if author is not None: fh.write("__author__ = %r\n\n" % author)
        if license is not None: fh.write("__license__ = '''\n%s'''\n" % license)
    return
