#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from nti.app.products.courseware.webinars.container import course_to_webinar_container

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset
from nti.app.products.courseware.webinars.interfaces import ICourseWebinarContainer

from nti.app.products.webinar.client_models import Webinar

from nti.app.products.webinar.interfaces import IWebinarAuthorizedIntegration

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseContentLibraryProvider

from nti.contenttypes.presentation.interfaces import IPresentationAssetCreatedEvent

from nti.coremetadata.interfaces import IUser

from nti.externalization.interfaces import IObjectModifiedFromExternalEvent

logger = __import__('logging').getLogger(__name__)


@component.adapter(IWebinarAsset, IPresentationAssetCreatedEvent)
def _on_webinar_asset_created(asset, unused_event=None):
    course = ICourseInstance(asset)
    container = ICourseWebinarContainer(course)
    original_webinar = asset.webinar
    # pylint: disable=too-many-function-args
    normalized_webinar = container.get_or_create_webinar(original_webinar)
    asset.webinar = normalized_webinar
    # Ghost it?
    # if normalized_webinar != original_webinar:
    #     original_webinar._p_changed = None


@component.adapter(IWebinarAsset, IObjectModifiedFromExternalEvent)
def _on_webinar_asset_modified(asset, unused_event=None):
    _on_webinar_asset_created(asset, unused_event)


@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _on_course_removed(course, unused_event=None):
    container = course_to_webinar_container(course, False)
    if container:
        container.clear()


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
        integration = component.queryUtility(IWebinarAuthorizedIntegration)
        result = ()
        if integration is not None:
            result = (Webinar.mime_type,)
        return result
