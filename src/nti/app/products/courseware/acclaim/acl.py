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

from zope.security.management import getInteraction

from nti.app.products.courseware.acclaim.interfaces import ICourseAcclaimBadge
from nti.app.products.courseware.acclaim.interfaces import ICourseAcclaimBadgeContainer

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.common import get_course_editors

from nti.dataserver.authorization import ACT_READ

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import has_permission

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


@interface.implementer(IACLProvider)
@component.adapter(ICourseAcclaimBadgeContainer)
class CourseAcclaimBadgeContainerACLProvider(object):
    """
    An ACL provider the grants the anonymous principal read access to
    the badge container if the catalog supports anonymous access. We
    list badges that are awarded on the course information and
    therefore we need our view here to be accessible by the anonymous principal.
    """

    def __init__(self, context):
        self.context = context

    @property
    def __parent__(self):
        return self.context.__parent__

    @Lazy
    def __acl__(self):
        # If we have read access to the catalog entry, we should also
        # be able to see the badges we can award. The problem is our
        # parent is the ICourseInstance and having read access to the
        # ICatalogEntry does not imply we also have read access on our
        # parent, the ICourseInstance. That's probably an indication
        # that we've got the natural lineage boogered up somewhere.

        catalog = ICourseCatalogEntry(self.__parent__)
        
        # If this permission check is to slow we could cheat and
        # instead explicitly check the catalog is anonymous and grant
        # that principal explicit read access. That's less flexible
        # going forward and probably doesn't properly account for
        # things like unlisted courses.

        # For the principals tied to our current interaction, if they
        # have read access on the catalog entry, give them read
        # access on this container explicitly.
        aces = []
        for participation in getInteraction().participations:
            principal = participation.principal
            if has_permission(ACT_READ, catalog, principal.id):
                ace = ace_allowing(principal.id, ACT_READ, type(self))
                aces.append(ace)

        return acl_from_aces(aces)
        
