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
from nti.app.contenttypes.completion.interfaces import ICompletionContextCohort
from nti.app.contenttypes.completion.interfaces import ICompletedItemsContext

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.completion.interfaces import ICompletableItem
from nti.contenttypes.completion.interfaces import ICompletionContext

from nti.dataserver import authorization

from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ACE_DENY_ALL
from nti.dataserver.authorization_acl import ace_allowing

from nti.dataserver.interfaces import IPrincipal
from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ILengthEnumerableEntityContainer


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

    def __init__(self, course, subcontext):
        self.course = course
        self.subcontext = subcontext
    
    @property
    def __acl__(self):
        # Admins and instructors have read and list
        aces = [ace_allowing(authorization.ROLE_ADMIN, authorization.ACT_READ, type(self)),
                ace_allowing(authorization.ROLE_ADMIN, authorization.ACT_LIST, type(self))]

        for i in self.course.instructors:
            aces.append(ace_allowing(i, authorization.ACT_READ, type(self)))

        # If our context adapts to a user only that user can read and list.
        # Otherwise anyone enrolled can read
        user = IUser(self.subcontext, None)
        if user is not None:
            aces.append(ace_allowing(user, authorization.ACT_READ, type(self)))
            aces.append(ace_allowing(user, authorization.ACT_LIST, type(self)))
        else:
            sharing_scopes = self.course.SharingScopes
            sharing_scopes.initScopes()
            public_scope = sharing_scopes[ES_PUBLIC]
            aces.append(ace_allowing(IPrincipal(public_scope),
                                     authorization.ACT_READ,
                                     type(self)))

        # Stop propogration up the tree
        aces.append(ACE_DENY_ALL)  
            
        return acl_from_aces(aces)

@interface.implementer(ICompletionContextCohort)
def course_cohort(course, scope=ES_PUBLIC):
    sharing_scopes = course.SharingScopes
    sharing_scopes.initScopes()
    return ILengthEnumerableEntityContainer(sharing_scopes[scope])
