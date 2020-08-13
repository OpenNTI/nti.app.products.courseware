#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from requests.structures import CaseInsensitiveDict

from zope.cachedescriptors.property import Lazy

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware import VIEW_CLASSMATES
from nti.app.products.courseware import VIEW_USER_ENROLLMENTS
from nti.app.products.courseware import VIEW_COURSE_CLASSMATES

from nti.app.products.courseware.interfaces import ICoursesWorkspace
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from nti.app.products.courseware.interfaces import IClassmatesSuggestedContactsProvider

from nti.app.products.courseware.views._utils import _parse_course

from nti.app.products.courseware.views import raise_error

from nti.app.products.courseware.views.catalog_views import do_course_enrollment

from nti.appserver.workspaces.interfaces import IUserService

from nti.common.string import is_true

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_enrollment_record
from nti.contenttypes.courses.utils import has_instructed_courses
from nti.contenttypes.courses.utils import drop_any_other_enrollments
from nti.contenttypes.courses.utils import is_instructor_in_hierarchy
from nti.contenttypes.courses.utils import get_context_enrollment_records

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin
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
    A view that returns the user enrollment records.
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
        # 403 if not admin or instructor or self
        return (   self._is_admin \
                or self.remoteUser == self.context \
                or has_instructed_courses(self.remoteUser)) \
            and self._can_admin_user()

    def __call__(self):
        records = get_context_enrollment_records(self.context, self.remoteUser) or ()
        if     not self._predicate() \
            or (not records and not self._is_admin):
            raise_error(
                {'message': _(u"Cannot view user enrollments."),
                 'code': 'CannotAccessUserEnrollmentsError',},
                factory=hexc.HTTPForbidden)
        result = LocatedExternalDict()
        records = sorted(records, key=lambda x:x.createdTime, reverse=True)
        result[TOTAL] = len(records)
        self._batch_items_iterable(result, records, selector=ICourseInstanceEnrollment)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IUser,
             name=VIEW_USER_ENROLLMENTS,
             request_method='POST')
class UserCreateEnrollmentView(AbstractAuthenticatedView,
                               ModeledContentUploadRequestUtilsMixin):
    """
    A view that allows a user to be enrolled in a course.

    `ntiid`: course/entry ntiid
    """

    @Lazy
    def _is_admin(self):
        return is_admin(self.remoteUser)

    @Lazy
    def _is_site_admin(self):
        return is_site_admin(self.remoteUser)

    def _can_admin_user(self):
        # Verify a site admin is administering a user in their site.
        result = True
        if self._is_site_admin:
            admin_utility = component.getUtility(ISiteAdminUtility)
            result = admin_utility.can_administer_user(self.remoteUser, self.context)
        return result

    def _predicate(self):
        # 403 if not admin or instructor or self
        return  (self._is_admin or self._is_site_admin) \
            and self._can_admin_user()

    def readInput(self, value=None):
        if self.request.body:
            values = super(UserCreateEnrollmentView, self).readInput(value)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    def __call__(self):
        if not self._predicate():
            raise_error(
                {'message': _(u"Cannot modify user enrollments."),
                 'code': 'CannotAccessUserEnrollmentsError',},
                factory=hexc.HTTPForbidden)
        values = self.readInput()
        context = _parse_course(values)
        user = self.context
        scope = values.get('scope', ES_PUBLIC)
        if not scope or scope not in ENROLLMENT_SCOPE_VOCABULARY.by_token:
            raise_error({'message': _(u"Invalid scope.")})
        if is_instructor_in_hierarchy(context, user):
            msg = _(u'User is an instructor in course hierarchy')
            raise_error({'message': _(msg)})
        interaction = is_true(values.get('email') or values.get('interaction'))
        # Make sure we don't have any interaction.
        # XXX: why?
        if not interaction:
            endInteraction()
        try:
            drop_any_other_enrollments(context, user)
            service = IUserService(user)
            workspace = ICoursesWorkspace(service)
            parent = workspace['EnrolledCourses']
            entry = ICourseCatalogEntry(context, None)
            logger.info("Enrolling %s in %s (%s)",
                        user, getattr(entry, 'ntiid', None), self.remoteUser)
            result = do_course_enrollment(context, user, scope,
                                          parent=parent,
                                          safe=True,
                                          request=self.request)
        finally:
            if not interaction:
                restoreInteraction()
        return result
