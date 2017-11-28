#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
__docformat__ = "restructuredtext en"

from zope import component

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from zope.cachedescriptors.property import Lazy

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware import VIEW_CLASSMATES
from nti.app.products.courseware import VIEW_USER_ENROLLMENTS
from nti.app.products.courseware import VIEW_COURSE_CLASSMATES

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from nti.app.products.courseware.interfaces import IClassmatesSuggestedContactsProvider

from nti.app.products.courseware.views import raise_error

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import get_enrollment_record
from nti.contenttypes.courses.utils import get_instructed_courses
from nti.contenttypes.courses.utils import get_context_enrollment_records

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_site_admin
from nti.dataserver.authorization import is_admin_or_site_admin

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISiteAdminUtility

from nti.dataserver.users.users import User

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


class BaseClassmatesView(AbstractAuthenticatedView, BatchingUtilsMixin):
    """
    batchSize The size of the batch.  Defaults to 50.
    batchStart The starting batch index.  Defaults to 0.
    """

    _DEFAULT_BATCH_SIZE = 50
    _DEFAULT_BATCH_START = 0

    def selector(self, contact):
        user = User.get_user(contact.username)
        if user is not None and self.remoteUser != user:
            ext = to_external_object(user, name="summary")
            ext.pop(LINKS, None)
            return ext
        return contact

    def export_suggestions(self, result_dict, suggestions):
        result_dict['TotalItemCount'] = len(suggestions)
        self._batch_items_iterable(result_dict,
                                   suggestions,
                                   selector=self.selector)
        result_dict[ITEM_COUNT] = len(result_dict.get(ITEMS) or ())


@view_config(context=ICourseInstance)
@view_config(context=ICourseInstanceEnrollment)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_READ,
               name=VIEW_COURSE_CLASSMATES)
class CourseClassmatesView(BaseClassmatesView):

    def __call__(self):
        record = get_enrollment_record(self.context, self.remoteUser)
        if record is None:
            raise hexc.HTTPForbidden(_("Must be enrolled in course."))
        result = LocatedExternalDict()
        provider = component.getUtility(IClassmatesSuggestedContactsProvider)
        suggestions = provider.suggestions_by_course(self.remoteUser,
                                                     self.context)
        self.export_suggestions(result, suggestions)
        return result


@view_config(context=IUser)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_READ,
               name=VIEW_CLASSMATES)
class ClassmatesView(BaseClassmatesView):

    def __call__(self):
        if self.remoteUser != self.request.context:
            raise hexc.HTTPForbidden()
        result = LocatedExternalDict()
        provider = component.getUtility(IClassmatesSuggestedContactsProvider)
        suggestions = provider.suggestions(self.remoteUser)
        self.export_suggestions(result, suggestions)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IUser,
             name=VIEW_USER_ENROLLMENTS,
             request_method='GET')
class UserEnrollmentsView(AbstractAuthenticatedView,
                          BatchingUtilsMixin):
    """
    A view that returns the user enrollment records. This view is
    """

    _DEFAULT_BATCH_START = 0
    _DEFAULT_BATCH_SIZE = None

    @Lazy
    def _is_admin(self):
        return is_admin_or_site_admin(self.remoteUser)

    def _can_admin_user(self):
        # Verify a site admin is administering a user in their site.
        result = True
        if is_site_admin(self.remoteUser):
            admin_utility = component.getUtility(ISiteAdminUtility)
            result = admin_utility.can_administer_user(self.remoteUser, self.context)
        return result

    def _predicate(self):
        # 403 if not admin or instructor
        return (    self._is_admin \
                or get_instructed_courses(self.remoteUser)) \
            and self._can_admin_user()

    def __call__(self):
        records = get_context_enrollment_records(self.context, self.remoteUser)
        if     not self._predicate() \
            or (not records and not self._is_admin):
            raise_error(
                {'message': _(u"Cannot view user enrollments."),
                 'code': 'CannotAccessUserEnrollmentsError',},
                factory=hexc.HTTPForbidden)
        if not records:
            raise_error(
                {'message': _(u"User enrollments not found."),
                 'code': 'UserEnrollmentsNotFound',},
                factory=hexc.HTTPNotFound)
        result = LocatedExternalDict()
        records = sorted(records, key=lambda x:x.createdTime, reverse=True)
        result[TOTAL] = len(records)
        self._batch_items_iterable(result, records, selector=ICourseInstanceEnrollment)
        return result
