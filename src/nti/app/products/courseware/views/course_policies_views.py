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

from nti.appserver.ugd_edit_views import UGDPutView, UGDDeleteView
from nti.appserver.ugd_edit_views import UGDPostView

from nti.contenttypes.courses.grading import reset_grading_policy
from nti.contenttypes.courses.grading import set_grading_policy_for_course
from nti.contenttypes.courses.grading import find_grading_policy_for_course

from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.dataserver import authorization as nauth

from nti.property.property import Lazy


class CourseGradingPolicyMixin(object):

    @Lazy
    def _course(self):
        return ICourseInstance(self.context)

    def _check(self):
        if      not is_course_instructor_or_editor(self._course, self.remoteUser) \
            and not has_permission(nauth.ACT_NTI_ADMIN, self._course, self.request):
            raise hexc.HTTPForbidden()


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name=VIEW_COURSE_GRADING_POLICY,
               permission=nauth.ACT_CONTENT_EDIT)
class CourseGradingPolicyGetView(AbstractAuthenticatedView, CourseGradingPolicyMixin):

    def __call__(self):
        self._check()
        policy = find_grading_policy_for_course(self._course)
        if policy is None:
            raise hexc.HTTPNotFound()
        return policy


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name=VIEW_COURSE_GRADING_POLICY,
               permission=nauth.ACT_CONTENT_EDIT)
class CourseGradingPolicyPostView(UGDPostView, CourseGradingPolicyMixin):

    content_predicate = ICourseGradingPolicy.providedBy

    def _do_call(self):
        self._check()

        creator = self.remoteUser
        policy = self.readCreateUpdateContentObject(creator,
                                                    search_owner=False)
        policy.creator = creator.username

        set_grading_policy_for_course(self._course, policy)
        lifecycleevent.created(policy)
        lifecycleevent.modified(self._course)

        self.request.response.status_int = 201
        return policy


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               name=VIEW_COURSE_GRADING_POLICY,
               permission=nauth.ACT_CONTENT_EDIT)
class CourseGradingPolicyPutView(UGDPutView, CourseGradingPolicyMixin):

    def _get_object_to_update(self):
        policy = find_grading_policy_for_course(self._course)
        if policy is None:
            raise hexc.HTTPNotFound()
        return policy

    def __call__(self):
        self._check()
        return UGDPutView.__call__(self)


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               name=VIEW_COURSE_GRADING_POLICY,
               permission=nauth.ACT_CONTENT_EDIT)
class CourseGradingPolicyDeleteView(UGDDeleteView, CourseGradingPolicyMixin):

    def _get_object_to_delete(self):
        policy = find_grading_policy_for_course(self._course)
        if policy is None:
            raise hexc.HTTPNotFound()
        return policy

    def _do_delete_object(self, obj):
        reset_grading_policy(self._course)
        lifecycleevent.removed(obj, self._course, None)
        return True

    def __call__(self):
        self._check()
        return UGDDeleteView.__call__(self)
