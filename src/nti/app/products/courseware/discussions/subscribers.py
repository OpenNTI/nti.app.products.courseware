#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os

from zope import component
from zope import interface

from zope.lifecycleevent import IObjectAddedEvent
from zope.lifecycleevent import IObjectModifiedEvent

from nti.app.products.courseware.discussions import create_topics
from nti.app.products.courseware.discussions import auto_create_forums
from nti.app.products.courseware.discussions import update_course_forums

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.app.products.courseware.utils import transfer_resources_from_filer

from nti.cabinet.filer import DirectoryFiler

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseRoleUpdatedEvent
from nti.contenttypes.courses.interfaces import ICourseRolesSynchronized
from nti.contenttypes.courses.interfaces import ICatalogEntrySynchronized
from nti.contenttypes.courses.interfaces import ICourseVendorInfoSynchronized
from nti.contenttypes.courses.interfaces import ICourseContentLibraryProvider

from nti.coremetadata.interfaces import IUser

from nti.dataserver.contenttypes.forums.topic import Topic
from nti.dataserver.contenttypes.forums.topic import HeadlineTopic
from nti.dataserver.contenttypes.forums.topic import CommunityHeadlineTopic

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseDiscussion, IObjectAddedEvent)
def _discussions_added(record, unused_event):
    course = ICourseInstance(record, None)
    if course is not None:
        # Now update our hrefs/icons, if necessary.
        target_filer = get_course_filer(course)
        if os.path.exists(course.root.absolute_path):
            source_filer = DirectoryFiler(course.root.absolute_path)
            transfer_resources_from_filer(ICourseDiscussion,
                                          record,
                                          source_filer,
                                          target_filer)
    # Now create topics
    if auto_create_forums(record):
        create_topics(record)


@component.adapter(ICourseDiscussion, IObjectModifiedEvent)
def _discussions_modified(record, unused_event):
    if auto_create_forums(record):
        create_topics(record)


def _update_course_forums(course):
    if course is not None and auto_create_forums(course):
        update_course_forums(course)


@component.adapter(ICourseCatalogEntry, ICatalogEntrySynchronized)
def _catalog_entry_synchronized(entry, unused_event):
    course = ICourseInstance(entry, None)
    _update_course_forums(course)


@component.adapter(ICourseInstance, ICourseRolesSynchronized)
def _course_roles_synchronized(course, unused_event):
    _update_course_forums(course)


@component.adapter(ICourseInstance, ICourseVendorInfoSynchronized)
def _course_vendor_info_synchronized(course, unused_event):
    _update_course_forums(course)


@component.adapter(ICourseRoleUpdatedEvent)
def _course_role_updated(event):
    _update_course_forums(event.course)


@component.adapter(IUser, ICourseInstance)
@interface.implementer(ICourseContentLibraryProvider)
class _CourseContentLibraryProvider(object):
    """
    Return the mimetypes of objects of course content that could be
    added to this course by this user.
    """

    def __init__(self, user, course):
        self.user = user
        self.course = course

    def get_item_mime_types(self):
        """
        Returns the collection of mimetypes that may be available (either
        they exist or can exist) in this course.
        """
        return (Topic.mime_type,
                HeadlineTopic.mime_type,
                CommunityHeadlineTopic.mime_type)
