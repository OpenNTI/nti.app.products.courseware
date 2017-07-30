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

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from datetime import datetime

from requests.structures import CaseInsensitiveDict

from pyramid import httpexceptions as hexc

from pyramid.interfaces import IRequest

from pyramid.view import view_config
from pyramid.view import view_defaults

from zope import component
from zope import interface

from zope.authentication.interfaces import IUnauthenticatedPrincipal

from zope.cachedescriptors.property import Lazy

from zope.security.management import getInteraction

from zope.traversing.interfaces import IPathAdapter

from nti.app.base.abstract_views import AbstractView
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.interfaces import ICoursesWorkspace
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from nti.app.products.courseware.interfaces import IEnrolledCoursesCollection
from nti.app.products.courseware.interfaces import IAdministeredCoursesCollection

from nti.app.products.courseware.views import MessageFactory as _
from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.app.products.courseware.views import VIEW_COURSE_FAVORITES
from nti.app.products.courseware.views import VIEW_COURSE_CATALOG_FAMILIES
from nti.app.products.courseware.views import VIEW_CURRENT_COURSES
from nti.app.products.courseware.views import VIEW_ARCHIVED_COURSES
from nti.app.products.courseware.views import VIEW_UPCOMING_COURSES

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.appserver.pyramid_authorization import can_create

from nti.appserver.workspaces.interfaces import IUserService
from nti.appserver.workspaces.interfaces import IContainerCollection

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import InstructorEnrolledException
from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import get_course_hierarchy
from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin_or_content_admin

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.traversal import traversal

ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


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
            for k in (NTIID, NTIID.lower(), 'ProviderUniqueID'):
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
                                 'message': _(u"There is no course by that name"),
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


class _AbstractFavoriteCoursesView(AbstractAuthenticatedView):
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
    def minimum_count(self):
        params = CaseInsensitiveDict(self.request.params)
        result = params.get('count') \
              or params.get('limit') \
              or params.get('size')
        return result or self.DEFAULT_RESULT_COUNT

    def _sort_key(self, entry_tuple):
        start_date = entry_tuple[0].StartDate
        return (start_date is not None, start_date)

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
        # Want the most recent first
        result = sorted(self.entries_and_records,
                        key=self._sort_key,
                        reverse=True)
        return result

    def _is_entry_current(self, entry):
        now = self.now
        return (entry.StartDate is None or now > entry.StartDate) \
            and (entry.EndDate is None or now < entry.EndDate)

    @Lazy
    def sorted_current_entries_and_records(self):
        result = [x for x in self.sorted_entries_and_records
                  if self._is_entry_current(x[0])]
        return result

    def _get_items(self):
        """
        Get our result set items, which will include the `current`
        enrollments backfilled with the most recent.
        """
        result = self.sorted_current_entries_and_records
        if len(result) < self.minimum_count:
            # Backfill with most-recent items
            seen_entries = set(x[0] for x in result)
            for entry_tuple in self.sorted_entries_and_records:
                if entry_tuple[0] not in seen_entries:
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


class _AbstractWindowedCoursesView(_AbstractFavoriteCoursesView):
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
    Paged Administered Courses View
    """

    def _sort_key(self, entry_tuple):
        enrollment = entry_tuple[1]
        return enrollment.createdTime


@view_config(route_name='objects.generic.traversal',
             context=IEnrolledCoursesCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_COURSE_FAVORITES,
             renderer='rest')
class FavoriteEnrolledCoursesView(_AbstractFavoriteCoursesView):
    """
    A view into the `favorite` enrolled courses of a user.
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
class FavoriteAdministeredCoursesView(_AbstractFavoriteCoursesView):
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
        items = result[ITEMS] = []
        for e in catalog.iterCatalogEntries():
            ext_obj = to_external_object(e)
            ext_obj['is_non_public'] = INonPublicCourseInstance.providedBy(e)
            items.append(ext_obj)
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


class _AbstractFilteredCourseView(_AbstractFavoriteCoursesView):

    def _get_entry_for_record(self, record):
        entry = ICourseCatalogEntry(record, None)
        return entry

    def _filter(self, entry):
        raise NotImplementedError()

    @Lazy
    def sorted_filtered_entries_and_records(self):
        result = sorted([x for x in self.entries_and_records
                         if self._filter(x[0])],
                        key=self._sort_key,
                        reverse=True)
        return result

    def _get_items(self):
        """
        Get only the upcoming courses
        """
        result = self.sorted_filtered_entries_and_records
        # Now grab the records we want
        result = [x[1] for x in result]
        return result


@view_config(route_name='objects.generic.traversal',
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_UPCOMING_COURSES,
             context=IContainerCollection)
class AllUpcomingCoursesView(_AbstractFilteredCourseView):
    """
    Fetch all upcoming courses in the collection
    """

    def _filter(self, entry):
        now = self.now
        return (entry.StartDate is None or now < entry.StartDate)


@view_config(route_name='objects.generic.traversal',
             context=IContainerCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_ARCHIVED_COURSES)
class AllArchivedCoursesView(_AbstractFilteredCourseView):
    """
    Fetch all archived courses in the collection
    """

    def _filter(self, entry):
        now = self.now
        return (entry.EndDate is None or now > entry.EndDate)


@view_config(route_name='objects.generic.traversal',
             context=IContainerCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name=VIEW_CURRENT_COURSES)
class AllCurrentCoursesView(_AbstractFilteredCourseView):
    """
    Fetch all current courses in the collection
    """

    def _filter(self, entry):
        return self._is_entry_current(entry)
