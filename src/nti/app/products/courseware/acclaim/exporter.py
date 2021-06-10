#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.app.products.courseware.acclaim import ACCLAIM_BADGE_FILE_NAME

from nti.app.products.courseware.acclaim.interfaces import ICourseAcclaimBadgeContainer

from nti.contenttypes.courses.exporter import BaseSectionExporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCompletionSectionExporter

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields

from nti.ntiids.ntiids import hash_ntiid

OID = StandardExternalFields.OID
ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE
CREATED_TIME = StandardExternalFields.CREATED_TIME
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

INTERNAL_NTIID = StandardInternalFields.NTIID

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseCompletionSectionExporter)
class AcclaimBadgeExporter(BaseSectionExporter):

    def _update_badge_ext(self, ext_obj, backup, salt):
        if not backup:
            for name in (OID, CREATED_TIME, LAST_MODIFIED):
                ext_obj.pop(name, None)
        else:
            ext_obj.pop(OID, None)
        if not backup:
            for name in (NTIID, INTERNAL_NTIID):
                value = ext_obj.get(name)
                if value:
                    ext_obj[name] = hash_ntiid(value, salt)

    def _export_badges(self, course, filer, backup, salt):
        """
        Exports the required items given by the required container. We'll
        need to make sure we salt ntiid values if not a backup.
        """
        badges = ICourseAcclaimBadgeContainer(course)
        result = [to_external_object(x, decorate=False) for x in badges.values()]
        if not backup:
            for badge_ext in result:
                self._update_badge_ext(badge_ext, backup, salt)
        if result:
            source = self.dump(result)
            filer.default_bucket = bucket = self.course_bucket(course)
            filer.save(ACCLAIM_BADGE_FILE_NAME,
                       source,
                       overwrite=True,
                       bucket=bucket,
                       contentType="application/x-json")

        for sub_instance in get_course_subinstances(course):
            self._export_badges(sub_instance, filer, backup, salt)

    def export(self, context, filer, backup=True, salt=None):
        course = ICourseInstance(context)
        self._export_badges(course, filer, backup, salt)
