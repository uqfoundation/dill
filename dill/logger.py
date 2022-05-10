#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
r"""
Logging utilities for dill.

Python's logging functionality can be conceptually divided into five steps:
  0. Check logging level -> abort if call level is greater than logger level
  1. Gather information -> construct a LogRecord from passed arguments and context
  2. Filter (optional) -> discard message if the record matches a filter
  3. Format -> format message with args, then format output string with message plus record
  4. Handle -> write the formatted string to output as defined in the handler


Basic calling sequence
======================

dill.logging.logger.log ->    # or logger.info, etc.
  Logger.log ->               \
    Logger._log ->             }- accept 'extra' parameter for custom record entries
      Logger.makeRecord ->    /
        LogRecord.__init__
      Logger.handle ->
        Logger.callHandlers ->
          Handler.handle ->
            Filterer.filter ->
              Filter.filter
            StreamHandler.emit ->
              Handler.format ->
                Formatter.format ->
                  LogRecord.getMessage      # does: record.message = msg % args
                  Formatter.formatMessage ->
                    PercentStyle.format     # does: self._fmt % record.__dict__

NOTE: All methods from the second line on are from logging.__init__.py


Logger customizations
=====================

Step 1 - Information
--------------------
We use a LoggerAdapter subclass to wrap the module's logger, as the logging API
doesn't allow setting it directly with a custom Logger subclass.  The added
'log_trace()' method receives a pickle instance as the first argument and
creates extra values to be added in the LogRecord from it, then calls 'log()'.

Step 3 - Formatting
-------------------
We use a Formatter subclass to add prefix and suffix strings to the log message
in trace mode (an also provide empty defaults for normal logs).  The user may
substitute the formatter to customize the extra information display.
"""

__all__ = ['INFO_DETAIL', 'adapter', 'logger', 'trace']

import locale, logging, math

INFO_DETAIL = (logging.INFO + logging.DEBUG) // 2

TRANS_TABLE = {ord(k): ord(v) for k, v in zip(u"│├┬└", "||+`")}


class TraceAdapter(logging.LoggerAdapter):
    """tracks object graph depth and calculates pickled object size"""
    def __init__(self, logger):
        self.logger = logger
    def process(self, msg, kwargs):
        # A no-op override, as we don't have self.extra
        return msg, kwargs
    def log_trace(self, pickler, msg=None, *args, **kwargs):
        """log_trace(self, pickler, msg=None, *args, reset=False, **kwargs)"""
        reset = kwargs.pop('reset', False)
        if msg is None:
            # Initialization and clean-up.
            if reset:
                pickler._trace_depth = 0
                pickler._size_stack = None
            elif self.isEnabledFor(INFO_DETAIL):
                pickler._trace_depth = 1
                pickler._size_stack = []
            return

        elif getattr(pickler, '_trace_depth', None):
            extra = kwargs.get('extra', {})
            pushed = msg.startswith('#')
            size = None
            try:
                size = pickler._file.tell()
                size += pickler.framer.current_frame.tell()
            except AttributeError:
                pass
            if size:
                if not pushed:
                    pickler._size_stack.append(size)
                else:
                    size -= pickler._size_stack.pop()
                    extra['size'] = size
            if pushed: pickler._trace_depth -= 1
            extra['depth'] = pickler._trace_depth
            kwargs['extra'] = extra
            self.log(INFO_DETAIL, msg, *args, **kwargs)
            if not pushed: pickler._trace_depth += 1

        else:
            self.info(msg, *args, **kwargs)

class TraceFormatter(logging.Formatter):
    """generates message prefix and suffix from record"""
    def __init__(self, *args, **kwargs):
        super(TraceFormatter, self).__init__(*args, **kwargs)
        self.is_utf8 = locale.getpreferredencoding() == 'UTF-8'
    def format(self, record):
        fields = {'prefix': "", 'suffix': ""}
        if getattr(record, 'depth', 0) > 0:
            if record.msg.startswith("#"):
                prefix = (record.depth-1)*u"│" + u"└ "
            elif record.depth == 1:
                prefix = u"┬ "
            else:
                prefix = (record.depth-2)*u"│" + u"├┬ "
            if not self.is_utf8:
                prefix = prefix[:-1].translate(TRANS_TABLE) + "- "
            fields['prefix'] = prefix
        if hasattr(record, 'size'):
            # Show object size in human-redable form.
            power = int(math.log(record.size, 2)) // 10
            size = record.size >> power*10
            fields['suffix'] = " [%d %sB]" % (size, "KMGTP"[power] + "i" if power else "")
        record.__dict__.update(fields)
        return super(TraceFormatter, self).format(record)


logger = logging.getLogger('dill')
adapter = TraceAdapter(logger)

handler = logging.StreamHandler()
logger.addHandler(handler)

formatter = TraceFormatter("%(prefix)s%(message)s%(suffix)s")
handler.setFormatter(formatter)


def trace(boolean, detail=False):
    """print a trace through the stack when pickling; useful for debugging"""
    if boolean:
        logger.setLevel(INFO_DETAIL if detail else logging.INFO)
    else:
        logger.setLevel(logging.WARNING)
