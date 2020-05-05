#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import shutil
import subprocess
import tempfile

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.contenttypes.completion.interfaces import IProgress

from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy

logger = __import__('logging').getLogger(__name__)

MAX_RETRIES = 3


def has_completed_course(user, course, success_only=False):
    """
    Answers if the user has completed the given course (and successfully if success_only is True). Will return False if
    the course is not completable (or is not successfully completed if success_only is True).
    """
    policy = ICompletionContextCompletionPolicy(course, None)
    result = False
    if policy is not None:
        progress = component.queryMultiAdapter((user, course), IProgress)
        result = policy.is_complete(progress)
        result = bool(result and result.Success) if success_only else bool(result)
    return result


class RetriesExceededError(Exception):
    """
    Raised when we've exceeded our max retry count
    """


class SVGConverter(object):

    @Lazy
    def _output_folder(self):
        return tempfile.mkdtemp(prefix="image_converter_tmp")

    def _output_filename(self, input_filename, ext=".png"):
        basename = os.path.basename(input_filename)
        name, _ = os.path.splitext(basename)
        return os.path.join(self._output_folder, "%s.%s" % (name, ext))

    def cleanup(self):
        if '_output_folder' in self.__dict__:
            shutil.rmtree(self._output_folder, ignore_errors=True)

    def convert(self,
                input_filename,
                width,
                height,
                density=900):
        """Convert the input file from SVG to PNG at the size expected by
        the template"""

        outfile_name = self._output_filename(input_filename)

        command = ["convert",
                   "-density", "%s" % density,
                   "-background", "none",
                   "-resize", "%fx%f" % (width, height),
                   input_filename,
                   "%s" % outfile_name]
        __traceback_info__ = command
        return_code = subprocess.call(command)

        # Check that the out put file is not 0 bytes, if it is try, try
        # again because something odd happened.
        retries = 0
        while return_code != 0 or os.stat(outfile_name).st_size == 0:
            logger.warning(
                '%s is empty!!!! Input was %s with size %s. Attempting to convert again.'
                % (outfile_name, input_filename, os.stat(input_filename).st_size))
            return_code = subprocess.call(command)

            retries += 1
            if retries > MAX_RETRIES:
                logger.error(
                    "Failed to convert '%s' to '%s'.  Max retries exceeded, "
                    "final return code = %s",
                    input_filename, outfile_name, return_code)
                raise RetriesExceededError(
                    "Unable to convert file: %s" % input_filename)

        return outfile_name
