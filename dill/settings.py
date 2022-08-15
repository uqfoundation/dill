#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
global settings for Pickler
"""

__all__ = ['settings', 'read_settings', 'reset_settings']

from pickle import DEFAULT_PROTOCOL, HIGHEST_PROTOCOL

settings = {
   #'main' : None,
    'protocol' : DEFAULT_PROTOCOL,
    'byref' : False,
   #'strictio' : False,
    'fmode' : 0, #HANDLE_FMODE
    'recurse' : False,
    'ignore' : False,
}

### Config file reader (INI format) ###

DEFAULT_SETTINGS = {
    'dill': settings.copy(),
    'dill.session': None,  # set in dill.session
}
FMODES = dict(HANDLE_FMODE=0, CONTENTS_FMODE=1, FILE_FMODE=2)
STANDARD_PROTOCOLS = dict(DEFAULT_PROTOCOL=DEFAULT_PROTOCOL, HIGHEST_PROTOCOL=HIGHEST_PROTOCOL)

del DEFAULT_PROTOCOL, HIGHEST_PROTOCOL

def _split_option(option, strip_quotes=False):
    """split option text by commas or newlines"""
    import re
    if not option: return []  # empty value
    option = option.strip(",\n")  # strip leading/trailing commas and empty lines
    option = option.splitlines() if '\n' in option else re.split(r',\s+', option)
    return [x.strip("\"'") for x in option] if strip_quotes else option

def _read_filters(section, module_filters):
    from logging.config import _resolve
    from dill.session import EXCLUDE, INCLUDE
    for rule_type in (EXCLUDE, INCLUDE):
        rule = rule_type.name.lower()
        if not any(option.lower().startswith(rule) for option in section):
            # If no filters, let it fall back to parent module or default filters.
            delattr(module_filters, rule)
            continue
        for option in (rule, '%s.names' % rule, '%s.regexes' % rule):
            if option in section:
                for filter in _split_option(section[option], strip_quotes=True):
                    module_filters.add(filter, rule_type=rule_type)
        if '%s.types' % rule in section:
            for name in _split_option(section['%s.types' % rule]):
                if '.' in name:
                    filter = _resolve(name)
                    if not isinstance(filter, type):
                        raise TypeError("filter is not a type: %r" % filter)
                else:
                    filter = 'type:%s' % name
                module_filters.add(filter, rule_type=rule_type)
        if '%s.funcs' % rule in section:
            for code in section['%s.funcs' % rule].strip('\n').splitlines():
                if code.startswith('(') and code.endswith(')'):
                    code = code[1:-1]
                globals_ = {}
                if not code.startswith('lambda'):
                    name = code.partition('(')[0]
                    _resolve(name)  # import required modules
                    top_level = name.partition('.')[0]
                    globals_[top_level] = __import__(top_level)
                filter = eval(code, globals_)
                if not callable(filter):
                    raise TypeError("filter is not callable: %r" % filter)
                module_filters.add(filter, rule_type=rule_type)

def read_settings(filename) -> None:
    """Read dill settings from an INI file.

    Update the ``dill.settings`` dictionary with the contents of the INI file
    ``filename``.  Accepted file sections:

      - `dill`: general :py:mod:`dill` settings
      - `dill.module`: settings for :py:func:`dill.dump_module`
      - `filters`: default exclude/include filters for :py:func:`dill.dump_module`
      - `filters.<module_name>`: module-specific filters for
        :py:func:`dill.dump_module`, where `<module_name>` is the complete module
        path in the form `module[.submodule...]`

    Accepted option values for general settings:

      - boolean options (case insensitive): yes, no, on, off, true, false
      - `protocol`: DEFAULT_PROTOCOL, HIGHEST_PROTOCOL, 0, 1, 2, 3, ...
      - `fmode`: HANDLE_FMODE, 0, CONTENTS_FMODE, 1, FILE_FMODE, 2

    .. IMPORTANT: The demo config file below is used in test_settings.py
    .. Lexer 'pacmanconf' generates better highlighting than 'ini'.
    .. code-block:: pacmanconf

        [dill]
        # General settings
        ## Stored in dill.settings.
        protocol = HIGHEST_PROTOCOL
        byref = yes

        [dill.session]
        # Settings for dill.dump_module()
        ## Stored in dill.session.settings.
        refonfail = no

        [filters]
        # Default exclude/include filters for dill.dump_module()
        ## Stored in dill.settings['dump_module']['filters'].
        exclude.names = some_var, SomeClass
        exclude.regexes = '_.+'
        exclude.types = function, ModuleType, io.BytesIO
        exclude.funcs =
            lambda obj: type(obj.value) == int
            dill.session.size_filter('10 KB')
        include = _keep_this_var, '__.+__'

        [filters.some.module]
        # Filter rules specific to the module 'some.module'
        ## Reuse regex filters defined in the previous section.
        ## Option 'include' is unset, will fall back to default 'include' filters.
        exclude = ${filters:exclude.regexes}
        #include =

        [filters.another.module]
        # Filter rules specifit to the module 'another.module'
        ## Empty filter sets disable filtering for this module.
        exclude =
        include =

    Parameters:
        filename: a path-like object or a readable stream.

    Tip:
        The parser uses default syntax with extended interpolation enabled.
        For details about the accepted INI format, see :py:mod:`configparser`.
    """
    import configparser
    from dill import DEFAULT_PROTOCOL, HANDLE_FMODE
    from dill.session import ModuleFilters, settings as session_settings

    cp = configparser.ConfigParser(
            dict_type=dict,  # internal, in place of OrderedDict
            empty_lines_in_values=False,  # one value per line
            interpolation=configparser.ExtendedInterpolation(),
    )
    cp.read_dict(DEFAULT_SETTINGS)
    if hasattr(filename, 'readline'):
        cp.read_file(filename)
    else:
        cp.read(filename)

    # General settings.
    section = cp['dill']
    new_settings = {k: section.getboolean(k)
            for k, v in DEFAULT_SETTINGS['dill'].items() if type(v) == bool}
    fmode = section.get('fmode')
    protocol = section.get('protocol')
    new_settings['fmode'] = int(FMODES.get(fmode, fmode))
    new_settings['protocol'] = int(STANDARD_PROTOCOLS.get(protocol, protocol))

    # Session settings (for dump_module).
    section = cp['dill.session']
    new_session_settings = {k: section.getboolean(k) for k in DEFAULT_SETTINGS['dill.session']}
    filters = new_session_settings['filters'] = ModuleFilters(rules=())
    if 'filters' in cp:
        # Default filters.
        _read_filters(cp['filters'], filters)
    for module, section in cp.items():
        if not module.startswith('filters.'):
            continue
        module = module.partition('.')[-1]
        assert all(x.isidentifier() for x in module.split('.'))
        filters[module] = ()  # instantiate ModuleFilters and FilterSet's
        _read_filters(section, filters[module])

    # Update settings dictionary.
    settings.clear()
    settings.update(new_settings)
    session_settings.clear()
    session_settings.update(new_session_settings)

def reset_settings() -> None:
    "Reset all the dill settings to its default values."
    from dill.session import ModuleFilters, settings as session_settings
    settings.clear()
    settings.update(DEFAULT_SETTINGS['dill'])
    session_settings.clear()
    session_settings.update(DEFAULT_SETTINGS['dill.session'])
    session_settings['filters'] = ModuleFilters(rules=())
