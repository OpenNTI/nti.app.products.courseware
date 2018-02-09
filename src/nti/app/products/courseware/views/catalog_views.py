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

from datetime import datetime
from six.moves import urllib_parse
from collections import defaultdict

from requests.structures import CaseInsensitiveDict

from zope import component
from zope import interface

from zope.authentication.interfaces import IUnauthenticatedPrincipal

from zope.cachedescriptors.property import Lazy

from zope.security.management import getInteraction

from zope.traversing.interfaces import IPathAdapter

from pyramid import httpexceptions as hexc

from pyramid.interfaces import IRequest

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractView
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.interfaces import ICoursesWorkspace
from nti.app.products.courseware.interfaces import ICoursesCollection
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from nti.app.products.courseware.interfaces import ICoursesCatalogCollection
from nti.app.products.courseware.interfaces import IEnrolledCoursesCollection
from nti.app.products.courseware.interfaces import IAdministeredCoursesCollection

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

from nti.appserver.workspaces import VIEW_CATALOG_POPULAR
from nti.appserver.workspaces import VIEW_CATALOG_FEATURED

from nti.appserver.workspaces.interfaces import IUserService
from nti.appserver.workspaces.interfaces import IContainerCollection

from nti.base._compat import text_

from nti.common.string import is_false

from nti.contenttypes.courses.interfaces import ES_PUBLIC

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import InstructorEnrolledException
from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntryFilterUtility

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import filter_hidden_tags
from nti.contenttypes.courses.utils import get_courses_for_tag
from nti.contenttypes.courses.utils import get_course_hierarchy
from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin_or_content_admin
from nti.dataserver.authorization import is_admin_or_content_admin_or_site_admin

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserverFolder

from nti.datastructures.datastructures import LastModifiedCopyingUserList

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields

from nti.traversal import traversal

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

    @Lazy
    def entries_and_records(self):
        result = list()
        for record in self.context.container or ():
            entry = self._get_entry_for_record(record)
            if entry is not None:
                result.append((entry, record))
        return result

    @Lazy
    def sorted_entries_and_records(self):
        # Sort secondary key first, ascending alpha
        result = sorted(self.entries_and_records, key=self._secondary_sort_key)
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
                  if self._is_entry_current(x[0])]
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
        result[ITEMS] = items = self._get_items()
        result[ITEM_COUNT] = len(items)
        result[TOTAL] = len(self.entries_and_records)
        return result


class _AbstractWindowedCoursesView(_AbstractSortingAndFilteringCoursesView):
    """
    Base for fetching courses in a more paged style. Request gives back courses
    that are between the notBefore and notAfter GET params. If neither of these
    params are given return the entire collection.
    """

    def _to_datetime(self, stamp):
        return datetime.utcfromtimestamp(stamp)

    @Lazy
    def _params(self):
        return CaseInsensitiveDict(self.request.params)

    def _get_param(self, param_name):
        # pylint: disable=no-member
        param_val = self._params.get(param_name)
        if param_val is None:
            return None
        try:
            result = float(param_val)
        except ValueError:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Invalid timestamp boundary.'),
                             },
                             None)
        result = self._to_datetime(result)
        return result

    @Lazy
    def not_before(self):
        return self._get_param("notBefore")

    @Lazy
    def not_after(self):
        return self._get_param("notAfter")

    def _is_not_before(self, course):
        return self.not_before is None or self.not_before < course.StartDate

    def _is_not_after(self, course):
        return self.not_after is None or self.not_after > course.StartDate

    def get_paged_records(self, entry_record_tuples):
        """
        Gather all records that fall within our window, defined by the user
        given timestamp boundaries.
        """
        records = []
        if self.not_before is None and self.not_after is None:
            # Return everything if no filter.
            return [x[1] for x in entry_record_tuples]
        # We are iterating from most recent to oldest.
        for entry, record in entry_record_tuples or ():
            if not self._is_not_before(entry):
                break
            if self._is_not_after(entry):
                records.append(record)
        return records

    def _get_items(self):
        records = self.get_paged_records(self.sorted_entries_and_records)
        return records


@view_config(route_name='objects.generic.traversal',
             context=IAdministeredCoursesCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name="WindowedAdministered",
             renderer='rest')
class WindowedFavoriteAdministeredCoursesView(_AbstractWindowedCoursesView):
    """
    Paged Administered Courses View
    """


@view_config(route_name='objects.generic.traversal',
             context=IEnrolledCoursesCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name="WindowedEnrolled",
             renderer='rest')
class WindowedFavoriteEnrolledCoursesView(_AbstractWindowedCoursesView):
    """
    Paged enrolled courses view. If we're paging, we'll want to sort
    by entry start date, not the record enrollment date.
    """


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


@view_config(route_name='objects.generic.traversal',
             context=ICourseInstanceEnrollment,
             request_method='DELETE',
             permission=nauth.ACT_DELETE,
             renderer='rest')
class drop_course_view(AbstractAuthenticatedView):
    """
    Dropping a course consists of DELETEing its appearance
    in your enrolled courses view.

    For this to work, it requires that the IEnrolledCoursesCollection
    is not itself traverseable to children.
    """

    def __call__(self):
        course_instance = self.request.context.CourseInstance
        catalog_entry = ICourseCatalogEntry(course_instance)
        enrollments = get_enrollments(course_instance, self.request)
        enrollments.drop(self.remoteUser)
        logger.info("User %s has dropped from course %s",
                    self.remoteUser, catalog_entry.ntiid)
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


@view_config(name="WindowedAllCourses")
@view_config(name="WindowedAllCatalogEntries")
@view_defaults(route_name='objects.generic.traversal',
               context=IContainerCollection,
               request_method='GET',
               permission=nauth.ACT_READ,
               renderer='rest')
class WindowedAllCatalogEntriesView(_AbstractWindowedCoursesView):
    """
    Paged AllCourses view
    """

    def _get_entry_for_record(self, record):
        entry = ICourseCatalogEntry(record, None)
        return entry


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
        # up aggresively.
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
        """
        return self._is_admin \
            or is_course_instructor_or_editor(course, self.remoteUser) \
            or is_enrolled(course, self.remoteUser)

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

    def _include_filter(self, entry):
        """
        Subclasses may use this to filter courses.
        """
        raise NotImplementedError()

    @Lazy
    def filtered_entries(self):
        return [x for x in self.entries_and_records if self._include_filter(x[0])]

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
        result[TOTAL] = len(self.entries_and_records)
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

    DEFAULT_RESULT_COUNT = 3
    MAXIMUM_RESULT_COUNT = 5

    @Lazy
    def minimum_popular_count(self):
        return self.requested_count or self.DEFAULT_RESULT_COUNT

    def _include_filter(self, entry):
        return self._is_entry_current(entry) \
            or self._is_entry_upcoming(entry)

    def _sort_key(self, entry_tuple):
        entry = entry_tuple[0]
        course = ICourseInstance(entry, None)
        enrollment_count = None
        if course is not None:
            # pylint: disable=too-many-function-args
            enrollment_count = ICourseEnrollments(course).count_enrollments()
        return (enrollment_count is not None, enrollment_count)

    def should_return_popular_entries(self):
        """
        We only return if our collection is twice the size of the requested
        popular item count (defaulting to 3).
        """
        return len(self.context.container) >= 2 * self.minimum_popular_count

    def _raise_not_found(self):
        raise_json_error(self.request,
                         hexc.HTTPNotFound,
                         {
                             'message': _(u"There are no popular courses."),
                             'code': 'NoPopularCoursesFoundError',
                         },
                         None)

    def _get_items(self):
        result = super(PopularCoursesView, self)._get_items()
        return_count = self.requested_count
        unused_batch_size, batch_start = self._get_batch_size_start()
        if not return_count and not batch_start:
            # If not a requested count or batching, bound between 3 and 5
            # by default.
            item_count = len(self.context.container)
            half_item_count = item_count // 2
            return_count = min(half_item_count, self.MAXIMUM_RESULT_COUNT)
            return_count = max(return_count, self.DEFAULT_RESULT_COUNT)
        if not result:
            self._raise_not_found()
        if return_count:
            result = result[:return_count]
        return result

    def __call__(self):
        if not self.should_return_popular_entries():
            self._raise_not_found()
        result = super(PopularCoursesView, self).__call__()
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

    def _include_filter(self, entry):
        return self._is_entry_upcoming(entry)

    def should_return_featured_entries(self):
        """
        We only return if our collection is twice the size of the requested
        featured item count (defaulting to 3).
        """
        return len(self.context.container) >= 2 * self.minimum_featured_count

    def _raise_not_found(self):
        raise_json_error(self.request,
                         hexc.HTTPNotFound,
                         {
                             'message': _(u"There are no featured courses."),
                             'code': 'NoFeaturedCoursesFoundError',
                         },
                         None)

    def _get_items(self):
        result = super(FeaturedCoursesView, self)._get_items()
        return_count = self.requested_count
        unused_batch_size, batch_start = self._get_batch_size_start()
        if not return_count and not batch_start:
            # If not a requested count and not a batch, bound between 1 and 3.
            item_count = len(self.context.container)
            half_item_count = item_count // 2
            return_count = min(half_item_count, self.DEFAULT_RESULT_COUNT)
            return_count = max(return_count, self.MINIMUM_RESULT_COUNT)
        if not result:
            self._raise_not_found()
        if return_count:
            result = result[:return_count]
        return result

    def __call__(self):
        if not self.should_return_featured_entries():
            self._raise_not_found()
        result = super(FeaturedCoursesView, self).__call__()
        return result


@view_config(context=ICoursesCollection)
@view_config(context=ICoursesCatalogCollection)
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
        filter - (optional) include a catalog entry containing this str

    """

    #: To maintain BWC; disable paging by default.
    _DEFAULT_BATCH_SIZE = None
    _DEFAULT_BATCH_START = None

    DESC_SORT_ORDER = False

    def _include_filter(self, unused_entry):  # pylint: disable=arguments-differ
        pass

    @Lazy
    def _params(self):
        values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    @Lazy
    def filter_str(self):
        # pylint: disable=no-member
        result = self._params.get('filter')
        return result and result.lower()

    @Lazy
    def filtered_entries(self):
        # pylint: disable=not-an-iterable
        filter_utility = component.getUtility(ICourseCatalogEntryFilterUtility)
        entries = (x[0] for x in self.entries_and_records)
        entries = filter_utility.filter_entries(entries, self.filter_str)
        entries = set(entries)
        return [x for x in self.entries_and_records if x[0] in entries]

    def _sort_key(self, entry_tuple):
        entry = entry_tuple[0]
        title = entry.title and entry.title.lower()
        start_date = entry.StartDate
        return (not title, title, start_date is not None, start_date)

    def __call__(self):
        new_items = self._get_items()
        # Toggle our container and externalize for batching.
        new_container = LastModifiedCopyingUserList()
        new_container.extend(new_items)
        self.context.container = new_container
        result = to_external_object(self.context)
        self._batch_items_iterable(result, result[ITEMS])
        result[TOTAL] = len(self.context)
        result['FilteredTotalItemCount'] = len(new_items)
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
    """

    DESC_SORT_ORDER = True

    def _sort_key(self, entry_tuple):
        enrollment = entry_tuple[1]
        return enrollment.createdTime

    def _get_entry_for_record(self, record):
        course = record.CourseInstance
        entry = ICourseCatalogEntry(course, None)
        return entry


@view_config(route_name='objects.generic.traversal',
             context=ICoursesCollection,
             request_method='GET',
             name=VIEW_COURSE_BY_TAG,
             permission=nauth.ACT_READ)
class CourseCatalogByTagView(AbstractAuthenticatedView, BatchingUtilsMixin):
    """
    A view to return an :class:`ICoursesCollection` grouped by tag.

    The entries within a bucket are sorted by enrollment count (desc).

    The tag buckets are sorted by tag name, with hidden tags last.

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

    def _tag_sort_key(self, item_tuple):
        # Sort by tag name
        return item_tuple[0].lower()

    def _bucket_sort_key(self, entry):
        course = ICourseInstance(entry, None)
        enrollment_count = None
        if course is not None:
            # pylint: disable=too-many-function-args
            enrollment_count = ICourseEnrollments(course).count_enrollments()
        return (enrollment_count is not None, enrollment_count)

    def _get_tagged_entries(self):
        """
        Return the set of tagged entries for the given tag.
        """
        tagged_courses = get_courses_for_tag(self._tag_drilldown)
        tagged_entries = {ICourseCatalogEntry(x, None)
                          for x in tagged_courses}
        tagged_entries.discard(None)
        return tagged_entries

    def _get_entries(self):
        entries = self.context.container or ()
        if self._tag_drilldown:
            if self._tag_drilldown == self.NO_TAG_NAME:
                # Special case, fetch all un-tagged entries
                entries = [x for x in entries if not x.tags]
            else:
                tagged_entries = set(self._get_tagged_entries())
                entries = set(entries) & tagged_entries
        return entries

    @Lazy
    def _tag_buckets(self):
        """
        Build buckets of tag_name -> entries.
        """
        result = defaultdict(list)
        entries = self._get_entries()
        if self._tag_drilldown:
            # If a specific tag is requested, this is easy.
            result[self._tag_drilldown] = entries
        else:
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
                                    key=self._bucket_sort_key,
                                    reverse=True)
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
        buckets = self._sorted_tag_buckets
        if self._tag_drilldown and buckets:
            # Get our first dict if we have info.
            # pylint: disable=unsubscriptable-object
            result.update(buckets[0])
            self._batch_items_iterable(result, result[ITEMS])
        elif self._tag_drilldown:
            # Empty requested bucket
            result['Name'] = self._tag_drilldown
            result[ITEMS] = ()
            result[ITEM_COUNT] = result[TOTAL] = 0
        else:
            result[ITEMS] = buckets
            result[TOTAL] = len(buckets)
        return result
