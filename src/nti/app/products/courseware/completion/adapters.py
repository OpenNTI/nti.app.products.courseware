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

from pyramid.threadlocal import get_current_request

from nti.app.authentication import get_remote_user

from nti.app.contenttypes.completion.interfaces import ICompletionContextACLProvider
from nti.app.contenttypes.completion.interfaces import ICompletedItemsContext

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.completion.interfaces import ICompletableItem
from nti.contenttypes.completion.interfaces import ICompletionContext

from nti.dataserver import authorization

from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ACE_DENY_ALL
from nti.dataserver.authorization_acl import ace_allowing

@interface.implementer(ICompletionContext)
def _course_from_completable_item(item):
    """
    Find a :class:`ICourseInstance` from the given :class:`ICompletableItem`.
    """
    course = None
    # We would always prefer to get this off of calling context
    request = get_current_request()
    if request is not None:
        course = ICourseInstance(request, None)
    if course is None:
        # Otherwise, item/user might be a best guess
        user = get_remote_user(request)
        if user is not None:
            course = component.queryMultiAdapter((item, user),
                                                 ICourseInstance)
    if course is None:
        # Or we blindly guess on and item that may be shared across
        # multiple courses
        course = ICourseInstance(item, None)
    return course


@interface.implementer(ICompletionContextACLProvider)
class CourseCompletedItemsACLProvider(object):

    def __init__(self, course, completeditems):
        self.course = course
        self.completeditemsctx = completeditems
    
    @property
    def __acl__(self):
        aces = [ace_allowing(self.completeditemsctx.user, authorization.ACT_READ, type(self)),
                ace_allowing(authorization.ROLE_ADMIN, authorization.ACT_READ, type(self))]

        for i in self.course.instructors:
            aces.append(ace_allowing(i, authorization.ACT_READ, type(self)))
        aces.append(ACE_DENY_ALL)
        return acl_from_aces(aces)
