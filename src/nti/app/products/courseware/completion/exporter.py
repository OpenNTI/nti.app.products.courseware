#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.app.products.courseware.completion import COMPLETION_POLICY_FILE_NAME
from nti.app.products.courseware.completion import DEFAULT_REQUIRED_ITEMS_FILE_NAME
from nti.app.products.courseware.completion import COMPLETABLE_ITEM_REQUIRED_FILE_NAME

from nti.contenttypes.completion.interfaces import ICompletableItemContainer
from nti.contenttypes.completion.interfaces import ICompletableItemDefaultRequiredPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.contenttypes.courses.exporter import BaseSectionExporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCompletionSectionExporter

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields
from nti.contenttypes.presentation.interfaces import IContentBackedPresentationAsset

from nti.ntiids.ntiids import find_object_with_ntiid

ITEMS = StandardExternalFields.ITEMS

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseCompletionSectionExporter)
class CourseCompletionExporter(BaseSectionExporter):

    def _get_new_ntiid(self, ntiid, salt):
        """
        Do not hash content backed presentation assets.
        """
        result = ntiid
        obj = find_object_with_ntiid(ntiid)
        if      obj is not None \
            and not IContentBackedPresentationAsset.providedBy(obj):
            result = self.hash_ntiid(ntiid, salt)
        return result

    def _export_policy(self, course, filer, backup, salt):
        """
        Exports the required items given by the policy container. We'll
        need to make sure we salt ntiid values if (a) not a backup and (b)
        the objects are not content-backed.
        """
        policy_container = ICompletionContextCompletionPolicyContainer(course)
        ext_policy = to_external_object(policy_container)
        if not backup:
            policy_map = ext_policy.get(ITEMS) or {}
            new_policy_map = {}
            for ntiid, policy_ext in policy_map.items():
                new_ntiid = self._get_new_ntiid(ntiid, salt)
                new_policy_map[new_ntiid] = policy_ext
            ext_policy[ITEMS] = new_policy_map
        if ext_policy:
            source = self.dump(ext_policy)
            filer.default_bucket = bucket = self.course_bucket(course)
            filer.save(COMPLETION_POLICY_FILE_NAME,
                       source,
                       overwrite=True,
                       bucket=bucket,
                       contentType="application/x-json")

    def _export_required_items(self, course, filer, backup, salt):
        """
        Exports the required items given by the required container. We'll
        need to make sure we salt ntiid values if (a) not a backup and (b) the
        objects are not content-backed.
        """
        required_container = ICompletableItemContainer(course)
        ext_container = to_external_object(required_container)
        if not backup:
            for required_type_key in ('required', 'optional'):
                required_keys = ext_container.get(required_type_key) or []
                ext_container[required_type_key] = [self._get_new_ntiid(x, salt)
                                                    for x in required_keys]
        if ext_container:
            source = self.dump(ext_container)
            filer.default_bucket = bucket = self.course_bucket(course)
            filer.save(COMPLETABLE_ITEM_REQUIRED_FILE_NAME,
                       source,
                       overwrite=True,
                       bucket=bucket,
                       contentType="application/x-json")

    def _export_default_required_items(self, course, filer):
        """
        Exports the default required (mimetypes) of this course completion context.
        """
        default_required_container = ICompletableItemDefaultRequiredPolicy(course)
        ext_policy = to_external_object(default_required_container)
        if ext_policy:
            source = self.dump(ext_policy)
            filer.default_bucket = bucket = self.course_bucket(course)
            filer.save(DEFAULT_REQUIRED_ITEMS_FILE_NAME,
                       source,
                       overwrite=True,
                       bucket=bucket,
                       contentType="application/x-json")

    def export(self, context, filer, backup=True, salt=None):
        course = ICourseInstance(context)
        self._export_policy(course, filer, backup, salt)
        self._export_required_items(course, filer, backup, salt)
        self._export_default_required_items(course, filer)
