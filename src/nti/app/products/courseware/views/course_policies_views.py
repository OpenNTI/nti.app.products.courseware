#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import lifecycleevent

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.views import VIEW_COURSE_GRADING_POLICY

from nti.appserver.pyramid_authorization import has_permission

from nti.appserver.ugd_edit_views import UGDPostView

from nti.contenttypes.courses.grading import set_grading_policy_for_course
from nti.contenttypes.courses.grading import find_grading_policy_for_course

from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver import authorization as nauth

from nti.property.property import Lazy


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name=VIEW_COURSE_GRADING_POLICY,
               permission=nauth.ACT_CONTENT_EDIT)
class CourseGradingPolicyGetView(AbstractAuthenticatedView):

    @Lazy
    def _course(self):
        return ICourseInstance(self.context)

    def __call__(self):
        if      not is_course_instructor(self._course, self.remoteUser) \
            and not has_permission(nauth.ACT_NTI_ADMIN, self._course, self.request):
            raise hexc.HTTPForbidden()

        policy = find_grading_policy_for_course(self._course)
        if policy is None:
            raise hexc.HTTPNotFound()
        return policy


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_CONTENT_EDIT)
class CourseDiscussionsPostView(UGDPostView):

    content_predicate = ICourseGradingPolicy.providedBy

    @Lazy
    def _course(self):
        return ICourseInstance(self.context)

    def _do_call(self):
        if      not is_course_instructor(self._course, self.remoteUser) \
            and not has_permission(nauth.ACT_NTI_ADMIN, self._course, self.request):
            raise hexc.HTTPForbidden()

        creator = self.remoteUser
        policy = self.readCreateUpdateContentObject(creator,
                                                    search_owner=False)
        policy.creator = creator.username

        set_grading_policy_for_course(self._course, policy)
        lifecycleevent.created(self._course)

        self.request.response.status_int = 201
        return policy
