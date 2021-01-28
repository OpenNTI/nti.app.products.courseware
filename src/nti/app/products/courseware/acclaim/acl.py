#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: acl.py 124926 2017-12-15 01:32:03Z josh.zuech $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.acclaim.interfaces import ICourseAcclaimBadge

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.common import get_course_editors

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.interfaces import IACLProvider

from nti.traversal.traversal import find_interface


logger = __import__('logging').getLogger(__name__)


@interface.implementer(IACLProvider)
@component.adapter(ICourseAcclaimBadge)
class CourseAcclaimBadgeACLProvider(object):

    def __init__(self, context):
        self.context = context

    @property
    def __parent__(self):
        return self.context.__parent__

    @Lazy
    def __acl__(self):
        course = find_interface(self.context, ICourseInstance)
        editors = get_course_editors(course)
        aces = []
        for editor in editors or ():
            ace = ace_allowing(editor, ALL_PERMISSIONS, type(self))
            aces.append(ace)
        return acl_from_aces(aces)
