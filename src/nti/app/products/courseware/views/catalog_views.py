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

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from collections import defaultdict

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

from nti.dataserver import authorization as nauth

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
def CoursesPathAdapter(context, request):
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
            raise_json_error(
                        self.request,
                        hexc.HTTPNotFound,
                        {
                            u'message': _("There is no course by that name"),
                            u'code': 'NoCourseFoundError',
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
            raise_json_error(
                    self.request,
                    hexc.HTTPUnprocessableEntity,
                    {
                        u'message': str(e) or e.i18n_message,
                        u'code': 'InstructorEnrolledError',
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
            
        # If no paging, grab all records
        result = [x[1] for x in result]
        return result

    def __call__(self):
        result = LocatedExternalDict()
        result[ITEMS] = items = self._get_items()
        result[ITEM_COUNT] = len(items)
        result[TOTAL] = len(self.entries_and_records)
        return result


class _AbstractPagedFavoriteCoursesView(_AbstractFavoriteCoursesView):
    """
    Base for a course fetching view that will page the results.
    The first page (get arg page=1) will return the current and upcoming
    courses along with the most recent month of archived courses. All other pages
    will return months in chronological order of archived courses
    """

    @Lazy
    def page_number(self):
        params = CaseInsensitiveDict(self.request.params)
        try:
            result = int(params.get("page"))
        except (ValueError, TypeError):
            return False
        return result

    def _get_page_dict(self, courses):
        pages = defaultdict(list)
        for course in courses:
            course_year = course.StartDate.date().year
            course_month = course.StartDate.date().month
            pages[str(course_year) + str(course_month)].append(course)
        self.page_count = len(pages.keys())
        return pages

    def get_paged_courses(self, courses):
        pages = self._get_page_dict(courses)
        return pages.values()[self.page_number - 1]

    def _get_items(self):
        """
        Get our result set items, which will include the `current`
        enrollments (if first page) backfilled with the most recent.
        """
        result = self.sorted_current_entries_and_records
        paged = []
        seen_entries = set(x[0] for x in result)
        not_seen = [
            x[0] for x in self.sorted_entries_and_records if x[0] not in seen_entries]
        paged_courses = self.get_paged_courses(not_seen)
        result = result + paged_courses if self.page_number == 1 else paged_courses
        return result

    def __call__(self):
        if not self.page_number:
            return hexc.HTTPBadRequest()
        result = LocatedExternalDict()
        result[ITEMS] = items = self._get_items()
        result[ITEM_COUNT] = len(items)
        result[TOTAL] = len(self.entries_and_records)
        result["PageCount"] = self.page_count
        return result

@view_config(route_name='objects.generic.traversal',
             context=IAdministeredCoursesCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name="PagedAdministered",
             renderer='rest')
class PagedFavoriteAdministeredCoursesView(_AbstractPagedFavoriteCoursesView):
    """
    Paged Administered Courses View
    """

@view_config(route_name='objects.generic.traversal',
             context=IEnrolledCoursesCollection,
             request_method='GET',
             permission=nauth.ACT_READ,
             name="PagedEnrolled",
             renderer='rest')
class PagedFavoriteEnrolledCoursesView(_AbstractPagedFavoriteCoursesView):
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
    is not itself traversable to children.
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

@view_config(name="PagedAllCourses")
@view_config(name="PagedAllCatalogEntries")
@view_defaults(route_name='objects.generic.traversal',
               context=IContainerCollection,
               request_method='GET',
               permission=nauth.ACT_NTI_ADMIN,
               renderer='rest')
class PagedAllCatalogEntriesView(_AbstractPagedFavoriteCoursesView):
    """
    Paged AllCourses view
    """
    
    def __call__(self):
        if not self.page_number:
            return hexc.HTTPBadRequest()
        catalog = component.getUtility(ICourseCatalog)
        result = LocatedExternalDict()
        items = result[ITEMS] = []
        non_current = []
        for e in catalog.iterCatalogEntries():
            ext_obj = to_external_object(e)
            ext_obj['is_non_public'] = INonPublicCourseInstance.providedBy(e)
            if self._is_entry_current(e):
                if self.page_number == 1:
                    items.append(ext_obj)
            else:
                non_current.append(e)
        non_current = self.get_paged_courses(non_current)
        items += non_current
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        result["PageCount"] = self.page_count
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
