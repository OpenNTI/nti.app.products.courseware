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

from nti.app.products.courseware.acclaim import ACCLAIM_BADGE_FILE_NAME

from nti.app.products.courseware.acclaim.interfaces import ICourseAcclaimBadgeContainer

from nti.cabinet.filer import transfer_to_native_file

from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.courses.importer import BaseSectionImporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCompletionSectionImporter

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object


logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseCompletionSectionImporter)
class AcclaimBadgeImporter(BaseSectionImporter):
    """
    Store our policies and required info around completion for this course.
    """

    def process(self, context, filer, writeout=True):
        """
        We could ignore any badges that do not have the currently configured
        acclaim organization id. Instead, we'll import these anyways since
        most imports are probably within site. Also, this scenario could
        happen currently if a client changes acclaim organizations; the client
        should be able to handle that scenario.
        """
        course = ICourseInstance(context)
        path = self.course_bucket_path(course) + ACCLAIM_BADGE_FILE_NAME
        source = self.safe_get(filer, path)
        if source is not None:
            container = ICourseAcclaimBadgeContainer(course)
            ext_badges = self.load(source)
            for ext_badge in ext_badges:
                factory = find_factory_for(ext_badge)
                badge = factory()
                update_from_external_object(badge, ext_badge, notify=False)
                container.get_or_create_badge(badge)
            # save source
            if writeout and IFilesystemBucket.providedBy(course.root):
                path = self.course_bucket_path(course) + ACCLAIM_BADGE_FILE_NAME
                source = self.safe_get(filer, path)  # reload
                if source is not None:
                    self.makedirs(course.root.absolute_path)
                    new_path = os.path.join(course.root.absolute_path,
                                            ACCLAIM_BADGE_FILE_NAME)
                    transfer_to_native_file(source, new_path)

        for sub_instance in get_course_subinstances(course):
            self.process(sub_instance, filer, writeout=writeout)
