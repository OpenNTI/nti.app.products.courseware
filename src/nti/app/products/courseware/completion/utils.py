#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import random
import shutil
import string
import subprocess
import tempfile

from PIL import Image

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


def _get_size(outfile_name):  # pragma: no cover
    return os.stat(outfile_name).st_size


def _call(command):  # pragma: no cover
    return subprocess.call(command)


class ImageUtils(object):

    default_img_format = "png"

    @Lazy
    def _output_folder(self):
        return tempfile.mkdtemp(prefix="image_converter_tmp")

    def _rand_string(self, length=10):
        return ''.join(random.choice(string.ascii_letters) for _ in range(length))

    def _output_filename(self, input_filename, ext=None):
        basename = os.path.basename(input_filename)
        name, input_ext = os.path.splitext(basename)
        ext = ext or input_ext
        return os.path.join(self._output_folder, "%s-%s%s"
                            % (name, self._rand_string(), ext))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cleanup()
        return False

    def cleanup(self):
        if '_output_folder' in self.__dict__:
            shutil.rmtree(self._output_folder, ignore_errors=True)

    def constrain_size(self, input_file, max_width, max_height):
        with Image.open(input_file) as image:
            image.thumbnail((max_width, max_height))
            outfile_name = self._output_filename(input_file)
            image.save(outfile_name)

        return outfile_name

    def convert(self,
                input_filename,
                width,
                height,
                img_format=None,
                density=900):
        """
        Convert the input file with the specified width and height,
        returning the new filename.
        """

        img_format = img_format or self.default_img_format
        outfile_name = self._output_filename(input_filename,
                                             ext=".%s" % (img_format,))

        command = ["convert",
                   "-density", "%s" % density,
                   "-background", "none",
                   "-resize", "%fx%f" % (width, height),
                   input_filename,
                   "%s:%s" % (img_format, outfile_name)]
        __traceback_info__ = command
        return_code = _call(command)

        # Check that the out put file is not 0 bytes, if it is try, try
        # again because something odd happened.
        retries = 0
        while return_code != 0 or _get_size(outfile_name) == 0:
            logger.warning(
                '%s is empty!!!! Input was %s with size %s. Attempting to convert again.'
                % (outfile_name, input_filename, _get_size(input_filename)))
            return_code = _call(command)

            retries += 1
            if retries >= MAX_RETRIES:
                logger.error(
                    "Failed to convert '%s' to '%s'.  Max retries exceeded, "
                    "final return code = %s",
                    input_filename, outfile_name, return_code)
                raise RetriesExceededError(
                    "Unable to convert file: %s" % input_filename)

        return outfile_name
