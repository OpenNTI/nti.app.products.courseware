#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from datetime import datetime

from zope import component
from zope import interface

from pyramid.threadlocal import get_current_request

from nti.app.products.courseware.utils import ZERO_DATETIME

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.interfaces import IContentUnit

from nti.contentsearch.interfaces import ISearchHitPredicate

from nti.contentsearch.predicates import DefaultSearchHitPredicate

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineNodes

from nti.contenttypes.courses.utils import is_enrolled

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.dataserver.contenttypes.forums.interfaces import ICommunityForum
from nti.dataserver.contenttypes.forums.interfaces import IGeneralForumComment
from nti.dataserver.contenttypes.forums.interfaces import ICommunityHeadlinePost

from nti.dataserver.interfaces import IUserGeneratedData

from nti.dataserver.authorization import ACT_NTI_ADMIN
from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.users import User

from nti.property.property import Lazy

from nti.traversal.traversal import find_interface


@interface.implementer(ISearchHitPredicate)
class _CourseSearchHitPredicate(DefaultSearchHitPredicate):

    @Lazy
    def request(self):
        return get_current_request()

    @Lazy
    def user(self):
        return User.get_user(self.principal.id)

    def is_admin(self, context):
        return has_permission(ACT_NTI_ADMIN, context, self.request)

    def is_editor(self, context):
        return has_permission(ACT_CONTENT_EDIT, context, self.request)

    def check_nodes(self, nodes):
        for node in nodes or ():
            available = getattr(node, 'AvailableBeginning', None)
            beginning = available or ZERO_DATETIME
            lesson = INTILessonOverview(node, None)
            if 		lesson is not None \
                    and lesson.isPublished() \
                    and datetime.utcnow() >= beginning:
                return True  # first node found
        return False

    def allow(self, item, score, query=None):
        if self.principal is None or self.is_admin(item):
            return True
        nodes = component.queryMultiAdapter((item, self.user), 
                                            ICourseOutlineNodes)
        if not nodes:  # nothing points to it or no adapter
            return True
        return self.check_nodes(nodes)


@component.adapter(IContentUnit)
class _ContentHitPredicate(_CourseSearchHitPredicate):
    pass


@component.adapter(IPresentationAsset)
class _PresentationAssetHitPredicate(_CourseSearchHitPredicate):
    pass


@interface.implementer(IUserGeneratedData)
class _UserGeneratedDataHitPredicate(_CourseSearchHitPredicate):

    def allow(self, item, score, query=None):
        nodes = component.queryMultiAdapter((item, self.user), 
                                            ICourseOutlineNodes)
        if not nodes:  # nothing points to it or no adapter
            return True
        return self.check_nodes(nodes)

@interface.implementer(ICommunityForum)
class _CommunityForumHitPredicate(_CourseSearchHitPredicate):

    def allow(self, item, score, query=None):
        course = find_interface(item, ICourseInstance, strict=False)
        entry = ICourseCatalogEntry(course, None)
        if entry is not None:
            return (self.is_admin(course) or self.is_editor(course)) \
                or (is_enrolled(course, self.user) 
                    and not getattr(entry, 'Preview', False))
        return True

@interface.implementer(ICommunityHeadlinePost)
class _CommunityHeadlinePostHitPredicate(_CommunityForumHitPredicate):
    pass

@interface.implementer(IGeneralForumComment)
class _GeneralForumCommentHitPredicate(_CommunityHeadlinePostHitPredicate):
    pass
