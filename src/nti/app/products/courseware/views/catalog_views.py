#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views relating to the course catalog and the courses workspace.

The initial strategy is to use a path adapter named Courses. It will
return something that isn't traversable (in this case, the Courses
workspace). Named views will be registered based on that to implement
the workspace collections.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import BTrees

import gevent
import itertools

from datetime import datetime
from six.moves import urllib_parse
from collections import defaultdict

from requests.structures import CaseInsensitiveDict

from zope import component
from zope import interface

from zope.authentication.interfaces import IUnauthenticatedPrincipal

from zope.cachedescriptors.property import Lazy

from zope.catalog.catalog import ResultSet

from zope.intid.interfaces import IIntIds

from zope.security.management import getInteraction

from zope.traversing.interfaces import IPathAdapter

from pyramid import httpexceptions as hexc

from pyramid.interfaces import IRequest

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.authentication import get_remote_user

from nti.app.base.abstract_views import AbstractView
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.completion.utils import has_completed_course

from nti.app.products.courseware.interfaces import ICoursesWorkspace
from nti.app.products.courseware.interfaces import ICoursesCollection
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from nti.app.products.courseware.interfaces import ICoursesCatalogCollection
from nti.app.products.courseware.interfaces import IEnrolledCoursesCollection
from nti.app.products.courseware.interfaces import IAdministeredCoursesCollection
from nti.app.products.courseware.interfaces import IAdministeredCoursesFavoriteFilter

from nti.app.products.courseware.views import MessageFactory as _
from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.app.products.courseware.views import VIEW_COURSE_BY_TAG
from nti.app.products.courseware.views import VIEW_CURRENT_COURSES
from nti.app.products.courseware.views import VIEW_ARCHIVED_COURSES
from nti.app.products.courseware.views import VIEW_COURSE_FAVORITES
from nti.app.products.courseware.views import VIEW_UPCOMING_COURSES
from nti.app.products.courseware.views import VIEW_COURSE_CATALOG_FAMILIES

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.appserver.pyramid_authorization import can_create
from nti.appserver.pyramid_authorization import has_permission

from nti.appserver.workspaces import VIEW_CATALOG_POPULAR
from nti.appserver.workspaces import VIEW_CATALOG_FEATURED

from nti.appserver.workspaces.interfaces import IUserService
from nti.appserver.workspaces.interfaces import IContainerCollection

from nti.base._compat import text_

from nti.common.string import is_true
from nti.common.string import is_false

from nti.contenttypes.courses.administered import get_course_admin_role

from nti.contenttypes.courses.index import get_enrollment_meta_catalog

from nti.contenttypes.courses.index import IX_ENROLLMENT_COUNT
from nti.contenttypes.courses.index import IX_ENTRY_START_DATE
from nti.contenttypes.courses.index import IX_ENTRY_END_DATE
from nti.contenttypes.courses.index import IX_ENTRY_TITLE_SORT
from nti.contenttypes.courses.index import IX_ENTRY_PUID_SORT

from nti.contenttypes.courses.index import get_courses_catalog

from nti.contenttypes.courses.interfaces import ES_PUBLIC

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import IDeletedCourse
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IDenyOpenEnrollment
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import InstructorEnrolledException
from nti.contenttypes.courses.interfaces import OpenEnrollmentNotAllowedException
from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntryFilterUtility

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import filter_hidden_tags
from nti.contenttypes.courses.utils import get_course_hierarchy
from nti.contenttypes.courses.utils import get_entry_intids_for_tag
from nti.contenttypes.courses.utils import get_non_tagged_entry_intids
from nti.contenttypes.courses.utils import entry_intids_to_course_intids
from nti.contenttypes.courses.utils import course_intids_to_entry_intids
from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin
from nti.dataserver.authorization import is_site_admin
from nti.dataserver.authorization import is_admin_or_site_admin
from nti.dataserver.authorization import is_admin_or_content_admin
from nti.dataserver.authorization import is_admin_or_content_admin_or_site_admin

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISiteAdminUtility
from nti.dataserver.interfaces import IDataserverFolder

from nti.datastructures.datastructures import LastModifiedCopyingUserList

from nti.dataserver.metadata.index import IX_CREATEDTIME

from nti.dataserver.metadata.index import get_metadata_catalog

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields

from nti.traversal import traversal
from nti.coremetadata.interfaces import IContextLastSeenContainer
from nti.ntiids.ntiids import find_object_with_ntiid

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

INTERNAL_NTIID = StandardInternalFields.NTIID

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IPathAdapter)
@component.adapter(IUser, IRequest)
def CoursesPathAdapter(context, unused_request):
    service = IUserService(context)
    workspace = ICoursesWorkspace(service)
    return workspace


@view_config(context=ICourseCatalogEntry)
class CatalogGenericGetView(GenericGetView):
    pass


def get_enrollments(course_instance, request):
    try:
        enrollments = component.getMultiAdapter((course_instance, request),
                                                ICourseEnrollmentManager)
    except LookupError:
        enrollments = ICourseEnrollmentManager(course_instance)
    return enrollments


def do_course_enrollment(context, user, scope=ES_PUBLIC, parent=None,
                         request=None, safe=False):
    course_instance = ICourseInstance(context)
    enrollments = get_enrollments(course_instance, request)
    freshly_added = enrollments.enroll(user, scope=scope)

    # get an course instance enrollent
    if not safe:
        enrollment = component.getMultiAdapter((course_instance, user),
                                               ICourseInstanceEnrollment)
    else:
        enrollment = component.queryMultiAdapter((course_instance, user),
                                                 ICourseInstanceEnrollment)

    if enrollment is not None:
        if parent and not enrollment.__parent__:
            enrollment.__parent__ = parent
    else:
        enrollment = freshly_added

    if freshly_added and request:
        request.response.status_int = 201
        request.response.location = traversal.resource_path(enrollment)

    # User is not able to enroll here, but admins can enroll them.
    if      scope == ES_PUBLIC \
        and IDenyOpenEnrollment.providedBy(course_instance) \
        and get_remote_user() == user:
        raise OpenEnrollmentNotAllowedException(_("Open enrollment is not allowed."))
    # Return our enrollment, whether fresh or not
    # This should probably be a multi-adapter
    return enrollment


@view_config(route_name='objects.generic.traversal',
             context=IEnrolledCoursesCollection,
             request_method='POST',
             permission=nauth.ACT_CREATE,
             renderer='rest')
class enroll_course_view(AbstractAuthenticatedView,
                         ModeledContentUploadRequestUtilsMixin):
    """
    POSTing a course identifier to the enrolled courses
    collection enrolls you in it. You can simply post the
    course catalog entry to this view as the identifier.

    At this writing, anyone is allowed to enroll in any course,
    so the only security on this is that the remote user
    has write permissions to the collection (which implies
    either its his collection or he's an admin).
    """

    inputClass = object

    def _do_call(self):
        catalog = component.getUtility(ICourseCatalog)
        identifier = self.readInput()
        catalog_entry = None
        # We accept either a raw string or a dict with
        # 'ntiid' or 'ProviderUniqueID', as per the catalog entry;
        # that's the preferred form.
        if isinstance(identifier, basestring):
            try:
                catalog_entry = catalog.getCatalogEntry(identifier)
            except KeyError:
                pass
        else:
            for k in (NTIID, INTERNAL_NTIID, 'ProviderUniqueID'):
                try:
                    k = identifier[k]
                    catalog_entry = catalog.getCatalogEntry(k)
                    # The above either finds the entry or throws a
                    # KeyError. NO NEED TO CHECK before breaking
                    break
                except (AttributeError, KeyError, TypeError):
                    pass

        if catalog_entry is None:
            raise_json_error(self.request,
                             hexc.HTTPNotFound,
                             {
                                 'message': _(u"There is no course by that name."),
                                 'code': 'NoCourseFoundError',
                             },
                             None)

        if not can_create(catalog_entry, request=self.request):
            raise hexc.HTTPForbidden()

        if IDeletedCourse.providedBy(ICourseInstance(catalog_entry)):
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _('Course is no longer available.'),
                                 'code': 'CourseNotAvailableError',
                             },
                             None)

        try:
            enrollment = do_course_enrollment(catalog_entry,
                                              self.remoteUser,
                                              parent=self.request.context,
                                              request=self.request)
        except InstructorEnrolledException as e:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': str(e) or e.i18n_message,
                                 'code': 'InstructorEnrolledError',
                             },
                             None)
        except OpenEnrollmentNotAllowedException as e:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': str(e) or e.i81n_message,
                                 'code': 'OpenEnrollmentNotAllowedError'
                             },
                             None)

        entry = catalog_entry
        if enrollment is not None:
            entry = ICourseCatalogEntry(enrollment.CourseInstance, None)
        entry = catalog_entry if entry is None else entry

        logger.info("User %s has enrolled in course %s",
                    self.remoteUser, entry.ntiid)

        return enrollment


class _AbstractSortingAndFilteringCoursesView(AbstractAuthenticatedView):
    """
    An abstract view to fetch the `favorite` courses of a user. All
    `current` courses will be returned, or the default minimum. Current
    courses are defined as being currently past their start date (or the
    start date is empty) and currently before the course end date (or the end
    date is empty).

    params
        count - the minimum number of courses to return
    """

    #: The default minimum number of items we return in our favorites view.
    DEFAULT_RESULT_COUNT = 4

    #: The maximum result set to return
    MAX_RESULT_SIZE = None

    @Lazy
    def requested_count(self):
        params = CaseInsensitiveDict(self.request.params)
        result = params.get('count') \
              or params.get('limit') \
              or params.get('size')
        if result:
            try:
                result = int(result)
            except TypeError:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u'Invalid count param.'),
                                     'code': 'InvalidCountParam'
                                 },
                                 None)
        return result

    @Lazy
    def minimum_count(self):
        return self.requested_count or self.DEFAULT_RESULT_COUNT

    def _sort_key(self, entry_tuple):
        start_date = entry_tuple[0].StartDate
        return (start_date is not None, start_date)

    def _secondary_sort_key(self, entry_tuple):
        result = entry_tuple[0].ProviderUniqueID
        return result and result.lower()

    @Lazy
    def now(self):
        return datetime.utcnow()

    def _get_entry_for_record(self, record):
        course = record.CourseInstance
        entry = ICourseCatalogEntry(course, None)
        return entry

    def iter_entries_and_records(self):
        for record in self.context.container or ():
            entry = self._get_entry_for_record(record)
            if entry is not None:
                gevent.sleep()
                yield (entry, record)

    @Lazy
    def entries_and_records(self):
        return tuple(self.iter_entries_and_records())

    def _include_filter(self, unused_entry):
        """
        Subclasses may use this to filter courses.
        """
        return True

    @Lazy
    def sorted_entries_and_records(self):
        # Sort secondary key first, ascending alpha
        result = sorted(self.iter_entries_and_records(), key=self._secondary_sort_key)
        # Then primary key (date), most recent first
        result = sorted(result,
                        key=self._sort_key,
                        reverse=True)
        return result

    def _is_entry_current(self, entry):
        now = self.now
        return  (entry.StartDate is None or now > entry.StartDate) \
            and (entry.EndDate is None or now < entry.EndDate)

    def _is_entry_upcoming(self, entry):
        return entry.StartDate is not None and self.now < entry.StartDate

    @Lazy
    def sorted_current_entries_and_records(self):
        # pylint: disable=not-an-iterable
        result = [x for x in self.sorted_entries_and_records
                  if self._is_entry_current(x[0]) and self._include_filter(x[0])]
        return result

    def _get_items(self):
        """
        Get our result set items, which will include the `current`
        enrollments backfilled with the most recent.
        """
        # pylint: disable=not-an-iterable
        result = self.sorted_current_entries_and_records
        if len(result) < self.minimum_count:
            # Backfill with most-recent items
            seen_entries = set(x[0] for x in result)
            for entry_tuple in self.sorted_entries_and_records:
                if entry_tuple[0] not in seen_entries:
                    # pylint: disable=no-member
                    result.append(entry_tuple)
                    if len(result) >= self.minimum_count:
                        break
        # Now grab the records we want
        result = [x[1] for x in result]
        return result

    def __call__(self):
        result = LocatedExternalDict()
        items = self._get_items()
        if self.MAX_RESULT_SIZE and len(items) > self.MAX_RESULT_SIZE:
            items = items[:self.MAX_RESULT_SIZE]
        result[ITEMS] = items
        result[ITEM_COUNT] = len(items)
        result[TOTAL] = len(self.sorted_entries_and_records)
        return result


@view_config(route_name='objects.generic.traversal',
             context=IEnrolledCoursesCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_COURSE_FAVORITES,
             renderer='rest')
class FavoriteEnrolledCoursesView(_AbstractSortingAndFilteringCoursesView):
    """
    A view into the `favorite` enrolled courses of a user. We want to sort
    by enrollment record here.
    """

    def _sort_key(self, entry_tuple):
        enrollment = entry_tuple[1]
        return enrollment.createdTime

    def _include_filter(self, entry):
        """
        We only want to return non-completed or failed-completed courses.
        """
        course = ICourseInstance(entry, None)
        result = True
        if course is not None:
            result = not has_completed_course(self.remoteUser, course, success_only=True)
        return result


@view_config(route_name='objects.generic.traversal',
             context=IAdministeredCoursesCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_COURSE_FAVORITES,
             renderer='rest')
class FavoriteAdministeredCoursesView(_AbstractSortingAndFilteringCoursesView):
    """
    A view into the `favorite` administered courses of a user.
    """

    MAX_RESULT_SIZE = 28

    @Lazy
    def _admin_favorites_filter(self):
        return component.queryUtility(IAdministeredCoursesFavoriteFilter)

    def _include_filter(self, entry):
        """
        Subclasses may use this to filter courses.
        """
        favorites_filter = self._admin_favorites_filter
        result = True
        if favorites_filter is not None:
            user = self.context.__parent__.user
            result = favorites_filter.include_entry(user, entry)
        if result:
            course = ICourseInstance(entry)
            result = not IDeletedCourse.providedBy(course)
        return result

    def _get_items(self):
        """
        Get our result set items, which will include the `current`
        courses backfilled with the most recent.

        The result set will be sorted by PUID - start date or not.
        """
        intids = component.getUtility(IIntIds)
        courses_catalog = get_courses_catalog()
        course_intids = self.context.course_intids
        user_entry_ids = course_intids_to_entry_intids(course_intids)
        filter_utility = component.getUtility(ICourseCatalogEntryFilterUtility)
        current_intids = filter_utility.get_current_entry_intids(user_entry_ids)
        sorted_current_ids = courses_catalog[IX_ENTRY_PUID_SORT].sort(current_intids)

        if len(current_intids) < self.minimum_count:
            # XXX: We will gather up to max on this path
            # If less than minimum, add our sorted_puids to the mix
            sorted_puids = courses_catalog[IX_ENTRY_PUID_SORT].sort(user_entry_ids)
            # Make sure we do not have duplicates
            sorted_puids = (x for x in sorted_puids if x not in current_intids)
            iter_intids = itertools.chain(sorted_current_ids, sorted_puids)
        else:
            # Otherwise this is enough
            iter_intids = sorted_current_ids

        result = []
        entry_rs = ResultSet(iter_intids, intids)
        user = self.context.__parent__.user
        # Collect until we reach max or run out of items
        for entry in entry_rs:
            if len(result) == self.MAX_RESULT_SIZE:
                break
            if self._include_filter(entry):
                course = ICourseInstance(entry)
                admin_role = get_course_admin_role(course, user)
                result.append(admin_role)
        return result

    def __call__(self):
        # XXX: Work here with parent class
        result = LocatedExternalDict()
        items = self._get_items()
        result[ITEMS] = items
        result[ITEM_COUNT] = len(items)
        result[TOTAL] = len(self.context)
        return result


@view_config(route_name='objects.generic.traversal',
             context=ICourseInstanceEnrollment,
             request_method='DELETE',
             renderer='rest')
class drop_course_view(AbstractAuthenticatedView):
    """
    Dropping a course consists of DELETEing its appearance
    in your enrolled courses view.

    For this to work, it requires that the IEnrolledCoursesCollection
    is not itself traverseable to children.

    NT and site admins can also delete the enrollment record.
    """

    @Lazy
    def _is_admin(self):
        return is_admin(self.remoteUser)

    @Lazy
    def _is_site_admin(self):
        return is_site_admin(self.remoteUser)

    def _can_admin_user(self, user):
        # Verify a site admin is administering a user in their site.
        result = False
        if self._is_site_admin:
            admin_utility = component.getUtility(ISiteAdminUtility)
            result = admin_utility.can_administer_user(self.remoteUser, user)
        return result

    def _check_access(self, user):
        # 403 if not admin or site admin or self
        # We used to check DELETE perms (instructors have DELETE perm
        # through course). An open question is whether instructors should
        # be able to drop users.
        return     self._is_admin \
                or self.remoteUser == user \
                or self._can_admin_user(user)

    @Lazy
    def _params(self):
        values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    @Lazy
    def override_completion(self):
        """
        Unenroll the user even if they have completed the course.
        """
        result = self._params.get('override_completion', False)
        return is_true(result)

    def __call__(self):
        course = self.request.context.CourseInstance
        user = IUser(self.context, None)
        if user is None:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Cannot find user for enrollment."),
                                 'code': 'MissingEnrollmentUserError',
                             },
                             None)
        if not self._check_access(user):
            raise_json_error(self.request,
                             hexc.HTTPForbidden,
                             {
                                 'message': _(u"Cannot drop the user."),
                                 'code': 'DropEnrollmentAccessError'
                             },
                             None)
        if not self.override_completion and has_completed_course(user, course):
            raise_json_error(self.request,
                             hexc.HTTPForbidden,
                             {
                                 'message': _(u"Cannot drop a completed course."),
                                 'code': 'CannotDropCompletedCourseError',
                             },
                             None)
        catalog_entry = ICourseCatalogEntry(course)
        enrollments = get_enrollments(course, self.request)
        enrollments.drop(user)
        logger.info("User %s has dropped from course %s (%s)",
                    user, catalog_entry.ntiid, self.remoteUser)
        return hexc.HTTPNoContent()


@view_config(name='AllCourses')
@view_config(name='AllCatalogEntries')
@view_defaults(route_name='objects.generic.traversal',
               context=CourseAdminPathAdapter,
               request_method='GET',
               permission=nauth.ACT_NTI_ADMIN,
               renderer='rest')
class AllCatalogEntriesView(AbstractAuthenticatedView):

    def __call__(self):
        catalog = component.getUtility(ICourseCatalog)
        result = LocatedExternalDict()
        items = result[ITEMS] = tuple(catalog.iterCatalogEntries())
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result


@view_config(name='AnonymouslyButNotPubliclyAvailableCourseInstances')
@view_config(name='_AnonymouslyButNotPubliclyAvailableCourseInstances')
@view_defaults(name='_AnonymouslyButNotPubliclyAvailableCourseInstances',
               route_name='objects.generic.traversal',
               request_method='GET',
               context=IDataserverFolder,
               renderer='rest')
class AnonymouslyAvailableCourses(AbstractView):

    def _can_access(self):
        """
        Only let requests that are actually anonymous, those which the interaction
        provides IUnauthenticatedPrincipal, fetch this information
        """
        # we should always have an interaction here at this point right?
        # if we don't something went really wrong and we probably want to blow
        # up aggressively.
        principal = getInteraction().participations[0].principal
        return IUnauthenticatedPrincipal.providedBy(principal)

    def __call__(self):
        if not self._can_access():
            raise hexc.HTTPForbidden()

        catalog = component.getUtility(ICourseCatalog)
        result = LocatedExternalDict()
        items = result[ITEMS] = []
        for e in catalog.iterCatalogEntries():
            if IAnonymouslyAccessibleCourseInstance.providedBy(e):
                course_instance = ICourseInstance(e)
                ext_obj = to_external_object(course_instance)
                items.append(ext_obj)
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name=VIEW_COURSE_CATALOG_FAMILIES,
               request_method='GET',
               permission=nauth.ACT_READ)
class UserCourseCatalogFamiliesView(AbstractAuthenticatedView):
    """
    A view that fetches the parent/subinstance :class:`ICourseCatalogEntry`
    objects of the given context.
    """

    @Lazy
    def _course(self):
        return ICourseInstance(self.context)

    @Lazy
    def _is_admin(self):
        return is_admin_or_content_admin(self.remoteUser)

    def _is_visible(self, course):
        """
        Course is visible if we're an admin (all courses), instructor/editor,
        or enrolled.
        ACT_CONTENT_EDIT will allow access to site admins.
        """
        return self._is_admin \
            or is_course_instructor_or_editor(course, self.remoteUser) \
            or is_enrolled(course, self.remoteUser) \
            or has_permission(nauth.ACT_CONTENT_EDIT, course, self.request)

    def _get_entries(self):
        """
        Fetch all catalog entries for courses we have access to.
        """
        result = []
        courses = get_course_hierarchy(self._course)
        for course in courses or ():
            if self._is_visible(course):
                entry = ICourseCatalogEntry(course)
                result.append(entry)
        return result

    def __call__(self):
        result = LocatedExternalDict()
        entries = self._get_entries()
        result[ITEM_COUNT] = len(entries)
        result[ITEMS] = entries
        return result


class _AbstractFilteredCourseView(_AbstractSortingAndFilteringCoursesView,
                                  BatchingUtilsMixin):

    DESC_SORT_ORDER = True
    _DEFAULT_BATCH_START = None
    _DEFAULT_BATCH_SIZE = None

    def _get_entry_for_record(self, record):
        entry = ICourseCatalogEntry(record, None)
        return entry

    @Lazy
    def filtered_entries(self):
        return [x for x in self.iter_entries_and_records() if self._include_filter(x[0])]

    @Lazy
    def sorted_filtered_entries_and_records(self):
        result = sorted(self.filtered_entries,
                        key=self._sort_key,
                        reverse=self.DESC_SORT_ORDER)
        return result

    def _get_items(self):
        """
        Get the courses relevant in the collection
        """
        result = self.sorted_filtered_entries_and_records
        # Now grab the records we want
        result = [x[1] for x in result]
        return result

    def __call__(self):
        result = LocatedExternalDict()
        result[ITEMS] = items = self._get_items()
        result[ITEM_COUNT] = len(items)
        result[TOTAL] = len(self.filtered_entries)
        self._batch_items_iterable(result, items)
        return result


@view_config(route_name='objects.generic.traversal',
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_UPCOMING_COURSES,
             context=IContainerCollection)
class UpcomingCoursesView(_AbstractFilteredCourseView):
    """
    Fetch all upcoming courses in the collection
    """

    def _include_filter(self, entry):
        return self._is_entry_upcoming(entry)


@view_config(route_name='objects.generic.traversal',
             context=IContainerCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_ARCHIVED_COURSES)
class ArchivedCoursesView(_AbstractFilteredCourseView):
    """
    Fetch all archived courses in the collection
    """

    def _include_filter(self, entry):
        now = self.now
        return entry.EndDate is not None and now > entry.EndDate


@view_config(route_name='objects.generic.traversal',
             context=IContainerCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_CURRENT_COURSES)
class CurrentCoursesView(_AbstractFilteredCourseView):
    """
    Fetch all current courses in the collection
    """

    def _include_filter(self, entry):
        return self._is_entry_current(entry)


@view_config(route_name='objects.generic.traversal',
             context=ICoursesCatalogCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_CATALOG_POPULAR)
class PopularCoursesView(_AbstractFilteredCourseView):
    """
    We want to return all `popular` courses, which by definition, are current
    or upcoming, sorted by enrollment count.
    """

    @Lazy
    def _entry_intids(self):
        return self.context.entry_intids()

    def _raise_not_found(self):
        raise_json_error(self.request,
                         hexc.HTTPNotFound,
                         {
                             'message': _(u"There are no popular courses."),
                             'code': 'NoPopularCoursesFoundError',
                         },
                         None)

    def _batch_selector(self, course):
        return ICourseCatalogEntry(course, None)

    def _get_items(self):
        courses_catalog = get_courses_catalog()
        user_entry_intids = self._entry_intids
        now = datetime.utcnow()
        # Get all current/upcoming entry intids
        filter_utility = component.getUtility(ICourseCatalogEntryFilterUtility)
        current_entry_intids = filter_utility.get_current_entry_intids(user_entry_intids)
        future_entry_intids = filter_utility.get_entry_intids_by_dates(start_not_before=now)
        future_user_entry_ids = courses_catalog.family.IF.intersection(user_entry_intids,
                                                                       future_entry_intids)
        current_upcoming_entry_intids = courses_catalog.family.IF.union(current_entry_intids,
                                                                        future_user_entry_ids)
        if not current_upcoming_entry_intids:
            self._raise_not_found()
        # Now get our course intids
        course_intids = entry_intids_to_course_intids(current_upcoming_entry_intids)

        # Now sort with our index
        enrollment_meta_catalog = get_enrollment_meta_catalog()
        count_idx = enrollment_meta_catalog[IX_ENROLLMENT_COUNT]
        sorted_course_intids = count_idx.sort(course_intids, reverse=True)
        count_idx_intids = BTrees.family64.IF.Set(count_idx.ids())
        empty_enrollment_intids = courses_catalog.family.IF.difference(course_intids,
                                                                       count_idx_intids)
        result_intids = itertools.chain(sorted_course_intids, empty_enrollment_intids)
        intids = component.getUtility(IIntIds)
        return ResultSet(result_intids, intids), len(current_upcoming_entry_intids)

    def __call__(self):
        result = LocatedExternalDict()
        items, item_count = self._get_items()
        result[TOTAL] = item_count
        self._batch_items_iterable(result, items,
                                   selector=self._batch_selector)
        return result


@view_config(route_name='objects.generic.traversal',
             context=ICoursesCatalogCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_CATALOG_FEATURED)
class FeaturedCoursesView(_AbstractFilteredCourseView):
    """
    We want to return all `featured` courses, which by definition, are the
    upcoming courses closest to starting.
    """

    DEFAULT_RESULT_COUNT = 3
    MINIMUM_RESULT_COUNT = 1
    DESC_SORT_ORDER = False

    @Lazy
    def minimum_featured_count(self):
        return self.requested_count or self.MINIMUM_RESULT_COUNT

    def should_return_featured_entries(self):
        """
        We only return if our collection is twice the size of the requested
        featured item count (defaulting to 3).
        """
        return len(self._entry_intids) >= 2 * self.minimum_featured_count

    def _raise_not_found(self):
        raise_json_error(self.request,
                         hexc.HTTPNotFound,
                         {
                             'message': _(u"There are no featured courses."),
                             'code': 'NoFeaturedCoursesFoundError',
                         },
                         None)

    @Lazy
    def _entry_intids(self):
        return self.context.entry_intids()

    def _get_items(self):
        courses_catalog = get_courses_catalog()
        user_entry_intids = self._entry_intids
        now = datetime.utcnow()
        # Get all entries starting after now
        filter_utility = component.getUtility(ICourseCatalogEntryFilterUtility)
        future_entry_intids = filter_utility.get_entry_intids_by_dates(start_not_before=now)
        future_user_entry_ids = courses_catalog.family.IF.intersection(user_entry_intids,
                                                                       future_entry_intids)
        if not future_user_entry_ids:
            self._raise_not_found()
        sorted_ids = courses_catalog[IX_ENTRY_START_DATE].sort(future_user_entry_ids)
        intids = component.getUtility(IIntIds)
        return ResultSet(sorted_ids, intids), len(future_user_entry_ids)

    def _get_return_count(self, item_count):
        return_count = self.requested_count
        unused_batch_size, batch_start = self._get_batch_size_start()
        if not return_count and not batch_start:
            # If not a requested count and not a batch, bound between 1 and 3.
            half_item_count = item_count // 2
            return_count = min(half_item_count, self.DEFAULT_RESULT_COUNT)
            return_count = max(return_count, self.MINIMUM_RESULT_COUNT)
        return return_count

    def __call__(self):
        if not self.should_return_featured_entries():
            self._raise_not_found()
        result = LocatedExternalDict()
        items, item_count = self._get_items()
        return_count = self._get_return_count(item_count)
        result[ITEMS] = items
        result[ITEM_COUNT] = return_count
        result[TOTAL] = item_count
        self._batch_items_iterable(result, items,
                                   batch_size=return_count,
                                   batch_start=0)
        return result


@view_config(context=ICoursesCollection)
@view_defaults(route_name='objects.generic.traversal',
               request_method='GET',
               permission=nauth.ACT_READ)
class CourseCollectionView(_AbstractFilteredCourseView,
                           BatchingUtilsMixin):
    """
    A generic view to return an :class:`ICoursesCollection` container, with
    paging and filtering.

    By default, we return sorted by the catalog entry title and start date.

    params:
        filter - (optional) include a catalog entry containing this str;
            comma separate multiple filters

        filterOperator - (optional) either union or intersection if multiple filters
            are supplied

    """

    #: To maintain BWC; disable paging by default.
    _DEFAULT_BATCH_SIZE = None
    _DEFAULT_BATCH_START = None

    DESC_SORT_ORDER = False

    @Lazy
    def sort_key_to_func(self):
        return  {'title': lambda x: x[0].title and x[0].title.lower(),
                 'startdate': lambda x: (x[0].StartDate is not None, x[0].StartDate),
                 'enddate': lambda x: (x[0].EndDate is not None, x[0].EndDate),
                 'provideruniqueid': lambda x: x[0].ProviderUniqueID.lower(),
                 'createdtime': lambda x: x[1].createdTime,
                 'lastseentime': self._sort_record_by_last_seen,
                 'enrolled': lambda x: ICourseEnrollments(x[1].CourseInstance).count_enrollments()}

    @Lazy
    def _allowed_sorting_keys(self):
        return self.sort_key_to_func

    _ALLOWED_SORTING = _allowed_sorting_keys

    def _include_filter(self, unused_entry):  # pylint: disable=arguments-differ
        pass

    @Lazy
    def _params(self):
        values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    @Lazy
    def filter_str(self):
        """
        Returns a set of filter strings, used for searching.
        """
        # pylint: disable=no-member
        result = self._params.get('filter')
        if result:
            result = result.split(',')
            result = [x.lower() for x in result]
        return result

    @Lazy
    def filter_union(self):
        param = self.request.params.get('filterOperator', 'union')
        return param.lower() == 'union'

    @Lazy
    def filtered_entries(self):
        # pylint: disable=not-an-iterable
        filter_utility = component.getUtility(ICourseCatalogEntryFilterUtility)
        entries = filter_utility.filter_entries(self.iter_entries_and_records(),
                                                self.filter_str,
                                                selector=lambda x: x[0],
                                                union=self.filter_union)
        return entries

    @Lazy
    def last_seen_container(self):
        return IContextLastSeenContainer(self.remoteUser)

    def _sort_record_by_last_seen(self, record):
        course = record[1].CourseInstance
        puid = record[0].ProviderUniqueID.lower()
        last_seen = self.last_seen_container.get(course.ntiid)
        last_seen_timestamp = getattr(last_seen, 'timestamp', None)
        if self.sort_reverse:
            return (last_seen_timestamp, puid)
        else:
            return (last_seen_timestamp is None, last_seen_timestamp, puid)

    def _sort_key(self, entry_tuple):
        entry = entry_tuple[0]
        title = entry.title and entry.title.lower()
        start_date = entry.StartDate
        return (not title, title, start_date is not None, start_date)

    @Lazy
    def sortOn(self):
        sortOn = self._params.get('sortOn')
        sortOn = sortOn.lower() if sortOn else sortOn
        return sortOn if sortOn in self._ALLOWED_SORTING else None

    @Lazy
    def sortOrder(self):
        return self._params.get('sortOrder', 'ascending')

    @Lazy
    def sort_reverse(self):
        return self.sortOrder == 'descending'

    @Lazy
    def sorted_filtered_entries_and_records(self):
        sort_key = self.sort_key_to_func.get(self.sortOn) if self.sortOn else self._sort_key
        result = sorted(self.filtered_entries,
                        key=sort_key,
                        reverse=self.sort_reverse)
        return result

    def __call__(self):
        container_count = len(self.context)
        new_items = self._get_items()
        # Make sure we do our batching before we externalize
        ext_dict = LocatedExternalDict()
        self._batch_items_iterable(ext_dict, new_items)
        # Toggle our container and externalize for batching.
        new_container = LastModifiedCopyingUserList()
        new_container.extend(ext_dict[ITEMS])
        self.context.container = new_container
        result = to_external_object(self.context)
        result[TOTAL] = container_count
        result['FilteredTotalItemCount'] = len(new_container)

        # Need to manually add our batch rels
        batch_size, batch_start = self._get_batch_size_start()
        if batch_size is not None and batch_start is not None:
            result['BatchPage'] = batch_start // batch_size + 1
            prev_batch_start, next_batch_start = self._batch_start_tuple(batch_start,
                                                                         batch_size,
                                                                         len(new_items))

            self._set_batch_links(result, result,
                                  next_batch_start, prev_batch_start)
        return result


@view_config(route_name='objects.generic.traversal',
             context=IEnrolledCoursesCollection,
             request_method='GET',
             permission=nauth.ACT_READ)
class EnrolledCourseCollectionView(CourseCollectionView):
    """
    A generic view to return an :class:`IEnrolledCoursesCollection` container, with
    paging and filtering.

    Sorted by the enrollment record time desc.

    TODO: clean up this hierarchy
    - Move filtering to generic course collection view instead of specifci endpoints
    - Use enrollment record intids to use index based sorting
    """

    DESC_SORT_ORDER = True

    def _sort_key(self, entry_tuple):
        enrollment = entry_tuple[1]
        return enrollment.createdTime

    def _get_entry_for_record(self, record):
        course = record.CourseInstance
        entry = ICourseCatalogEntry(course, None)
        return entry


class AbstractIndexedCoursesCollectionView(CourseCollectionView):
    """
    Access to the user's collection of courses. This collection
    may have access to all courses in the site (e.g. thousands).

    Because of this, we we need to operate on the intid level such that we only
    reify the objects we need for this user.
    """

    DEFAULT_SORT_KEY = 'provideruniqueid'

    @Lazy
    def sort_key_to_func(self):
        return {'title': self._title_sort,
                'provideruniqueid': self._puid_sort,
                'startdate': self._start_date_sort,
                'enddate': self._end_date_sort,
                'lastseentime': self._last_seen_sort,
                'createdtime': self._created_time_sort}

    def _do_sort(self, idx, result_intids):
        return idx.sort(result_intids, reverse=self.sort_reverse)

    def _entry_intids_idx_sort(self, idx_key, result_intids):
        course_catalog = get_courses_catalog()
        idx = course_catalog[idx_key]
        return self._do_sort(idx, result_intids)

    def _title_sort(self, entry_intids):
        return self._entry_intids_idx_sort(IX_ENTRY_TITLE_SORT, entry_intids)

    def _puid_sort(self, entry_intids):
        return self._entry_intids_idx_sort(IX_ENTRY_PUID_SORT, entry_intids)

    def _start_date_sort(self, entry_intids):
        return self._entry_intids_idx_sort(IX_ENTRY_START_DATE, entry_intids)

    def _end_date_sort(self, entry_intids):
        return self._entry_intids_idx_sort(IX_ENTRY_END_DATE, entry_intids)

    def _created_time_sort(self, entry_intids):
        # This is only indexed on course intids - entries do not have valid
        # times (should fix this).
        course_intids = entry_intids_to_course_intids(entry_intids)
        catalog = get_metadata_catalog()
        idx = catalog[IX_CREATEDTIME]
        return self._do_sort(idx, course_intids)

    @Lazy
    def sorted_courses_by_lastseen(self):
        """
        This is a bit expansive. Reify all objects in this container
        looking for courses and then sort them. This should only be
        called if needed.
        """
        result = []
        for val in self.last_seen_container.values():
            # Currently, we store these by course OIDs.
            obj = find_object_with_ntiid(val.ntiid)
            if ICourseInstance.providedBy(obj):
                result.append((obj, val))
        result = sorted(result, key=lambda x: x[1].timestamp, reverse=self.sort_reverse)
        result = [x[0] for x in result]
        return result

    def _last_seen_sort(self, user_entry_intids):
        """
        Gather the ordered entry intids by last seen time, backfilling
        with those unopened courses.
        """
        intids = component.getUtility(IIntIds)
        entries = (ICourseCatalogEntry(x) for x in self.sorted_courses_by_lastseen)
        entry_intids = (intids.queryId(x) for x in entries)
        valid_entry_intids = [x for x in entry_intids if x in user_entry_intids]
        unopened_intids = set(user_entry_intids) - set(valid_entry_intids)
        courses_catalog = get_courses_catalog()
        sorted_unopened_intids = courses_catalog[IX_ENTRY_PUID_SORT].sort(unopened_intids,
                                                                          reverse=self.sort_reverse)
        sorted_ids = itertools.chain(valid_entry_intids, sorted_unopened_intids)
        return sorted_ids

    @Lazy
    def _entry_intids(self):
        """
        The user intids.
        """
        raise NotImplementedError()

    def _batch_selector(self, entry):
        """
        Passed to the batch iterables. We can convert our entry object or
        filter it here (by returning None).
        """
        return entry

    def filter_intids(self, entry_intids):
        # No-op - subclasses may change
        return entry_intids

    def _get_items(self):
        """
        Get the courses relevant in the collection
        """
        # Get our entry intids first
        courses_catalog = get_courses_catalog()
        user_entry_ids = self._entry_intids
        if self.filter_str:
            filter_utility = component.getUtility(ICourseCatalogEntryFilterUtility)
            filtered_entry_ids = filter_utility.get_entry_intids_for_filters(self.filter_str,
                                                                             union=self.filter_union)
            user_entry_ids = courses_catalog.family.IF.intersection(user_entry_ids,
                                                                    filtered_entry_ids)
        user_entry_ids = self.filter_intids(user_entry_ids)
        sortOn = self.sortOn or self.DEFAULT_SORT_KEY
        sort_func = self.sort_key_to_func.get(sortOn)
        if sort_func is None:
            raise hexc.HTTPUnprocessableEntity("Invalid sort")
        sorted_ids = sort_func(user_entry_ids)
        # For our two, possibly empty, attributes (start/end date),
        # we want to backfill with the remaining entry_ids (sorted by PUID???).
        # `sorted_ids` is now a generator.
        # Similarly to previous in-memory implementations, we'll want to return `None`
        # values last in descending order and vice versa.
        if sortOn in ('startdate', 'enddate'):
            sort_idx_key = IX_ENTRY_START_DATE if sortOn == 'startdate' else IX_ENTRY_END_DATE
            sort_idx = courses_catalog[sort_idx_key]
            sort_idx_intids = BTrees.family64.IF.Set(sort_idx.ids())
            non_date_intids = courses_catalog.family.IF.difference(user_entry_ids, sort_idx_intids)
            sorted_non_date_intids = courses_catalog[IX_ENTRY_PUID_SORT].sort(non_date_intids,
                                                                              reverse=self.sort_reverse)
            sorted_ids = itertools.chain(sorted_ids, sorted_non_date_intids)
        intids = component.getUtility(IIntIds)
        return ResultSet(sorted_ids, intids), len(user_entry_ids)

    def __call__(self):
        # XXX: Worth trying to fit this in parent __call__ logic?
        container_count = len(self.context)
        sorted_rs, filtered_count = self._get_items()
        # Make sure we do our batching before we externalize (??)
        ext_dict = LocatedExternalDict()
        self._batch_items_iterable(ext_dict, sorted_rs,
                                   selector=self._batch_selector)
        # Toggle our container and externalize for batching.
        new_container = LastModifiedCopyingUserList()
        new_container.extend(ext_dict[ITEMS])
        self.context.container = new_container
        result = to_external_object(self.context)
        result[TOTAL] = container_count
        result['FilteredTotalItemCount'] = filtered_count

        # Need to manually add our batch rels
        batch_size, batch_start = self._get_batch_size_start()
        if batch_size is not None and batch_start is not None:
            result['BatchPage'] = batch_start // batch_size + 1
            prev_batch_start, next_batch_start = self._batch_start_tuple(batch_start,
                                                                         batch_size,
                                                                         filtered_count)

            self._set_batch_links(result, result,
                                  next_batch_start, prev_batch_start)
        return result


@view_config(route_name='objects.generic.traversal',
             context=IAdministeredCoursesCollection,
             request_method='GET',
             permission=nauth.ACT_READ)
class AdministeredCoursesCollectionView(AbstractIndexedCoursesCollectionView):

    @Lazy
    def _entry_intids(self):
        course_intids = self.context.course_intids
        user_entry_ids = course_intids_to_entry_intids(course_intids)
        return user_entry_ids

    def _batch_selector(self, entry):
        """
        Turns our catalog entry into an administrative role.
        """
        course = ICourseInstance(entry)
        # This will effectively filter out partially deleted courses while
        # building the batch.
        if not IDeletedCourse.providedBy(course):
            return get_course_admin_role(course, self.context.__parent__.user)
        return None


@view_config(route_name='objects.generic.traversal',
             context=ICoursesCatalogCollection,
             request_method='GET',
             permission=nauth.ACT_READ)
class CoursesCatalogCollectionView(AbstractIndexedCoursesCollectionView):

    @Lazy
    def _entry_intids(self):
        return self.context.entry_intids()


@view_config(route_name='objects.generic.traversal',
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_UPCOMING_COURSES,
             context=IAdministeredCoursesCollection)
class AdministeredUpcomingCoursesView(AdministeredCoursesCollectionView):
    """
    Fetch all upcoming courses in the collection
    """

    def filter_intids(self, entry_intids):
        filter_utility = component.getUtility(ICourseCatalogEntryFilterUtility)
        now = datetime.utcnow()
        upcoming_intids = filter_utility.get_entry_intids_by_dates(start_not_before=now)
        catalog = get_courses_catalog()
        return catalog.family.IF.intersection(entry_intids, upcoming_intids)


@view_config(route_name='objects.generic.traversal',
             context=IAdministeredCoursesCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_ARCHIVED_COURSES)
class AdministeredArchivedCoursesView(AdministeredCoursesCollectionView):
    """
    Fetch all archived courses in the collection
    """

    def filter_intids(self, entry_intids):
        filter_utility = component.getUtility(ICourseCatalogEntryFilterUtility)
        now = datetime.utcnow()
        archived_intids = filter_utility.get_entry_intids_by_dates(end_not_after=now)
        catalog = get_courses_catalog()
        return catalog.family.IF.intersection(entry_intids, archived_intids)


@view_config(route_name='objects.generic.traversal',
             context=IAdministeredCoursesCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_CURRENT_COURSES)
class AdministeredCurrentCoursesView(AdministeredCoursesCollectionView):
    """
    Fetch all current courses in the collection. This will include courses
    without dates (e.g. always current).
    """

    def filter_intids(self, entry_intids):
        filter_utility = component.getUtility(ICourseCatalogEntryFilterUtility)
        return filter_utility.get_current_entry_intids(entry_intids)


@view_config(route_name='objects.generic.traversal',
             context=ICoursesCatalogCollection,
             request_method='GET',
             name=VIEW_COURSE_BY_TAG,
             permission=nauth.ACT_READ)
class CourseCatalogByTagView(AbstractAuthenticatedView, BatchingUtilsMixin):
    """
    A view to return an :class:`ICoursesCollection` grouped by tag. The
    tag buckets are sorted by tag name, with hidden tags last.

    XXX: this is inefficient and should not be used, particularly in sites
    with a large number of courses since we iterate through the catalog.

    Note: This API has been exposed externally to clients and should not be altered.

    This view also supports a subpath drilldown into a specific tag
    (e.g. `@@ByTag/tag_name`). `hidden_tags` is an unused param. `bucketSize`,
    if given, will still be respected. The tag drilldown supports paging.

    params:
        bucketSize - (default None) the number of entries per tag to return.
            If we do not find this many entries in a bucket, the bucket will
            return empty.
        hidden_tags - bucket by hidden tags (default True)
    """

    NO_TAG_NAME = '.nti_other'

    @Lazy
    def _params(self):
        return CaseInsensitiveDict(self.request.params)

    @Lazy
    def _tag_drilldown(self):
        # The url is decoded before it is split
        # into subpath (actually before webop PATH_INFO is defined). That means
        # slashes end up giving us multiple subpaths. That will be helpful
        # when we want the tags to nest (google style), but it is a pain right now.
        # grab the tag out of the RAW_URI and then decode it so we get the
        # full tag as one
        if not self.request.subpath:
            return None

        try:
            encoded = self.request.environ['RAW_URI'].split('/')[-1]
            encoded = encoded.split('?')[0]
            # pylint: disable=too-many-function-args
            tag = urllib_parse.unquote(encoded)
            return text_(tag) if tag else None
        except KeyError:
            # No RAW_URI unit test? Use old behaviour
            return self.request.subpath[0]

    @Lazy
    def _bucket_size(self):
        # pylint: disable=no-member
        result =   self._params.get('bucket') \
                or self._params.get('bucketSize') \
                or self._params.get('bucket_size')
        return result and int(result)

    @Lazy
    def _include_hidden_tags(self):
        # pylint: disable=no-member
        # Default True; only available for admins
        result =   self._params.get('hidden_tag') \
                or self._params.get('hidden_tags') \
                or self._params.get('hiddenTags')
        return  not is_false(result) \
            and is_admin_or_content_admin_or_site_admin(self.remoteUser)

    @Lazy
    def _entry_intids(self):
        """
        The LFSet of entry_intids of our context collection.
        """
        return self.context.entry_intids()

    def _tag_sort_key(self, item_tuple):
        # Sort by tag name
        return item_tuple[0].lower()

    def _bucket_sort_key(self, entry):
        return entry.ProviderUniqueID.lower()

    def _get_tagged_entry_intids(self):
        """
        Return the set of tagged entry intids for the given tag.
        """
        return get_entry_intids_for_tag(self._tag_drilldown)

    def _get_non_tagged_entry_intids(self):
        """
        Return the set of non-tagged entry intids.
        """
        exclude_non_public = not is_admin_or_site_admin(self.remoteUser)
        return get_non_tagged_entry_intids(exclude_non_public=exclude_non_public)

    def _get_entry_intids(self):
        """
        Returns a sorted set of entry intids.
        """
        if self._tag_drilldown == self.NO_TAG_NAME:
            # Special case, fetch all un-tagged entries
            entry_intids = self._get_non_tagged_entry_intids()
        else:
            entry_intids = self._get_tagged_entry_intids()
        # Now available for us
        intids = component.getUtility(IIntIds)
        entry_intids = intids.family.IF.intersection(entry_intids,
                                                     self._entry_intids)
        courses_catalog = get_courses_catalog()
        result_intids = courses_catalog[IX_ENTRY_PUID_SORT].sort(entry_intids)
        return ResultSet(result_intids, intids), len(entry_intids)

    def _get_entries(self):
        return self.context.container or ()

    @Lazy
    def _tag_buckets(self):
        """
        Build buckets of tag_name -> entries.
        """
        result = defaultdict(list)
        # XXX: This path is inefficient and should not be used.
        for entry in self._get_entries():
            entry_tags = entry.tags
            if not self._include_hidden_tags:
                entry_tags = filter_hidden_tags(entry_tags)
            if entry_tags:
                for entry_tag in entry_tags:
                    result[entry_tag].append(entry)
            else:
                result[self.NO_TAG_NAME].append(entry)
        return result

    @Lazy
    def _sorted_tag_buckets(self):
        result = list()
        # pylint: disable=no-member
        sorted_entry_tuples = sorted(self._tag_buckets.items(),
                                     key=self._tag_sort_key)
        # Now sort/reduce our bucket size.
        for tag, entries in sorted_entry_tuples:
            tag_dict = dict()
            sorted_entries = sorted(entries,
                                    key=self._bucket_sort_key)
            tag_entry_count = len(sorted_entries)
            if not tag_entry_count:
                # Skip any empty buckets.
                continue
            if self._bucket_size:
                # Bucket size acts as a min requested
                if tag_entry_count >= self._bucket_size:
                    # pylint: disable=invalid-slice-index
                    sorted_entries = sorted_entries[:self._bucket_size]
                else:
                    # Otherwise, we exclude these items.
                    sorted_entries = ()

            tag_dict['Name'] = tag
            tag_dict[ITEMS] = sorted_entries
            tag_dict[TOTAL] = tag_entry_count
            tag_dict[ITEM_COUNT] = len(sorted_entries)
            result.append(tag_dict)
        return result

    def __call__(self):
        result = LocatedExternalDict()
        if self._tag_drilldown:
            entry_intids, course_count = self._get_entry_intids()
            result['Name'] = self._tag_drilldown
            result[ITEMS] = entry_intids
            result[TOTAL] = course_count
            self._batch_items_iterable(result, result[ITEMS])
        else:
            buckets = self._sorted_tag_buckets
            result[ITEMS] = buckets
            result[TOTAL] = len(buckets)
        return result
