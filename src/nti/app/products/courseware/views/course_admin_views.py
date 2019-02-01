#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views related to administration of courses.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import csv
from io import BytesIO
from datetime import datetime

import isodate

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from requests.structures import CaseInsensitiveDict

import six

from zope import component

from zope.cachedescriptors.property import Lazy

from zope.intid.interfaces import IIntIds

from zope.security.interfaces import IPrincipal

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.completion.adapters import CompletionContextProgressFactory

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware.interfaces import ICoursesWorkspace

from nti.app.products.courseware.utils.migrator import course_enrollment_migrator

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.app.products.courseware.views._utils import _tx_string
from nti.app.products.courseware.views._utils import _parse_user
from nti.app.products.courseware.views._utils import _parse_course

from nti.app.products.courseware.views.catalog_views import get_enrollments
from nti.app.products.courseware.views.catalog_views import do_course_enrollment

from nti.appserver.workspaces.interfaces import IUserService

from nti.common.string import is_true

from nti.contenttypes.courses import get_enrollment_catalog

from nti.contenttypes.courses.administered import CourseInstanceAdministrativeRole

from nti.contenttypes.courses.enrollment import DefaultPrincipalEnrollments
from nti.contenttypes.courses.enrollment import migrate_enrollments_from_course_to_course

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_COURSE
from nti.contenttypes.courses.index import IX_USERNAME

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_NAMES
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import unenroll
from nti.contenttypes.courses.utils import drop_any_other_enrollments
from nti.contenttypes.courses.utils import is_instructor_in_hierarchy
from nti.contenttypes.courses.utils import get_enrollments as get_index_enrollments

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin
from nti.dataserver.authorization import is_site_admin

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IShardLayout
from nti.dataserver.interfaces import ISiteAdminUtility
from nti.dataserver.interfaces import IUsernameSubstitutionPolicy

from nti.dataserver.metadata.index import IX_MIMETYPE
from nti.dataserver.metadata.index import get_metadata_catalog

from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.intid.common import removeIntId

from nti.site.site import getSite
from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


class AbstractCourseEnrollView(AbstractAuthenticatedView,
                               ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        if self.request.body:
            values = super(AbstractCourseEnrollView, self).readInput(value)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    def parseCommon(self, values):
        unused_name, user = _parse_user(values)
        context = _parse_course(values)
        return (context, user)


@view_config(name='UserCourseEnroll')
@view_config(name='user_course_enroll')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               context=CourseAdminPathAdapter,
               permission=nauth.ACT_NTI_ADMIN)
class UserCourseEnrollView(AbstractCourseEnrollView):

    def __call__(self):
        values = self.readInput()
        context, user = self.parseCommon(values)
        scope = values.get('scope', ES_PUBLIC)
        if not scope or scope not in ENROLLMENT_SCOPE_VOCABULARY.by_token:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Invalid scope."),
                             },
                             None)
        if is_instructor_in_hierarchy(context, user):
            msg = _(u'User is an instructor in course hierarchy')
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': msg,
                             },
                             None)
        interaction = is_true(values.get('email') or values.get('interaction'))
        # Make sure we don't have any interaction (enrollment emails etc).
        if not interaction:
            endInteraction()
        try:
            drop_any_other_enrollments(context, user)
            service = IUserService(user)
            workspace = ICoursesWorkspace(service)
            parent = workspace['EnrolledCourses']
            entry = ICourseCatalogEntry(context, None)
            logger.info("Enrolling %s in %s",
                        user, getattr(entry, 'ntiid', None))
            result = do_course_enrollment(context, user, scope,
                                          parent=parent,
                                          safe=True,
                                          request=self.request)
        finally:
            if not interaction:
                restoreInteraction()
        return result


@view_config(name='UserCourseDrop')
@view_config(name='user_course_drop')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               context=CourseAdminPathAdapter,
               permission=nauth.ACT_NTI_ADMIN)
class UserCourseDropView(AbstractCourseEnrollView):

    def __call__(self):
        values = self.readInput()
        context, user = self.parseCommon(values)
        course_instance = ICourseInstance(context)
        enrollments = get_enrollments(course_instance, self.request)
        if enrollments.drop(user):
            entry = ICourseCatalogEntry(context, None)
            logger.info("%s drop from %s", user,
                        getattr(entry, 'ntiid', None))
        return hexc.HTTPNoContent()


@view_config(name='DropAllCourseEnrollments')
@view_config(name='drop_all_course_enrollments')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=CourseAdminPathAdapter,
               permission=nauth.ACT_NTI_ADMIN,
               name='DropAllCourseEnrollments')
class DropAllCourseEnrollmentsView(AbstractCourseEnrollView):

    def __call__(self):
        values = self.readInput()
        result = LocatedExternalDict()
        context = _parse_course(values)
        course_instance = ICourseInstance(context)
        manager = ICourseEnrollmentManager(course_instance)
        # pylint: disable=too-many-function-args
        dropped_records = manager.drop_all()
        items = result[ITEMS] = []
        for record in dropped_records:
            principal = IPrincipal(record.Principal, None)
            username = principal.id if principal is not None else 'deleted'
            items.append({'Username': username, 'Scope': record.Scope})
        entry = ICourseCatalogEntry(context, None)
        logger.info("Dropped %d enrollment records of %s",
                    len(dropped_records), getattr(entry, 'ntiid', None))
        return result


@view_config(name='UserCourseEnrollments')
@view_config(name='user_course_enrollments')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               context=CourseAdminPathAdapter,
               permission=nauth.ACT_NTI_ADMIN)
class UserCourseEnrollmentsView(AbstractAuthenticatedView):

    def __call__(self):
        params = CaseInsensitiveDict(self.request.params)
        unused_name, user = _parse_user(params)
        result = LocatedExternalDict()
        items = result[ITEMS] = []

        catalog = get_enrollment_catalog()
        intids = component.getUtility(IIntIds)
        site_names = get_component_hierarchy_names()
        query = {
            IX_SITE: {'any_of': site_names},
            IX_USERNAME: {'any_of': (user.username,)}
        }
        for uid in catalog.apply(query) or ():
            context = intids.queryObject(uid)
            if ICourseInstanceEnrollmentRecord.providedBy(context):
                items.append(context)
            # check for instructor role
            elif ICourseInstance.providedBy(context):
                roles = IPrincipalRoleMap(context)
                role = 'teaching assistant'
                if roles.getSetting(RID_INSTRUCTOR, user.id) is Allow:
                    role = 'instructor'
                context = CourseInstanceAdministrativeRole(RoleName=role,
                                                           CourseInstance=context)
                items.append(context)

        result[ITEM_COUNT] = result[TOTAL] = len(items)
        return result


@view_config(name='CourseEnrollmentMigrator')
@view_config(name='Course_enrollment_migrator')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=CourseAdminPathAdapter,
               permission=nauth.ACT_NTI_ADMIN)
class CourseEnrollmentMigrationView(AbstractCourseEnrollView):
    """
    Migrates the enrollments from one course to antother

    Call this as a GET request for dry-run processing. POST to it
    to do it for real.
    """

    def _do_call(self):
        params = {}
        values = self.readInput()
        catalog = component.getUtility(ICourseCatalog)
        for name, alias in (('source', 'source'), ('target', 'dest')):
            ntiid = values.get(name) or values.get(alias)
            if not ntiid:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u'No course entry specified.'),
                                 },
                                 None)
            try:
                entry = catalog.getCatalogEntry(ntiid)
                params[name] = entry
            except KeyError:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u'Course not found.'),
                                 },
                                 None)
        if params['source'] == params['target']:
            msg = _(u'Source and target course are the same.')
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': msg,
                             },
                             None)

        result = LocatedExternalDict()
        users_moved = result['Users'] = list()
        result['Source'] = params['source'].ntiid
        result['Target'] = params['target'].ntiid
        source = ICourseInstance(params['source'])
        target = ICourseInstance(params['target'])
        total = migrate_enrollments_from_course_to_course(source, target,
                                                          verbose=True,
                                                          result=users_moved)
        result[ITEM_COUNT] = result[TOTAL] = total
        return result

    def __call__(self):
        # Make sure we don't send enrollment email, etc, during this process
        # by not having any interaction.
        endInteraction()
        try:
            return self._do_call()
        finally:
            restoreInteraction()


@view_config(name='CourseSectionEnrollmentMigrator')
@view_config(name='Course_section_enrollment_migrator')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=CourseAdminPathAdapter,
               permission=nauth.ACT_NTI_ADMIN)
class CourseSectionEnrollmentMigrationView(AbstractAuthenticatedView):
    """
    Migrates the enrollments from a course to its sections

    Call this as a GET request for dry-run processing. POST to it
    to do it for real.
    """

    DEFAULT_SEAT_COUNT = 25

    def readInput(self):
        if self.request.body:
            values = read_body_as_external_object(self.request)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    def _do_call(self):
        values = self.readInput()
        course = _parse_course(values)
        if not course:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Course not found.'),
                             },
                             None)

        scope = values.get('Scope') or ES_PUBLIC
        if scope not in ENROLLMENT_SCOPE_NAMES:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Invalid scope.'),
                             },
                             None)

        seats = values.get('Seats') or values.get('SeatCount') \
             or values.get('MaxSeatCount') or values.get('max_seat_count') \
             or self.DEFAULT_SEAT_COUNT
        try:
            seats = int(seats)
            assert seats > 0
        except Exception:  # pylint: disable=broad-except
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'Invalid max seat count.'),
                             },
                             None)

        seen = set()
        sections = []
        data = values.get('sections') or ()
        if isinstance(data, six.string_types):
            data = data.split()
        for name in data:  # gather sections keep order
            if name not in seen:
                sections.append(name)
            seen.add(name)

        # migrate
        items, total = course_enrollment_migrator(scope=scope,
                                                  verbose=True,
                                                  context=course,
                                                  sections=sections,
                                                  max_seat_count=seats)
        result = LocatedExternalDict()
        m = result[ITEMS] = {}
        for info in items or ():
            m[info.section_name] = info.seat_count
        result[TOTAL] = result[ITEM_COUNT] = total
        return result

    def __call__(self):
        # Make sure we don't send enrollment email, etc, during this process
        # by not having any interaction.
        endInteraction()
        try:
            return self._do_call()
        finally:
            restoreInteraction()


@view_config(name='CourseEnrollments')
@view_config(name='course_enrollments')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               context=CourseAdminPathAdapter,
               permission=nauth.ACT_NTI_ADMIN)
class CourseEnrollmentsView(AbstractAuthenticatedView):

    @Lazy
    def _substituter(self):
        return component.queryUtility(IUsernameSubstitutionPolicy)

    def _replace(self, username):
        substituter = self._substituter
        if substituter is None:
            return username
        # pylint: disable=no-member
        result = substituter.replace(username) or username
        return result

    def __call__(self):
        params = CaseInsensitiveDict(self.request.params)
        context = _parse_course(params)
        course = ICourseInstance(context, None)
        if course is None:
            raise hexc.HTTPUnprocessableEntity(detail='Course not found')
        entry = ICourseCatalogEntry(course)

        bio = BytesIO()
        csv_writer = csv.writer(bio)

        # header
        header = ['username', 'realname', 'email', 'scope', 'created']
        csv_writer.writerow(header)

        catalog = get_enrollment_catalog()
        intids = component.getUtility(IIntIds)
        site_names = get_component_hierarchy_names()
        query = {
            IX_SITE: {'any_of': site_names},
            IX_COURSE: {'any_of': (entry.ntiid,)},
        }
        for uid in catalog.apply(query) or ():
            record = intids.queryObject(uid)
            if not ICourseInstanceEnrollmentRecord.providedBy(record):
                continue
            user = IUser(record, None)
            if user is None:
                continue

            scope = record.Scope
            username = user.username

            created = getattr(record, 'createdTime', None)
            created = created or record.lastModified or 0
            created = datetime.fromtimestamp(created)
            created = isodate.datetime_isoformat(created)

            profile = IUserProfile(user, None)
            email = getattr(profile, 'email', None)
            realname = getattr(profile, 'realname', None)

            row_data = [
                self._replace(username), realname, email, scope, created
            ]
            csv_writer.writerow([_tx_string(x) for x in row_data])

        response = self.request.response
        response.body = bio.getvalue()
        response.content_disposition = 'attachment; filename="enrollments.csv"'
        return response


import collections

from six import StringIO

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalList


@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_NTI_ADMIN,
               name='AllEnrollments.csv')
class AllCourseEnrollmentRosterDownloadView(AbstractAuthenticatedView):
    """
    Provides a downloadable table of all the enrollments
    present in the system. The table has columns
    for username, email address, and enrolled courses.
    """

    @Lazy
    def _substituter(self):
        return component.queryUtility(IUsernameSubstitutionPolicy)

    def _replace(self, username):
        substituter = self._substituter
        if substituter is None:
            return username
        # pylint: disable=no-member
        result = substituter.replace(username) or username
        return result

    def _iter_catalog_entries(self):
        """
        Returns something that can be used to iterate across the
        :class:`.ICourseCatalogEntry` objects of interest.
        """
        return component.getUtility(ICourseCatalog).iterCatalogEntries()

    def _make_enrollment_predicate(self):
        status_filter = self.request.GET.get('LegacyEnrollmentStatus')
        if not status_filter:
            return lambda *unused_args: True

        def func(course, user):
            enrollment = component.getMultiAdapter((course, user),
                                                   ICourseInstanceEnrollment)
            # Let this blow up when this goes away
            return enrollment.LegacyEnrollmentStatus == status_filter

        return func

    def __call__(self):
        # Our approach is to find all the courses,
        # and get the enrollments in each course,
        # accumulating users as we go.
        # (NOTE: This winds up being an O(n^2) approach
        # due to the poor implementation of enrollments
        # for legacy courses.)
        user_to_coursenames = collections.defaultdict(set)
        enrollment_predicate = self._make_enrollment_predicate()
        ntiids = {e.ntiid for e in self._iter_catalog_entries()}

        catalog = get_enrollment_catalog()
        intids = component.getUtility(IIntIds)
        site_names = get_component_hierarchy_names()
        query = {
            IX_COURSE: {'any_of': ntiids},
            IX_SITE: {'any_of': site_names}
        }
        for uid in catalog.apply(query) or ():
            record = intids.queryObject(uid)
            if not ICourseInstanceEnrollmentRecord.providedBy(record):
                continue
            course = record.CourseInstance
            course_name = ICourseCatalogEntry(course).Title

            user = IUser(record, None)
            if user is None:
                continue
            if enrollment_predicate(course, user):
                user_to_coursenames[user].add(course_name)

        rows = LocatedExternalList()
        for user, enrolled_course_names in user_to_coursenames.items():
            profile = IUserProfile(user, None)
            row = [self._replace(user.username),
                   getattr(profile, 'alias', None),
                   getattr(profile, 'realname', None),
                   getattr(profile, 'email', None),
                   ','.join(sorted(list(enrolled_course_names)))]
            rows.append([_tx_string(r) for r in row])

        # Convert to CSV
        # In the future, we might switch based on the accept header
        # and provide it as json alternately
        buf = StringIO()
        writer = csv.writer(buf)

        # header
        header = ['username', 'alias', 'realname', 'email', 'courses']
        writer.writerow(header)

        # rowdata
        writer.writerows(rows)

        self.request.response.body = buf.getvalue()
        self.request.response.content_disposition = 'attachment; filename="enrollments.csv"'
        return self.request.response


@view_config(name='Enrollments.csv')
@view_config(name='enrollments.csv')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               context=ICourseInstance,
               permission=nauth.ACT_NTI_ADMIN)
class CourseEnrollmentsRosterDownloadView(AllCourseEnrollmentRosterDownloadView):
    """
    Provides a downloadable table of the enrollments for
    a single course instance in the same format as :class:`AllCourseEnrollmentRosterDownloadView`.
    """

    def _iter_catalog_entries(self):
        return (ICourseCatalogEntry(self.request.context),)


@view_config(name='Enrollments.csv')
@view_config(name='enrollments.csv')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               context=ICourseCatalogEntry,
               permission=nauth.ACT_NTI_ADMIN)
class CourseCatalogEntryEnrollmentsRosterDownloadView(AllCourseEnrollmentRosterDownloadView):

    def _iter_catalog_entries(self):
        return (self.request.context,)


# Enrollment views


@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_NTI_ADMIN,
               name='FixBrokenEnrollments')
class FixBrokenEnrollmentsView(AbstractAuthenticatedView):
    """
    Fixes broken enrollment records stored in backing db. Param of
    `dry_run` will perform a test run.
    """

    def _get_stored_enrollments(self, user):
        enrollments = DefaultPrincipalEnrollments(user)
        return enrollments.iter_enrollments()

    def _get_enrollments(self, user):
        # We consider the index to be accurate.
        result = get_index_enrollments(user)
        return result

    def __call__(self):
        result = LocatedExternalDict()
        result[ITEMS] = items = dict()
        site_name = getSite().__name__
        count = 0
        params = CaseInsensitiveDict(self.request.params)
        dry_run = is_true(params.get('dry_run') or params.get('test'))

        dataserver = component.getUtility(IDataserver)
        users_folder = IShardLayout(dataserver).users_folder
        # pylint: disable=no-member
        for user in tuple(users_folder.values()):
            if not IUser.providedBy(user):
                continue
            actual = self._get_enrollments(user)
            stored = self._get_stored_enrollments(user)
            # Get extra enrollment records from storage.
            extra = set(stored).difference(actual)
            for extra_record in extra or ():
                username = user.username
                user_list = items.setdefault(username, [])
                if ICourseInstanceEnrollmentRecord.providedBy(extra_record):
                    course = extra_record.CourseInstance
                    entry = ICourseCatalogEntry(course, None)
                    entry_ntiid = entry and entry.ntiid
                    logger.info("[%s] Removing enrollment record for (user=%s) (entry=%s)",
                                site_name, username, entry_ntiid)
                    user_list.append(entry_ntiid)
                    count += 1
                    if not dry_run:
                        unenroll(extra_record, extra_record.Principal)
        result[ITEM_COUNT] = result[TOTAL] = count
        return result


@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_NTI_ADMIN,
               name='RemoveGhostCourseEnrollments')
class RemoveGhostCourseEnrollmentsView(AbstractAuthenticatedView):

    def __call__(self):
        catalog = get_metadata_catalog()
        intids = component.getUtility(IIntIds)
        query = {
            IX_MIMETYPE: {
                'any_of': ('application/vnd.nextthought.courses.defaultcourseinstanceenrollmentrecord',)
            },
        }
        for doc_id in catalog.apply(query) or ():
            obj = intids.queryObject(doc_id)
            if not ICourseInstanceEnrollmentRecord.providedBy(obj):
                continue
            course = find_interface(obj, ICourseInstance, strict=False)
            doc_id = intids.queryId(course)
            if doc_id is None:  # invalid course
                # pylint: disable=too-many-function-args
                manager = ICourseEnrollmentManager(course, None)
                if manager is not None:
                    manager.drop_all()
                if intids.queryId(obj) is not None:
                    removeIntId(obj)
        return hexc.HTTPNoContent()


@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name='CourseCompletionEnrollmentRecords')
class AllCourseCompletionView(AbstractAuthenticatedView):
    """
    Return a data set of all enrollment records that have completed courses
    within the specified date range.
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

    def _iter_catalog_entries(self):
        return component.getUtility(ICourseCatalog).iterCatalogEntries()

    def _include_record(self, progress):
        """
        Return a bool if this progress record falls within our boundaries.
        """
        return  progress.Completed \
            and (   self.not_before is None \
                 or progress.CompletedDate >= self.not_before) \
            and (   self.not_after is None \
                 or progress.CompletedDate < self.not_after)

    @Lazy
    def _is_admin(self):
        return is_admin(self.remoteUser)

    @Lazy
    def _is_site_admin(self):
        return is_site_admin(self.remoteUser)

    def _can_admin_user(self, user):
        # Verify a site admin is administering a user in their site.
        result = True
        if self._is_site_admin:
            admin_utility = component.getUtility(ISiteAdminUtility)
            result = admin_utility.can_administer_user(self.remoteUser, user)
        return result

    def _check_access(self):
        if not self._is_admin and not self._is_site_admin:
            raise hexc.HTTPForbidden()

    def __call__(self):
        self._check_access()
        result = LocatedExternalDict()
        result[ITEMS] = items = dict()
        required_item_providers = None
        course_count = 0
        item_count = 0
        for catalog_entry in self._iter_catalog_entries():
            course = ICourseInstance(catalog_entry, None)
            if course is None:
                continue
            course_result_records = []
            course_enrollments = ICourseEnrollments(course)
            for record in course_enrollments.iter_enrollments():
                user = IUser(record, None)
                if user is None or not self._can_admin_user(user):
                    # Deleted user
                    continue

                progress_factory = CompletionContextProgressFactory(user,
                                                                    course,
                                                                    required_item_providers)
                progress = progress_factory()
                if required_item_providers is None:
                    required_item_providers = progress_factory.required_item_providers

                if self._include_record(progress):
                    course_result_records.append(record)

            if course_result_records:
                items[catalog_entry.ntiid] = course_result_records
                course_count += 1
                item_count += len(course_result_records)
        result['CourseCount'] = course_count
        result['EnrollmentRecordCount'] = result[ITEM_COUNT] = item_count
        return result
