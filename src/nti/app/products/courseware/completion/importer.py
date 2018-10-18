#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os

from zope import interface

from nti.app.products.courseware.completion import COMPLETION_POLICY_FILE_NAME
from nti.app.products.courseware.completion import DEFAULT_REQUIRED_ITEMS_FILE_NAME
from nti.app.products.courseware.completion import COMPLETABLE_ITEM_REQUIRED_FILE_NAME

from nti.cabinet.filer import transfer_to_native_file

from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.completion.interfaces import ICompletableItemContainer
from nti.contenttypes.completion.interfaces import ICompletableItemDefaultRequiredPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.contenttypes.courses.importer import BaseSectionImporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCompletionSectionImporter

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.internalization import update_from_external_object

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseCompletionSectionImporter)
class CourseCompletionImporter(BaseSectionImporter):
    """
    Store our policies and required info around completion for this course.
    """

    def process(self, context, filer, writeout=True):
        course = ICourseInstance(context)
        for key, iface in ((COMPLETABLE_ITEM_REQUIRED_FILE_NAME, ICompletableItemContainer),
                           (DEFAULT_REQUIRED_ITEMS_FILE_NAME, ICompletableItemDefaultRequiredPolicy),
                           (COMPLETION_POLICY_FILE_NAME, ICompletionContextCompletionPolicyContainer)):
            path = self.course_bucket_path(course) + key
            source = self.safe_get(filer, path)
            if source is not None:
                completion_impl = iface(course)
                ext_obj = self.load(source)
                update_from_external_object(completion_impl,
                                            ext_obj,
                                            notify=False)
                # save source
                if writeout and IFilesystemBucket.providedBy(course.root):
                    path = self.course_bucket_path(course) + key
                    source = self.safe_get(filer, path)  # reload
                    if source is not None:
                        self.makedirs(course.root.absolute_path)
                        new_path = os.path.join(course.root.absolute_path,
                                                key)
                        transfer_to_native_file(source, new_path)

        for sub_instance in get_course_subinstances(course):
            self.process(sub_instance, filer, writeout=writeout)
