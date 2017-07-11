#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware.utils.exporter import save_resources_to_filer

from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.discussions.parser import path_to_discussions

from nti.contenttypes.courses.exporter import BaseSectionExporter

from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_MAP

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSectionExporter

from nti.contenttypes.courses.utils import get_course_subinstances
from nti.contenttypes.courses.utils import get_enrollment_in_hierarchy
from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.dataserver.users.users import User

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

from nti.namedfile.file import safe_filename

from nti.traversal.traversal import find_interface

OID = StandardExternalFields.OID
CLASS = StandardExternalFields.CLASS
NTIID = StandardExternalFields.NTIID
MIMETYPE = StandardExternalFields.MIMETYPE


@interface.implementer(ICourseSectionExporter)
class CourseDiscussionsExporter(BaseSectionExporter):

    def _process_resources(self, discussion, ext_obj, target_filer):
        save_resources_to_filer(ICourseDiscussion,  # provided interface
                                discussion,
                                target_filer,
                                ext_obj)

    def _ext_obj(self, discussion):
        ext_obj = to_external_object(discussion, decorate=False)
        ext_obj.pop(NTIID, None)
        ext_obj.pop(OID, None)
        return ext_obj

    def export(self, context, filer, backup=True, salt=None):
        course = ICourseInstance(context)
        bucket = path_to_discussions(course)
        discussions = ICourseDiscussions(course)
        for name, discussion in list(discussions.items()):  # snapshot
            ext_obj = to_external_object(discussion, decorate=False)
            self._process_resources(discussion, ext_obj, filer)
            source = self.dump(ext_obj)
            filer.save(name, source, contentType="application/json",
                       bucket=bucket, overwrite=True)
        # process subinstances
        for sub_instance in get_course_subinstances(course):
            self.export(sub_instance, filer, backup, salt)


def export_user_topic_as_discussion(topic):
    intids = component.queryUtility(IIntIds)
    course = find_interface(topic, ICourseInstance, strict=False)
    creator = getattr(topic.creator, 'username', topic.creator) or ''
    result = {
        'tags': topic.tags,
        CLASS: "Discussion",
        MIMETYPE: "application/vnd.nextthought.courses.discussion",
    }
    if creator:
        result['creator'] = creator
    # title and content
    headline = topic.headline
    result['body'] = headline.body
    result['title'] = headline.title
    # scope
    scopes = ["All"]
    if not is_course_instructor_or_editor(creator):
        user = User.get_user(creator)
        if user is not None:
            record = get_enrollment_in_hierarchy(course, user)
            if record is not None:  # user dropped
                term = ENROLLMENT_SCOPE_MAP.get(record.Scope)
                scopes = [record.Scope] + list(getattr(term, 'implies', ()))
    result["scopes"] = scopes
    path = path_to_discussions(course)
    if intids is not None:
        doc_id = intids.queryId(topic)
        doc_id = str(doc_id) if doc_id is not None else None
    else:
        doc_id = headline.title
    # give a proper id
    doc_id = safe_filename(doc_id or headline.title)
    result['id'] = "%s://%s/%s" % (NTI_COURSE_BUNDLE, path, doc_id)
    return result
