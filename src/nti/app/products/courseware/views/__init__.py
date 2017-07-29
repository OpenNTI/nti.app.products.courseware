#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from urllib import unquote

from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.container.contained import Contained

from zope.traversing.interfaces import IPathAdapter

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from nti.app.externalization.error import raise_json_error

from nti.app.products.courseware import MessageFactory

from nti.app.products.courseware import ASSETS_FOLDER
from nti.app.products.courseware import IMAGES_FOLDER
from nti.app.products.courseware import DOCUMENTS_FOLDER

from nti.app.products.courseware import VIEW_CONTENTS
from nti.app.products.courseware import VIEW_RESOURCES
from nti.app.products.courseware import VIEW_COURSE_MAIL
from nti.app.products.courseware import VIEW_CATALOG_ENTRY
from nti.app.products.courseware import VIEW_COURSE_ACTIVITY
from nti.app.products.courseware import VIEW_CURRENT_COURSES
from nti.app.products.courseware import VIEW_ARCHIVED_COURSES
from nti.app.products.courseware import VIEW_COURSE_FAVORITES
from nti.app.products.courseware import VIEW_COURSE_RECURSIVE
from nti.app.products.courseware import VIEW_UPCOMING_COURSES
from nti.app.products.courseware import SEND_COURSE_INVITATIONS
from nti.app.products.courseware import VIEW_COURSE_DISCUSSIONS
from nti.app.products.courseware import VIEW_LESSONS_CONTAINERS
from nti.app.products.courseware import VIEW_USER_COURSE_ACCESS
from nti.app.products.courseware import ACCEPT_COURSE_INVITATION
from nti.app.products.courseware import ACCEPT_COURSE_INVITATIONS
from nti.app.products.courseware import VIEW_COURSE_ACCESS_TOKENS
from nti.app.products.courseware import CHECK_COURSE_INVITATIONS_CSV
from nti.app.products.courseware import VIEW_COURSE_CATALOG_FAMILIES
from nti.app.products.courseware import VIEW_COURSE_RECURSIVE_BUCKET
from nti.app.products.courseware import VIEW_COURSE_ENROLLMENT_ROSTER

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.ntiids.ntiids import find_object_with_ntiid


@interface.implementer(IPathAdapter)
class CourseAdminPathAdapter(Contained):

    __name__ = 'CourseAdmin'

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context

    def __getitem__(self, ntiid):
        if not ntiid:
            raise hexc.HTTPNotFound()
        ntiid = unquote(ntiid)
        result = ICourseInstance(find_object_with_ntiid(ntiid), None)
        if ICourseInstance.providedBy(result):
            return result
        raise KeyError(ntiid)

    @Lazy
    def __acl__(self):
        aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self)),
                ace_allowing(ROLE_CONTENT_ADMIN, ALL_PERMISSIONS, type(self))]
        return acl_from_aces(aces)


def raise_error(data, tb=None,
                factory=hexc.HTTPUnprocessableEntity,
                request=None):
    request = request or get_current_request()
    raise_json_error(request, factory, data, tb)
