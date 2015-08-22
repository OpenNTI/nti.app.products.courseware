#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views related to administration of courses.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import csv
import six
import time
from io import BytesIO
from datetime import datetime

import isodate

from zope import component

from zope.intid import IIntIds

from zope.security.interfaces import IPrincipal
from zope.security.management import endInteraction, restoreInteraction

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.internalization import read_body_as_external_object
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.workspaces.interfaces import IUserService

from nti.common.property import Lazy
from nti.common.maps import CaseInsensitiveDict

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_USERNAME
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.contenttypes.courses import get_enrollment_catalog
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord
from nti.contenttypes.courses.enrollment import migrate_enrollments_from_course_to_course

from nti.dataserver.interfaces import IUser

from nti.dataserver import authorization as nauth

from nti.dataserver.users import User
from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.site import get_component_hierarchy_names

from ..utils import drop_any_other_enrollments
from ..utils import is_instructor_in_hierarchy

from ..interfaces import ICoursesWorkspace

from ..workspaces import CourseInstanceAdministrativeRole

from .catalog_views import get_enrollments
from .catalog_views import do_course_enrollment

from . import CourseAdminPathAdapter

ITEMS = StandardExternalFields.ITEMS

# HELPER admin views

def _tx_string(s):
	if s and isinstance(s, unicode):
		s = s.encode('utf-8')
	return s

def _parse_user(values):
	username = values.get('username') or values.get('user')
	if not username:
		raise hexc.HTTPUnprocessableEntity(detail='No username')

	user = User.get_user(username)
	if not user or not IUser.providedBy(user):
		raise hexc.HTTPUnprocessableEntity(detail='User not found')

	return username, user

def _parse_courses(values):
	# get validate course entry
	ntiids = values.get('ntiid') or values.get('ntiids') or \
			 values.get('entry') or values.get('entries') or \
			 values.get('course') or values.get('courses') 
	if not ntiids:
		raise hexc.HTTPUnprocessableEntity(detail='No course entry identifier')

	if isinstance(ntiids, six.string_types):
		ntiids = ntiids.split()
		
	result = []
	for ntiid in ntiids:
		context = find_object_with_ntiid(ntiid)
		if context is None:
			try:
				catalog = component.getUtility(ICourseCatalog)
				context = catalog.getCatalogEntry(ntiid)
			except LookupError:
				raise hexc.HTTPUnprocessableEntity(detail='Catalog not found')
			except KeyError:
				context = None
		else:
			context = ICourseCatalogEntry(context, None)

		if context is not None:
			result.append(context)
	return result

def _parse_course(values):
	result = _parse_courses(values)
	if not result:
		raise hexc.HTTPUnprocessableEntity(detail='Course not found')
	return result[0]

class AbstractCourseEnrollView(AbstractAuthenticatedView,
							   ModeledContentUploadRequestUtilsMixin):

	def readInput(self):
		if self.request.body:
			values = read_body_as_external_object(self.request)
		else:
			values = self.request.params
		result = CaseInsensitiveDict(values)
		return result

	def parseCommon(self, values):
		_, user = _parse_user(values)
		catalog_entry = _parse_course(values)
		return (catalog_entry, user)

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
		catalog_entry, user = self.parseCommon(values)
		scope = values.get('scope', 'Public')
		if not scope or scope not in ENROLLMENT_SCOPE_VOCABULARY.by_token.keys():
			raise hexc.HTTPUnprocessableEntity(detail='Invalid scope')

		if is_instructor_in_hierarchy(catalog_entry, user):
			msg = 'User is an instructor in course hierarchy'
			raise hexc.HTTPUnprocessableEntity(detail=msg)

		# Make sure we don't have any interaction.
		endInteraction()
		try:
			drop_any_other_enrollments(catalog_entry, user)
			service = IUserService(user)
			workspace = ICoursesWorkspace(service)
			parent = workspace['EnrolledCourses']

			logger.info("Enrolling %s in %s", user, catalog_entry.ntiid)
			result = do_course_enrollment(catalog_entry, user, scope,
										  parent=parent,
										  safe=True,
										  request=self.request)
		finally:
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
		catalog_entry, user = self.parseCommon(values)

		# Make sure we don't have any interaction.
		endInteraction()
		try:
			course_instance = ICourseInstance(catalog_entry)
			enrollments = get_enrollments(course_instance, self.request)
			if enrollments.drop(user):
				logger.info("%s drop from %s", user, catalog_entry.ntiid)
		finally:
			restoreInteraction()

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
		catalog_entry = _parse_course(values)

		# Make sure we don't have any interaction.
		endInteraction()
		try:
			course_instance = ICourseInstance(catalog_entry)
			manager = ICourseEnrollmentManager(course_instance)
			dropped_records = manager.drop_all()
			items = result[ITEMS] = []
			for record in dropped_records:
				principal = IPrincipal(record.Principal, None)
				username = principal.id if principal is not None else 'deleted'
				items.append({'Username': username, 'Scope': record.Scope})
			logger.info("Dropped %d enrollment records of %s",
						len(dropped_records), catalog_entry.ntiid)
		finally:
			restoreInteraction()
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
		_, user = _parse_user(params)
		result = LocatedExternalDict()
		items = result[ITEMS] = []

		now = time.time()
		catalog = get_enrollment_catalog()
		intids = component.getUtility(IIntIds)
		site_names = get_component_hierarchy_names()
		query = {
			IX_SITE:{'any_of': site_names},
			IX_USERNAME:{'any_of':(user.username,)}
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

		result['Total'] = len(items)
		result['TimeElapsed'] = time.time() - now
		return result

@view_config(name='CourseEnrollmentMigrator')
@view_config(name='Course_enrollment_migrator')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=CourseAdminPathAdapter,
			   permission=nauth.ACT_NTI_ADMIN)
class CourseEnrollmentMigrationView(AbstractAuthenticatedView):
	"""
	Migrates the enrollments from one course to antother

	Call this as a GET request for dry-run processing. POST to it
	to do it for real.
	"""

	def readInput(self):
		if self.request.body:
			values = read_body_as_external_object(self.request)
		else:
			values = self.request.params
		result = CaseInsensitiveDict(values)
		return result

	def _do_call(self):
		try:
			catalog = component.getUtility(ICourseCatalog)
		except LookupError:
			raise hexc.HTTPNotFound(detail='Catalog not found')

		params = {}
		values = self.readInput()
		for name, alias in (('source', 'source'), ('target', 'dest')):
			ntiid = values.get(name) or values.get(alias)
			if not ntiid:
				msg = 'No %s course entry specified' % name
				raise hexc.HTTPUnprocessableEntity(detail=msg)
			try:
				entry = catalog.getCatalogEntry(ntiid)
				params[name] = entry
			except KeyError:
				raise hexc.HTTPUnprocessableEntity(detail='Course not found')

		if params['source'] == params['target']:
			msg = 'Source and target course are the same'
			raise hexc.HTTPUnprocessableEntity(detail=msg)

		result = LocatedExternalDict()
		users_moved = result['Users'] = list()
		result['Source'] = params['source'].ntiid
		result['Target'] = params['target'].ntiid
		source = ICourseInstance(params['source'])
		target = ICourseInstance(params['target'])
		total = migrate_enrollments_from_course_to_course(source, target, verbose=True,
														  result=users_moved)
		result['Total'] = total
		return result

	def __call__(self):
		# Make sure we don't send enrollment email, etc, during this process
		# by not having any interaction.
		endInteraction()
		try:
			return self._do_call()
		finally:
			restoreInteraction()

# REPORT admin views

@view_config(name='CourseRoles')
@view_config(name='course_roles')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=CourseAdminPathAdapter,
			   request_method='GET',
			   permission=nauth.ACT_MODERATE)
class CourseRolesView(AbstractAuthenticatedView,
					  ModeledContentUploadRequestUtilsMixin):

	def __call__(self):
		catalog = component.getUtility(ICourseCatalog)

		bio = BytesIO()
		csv_writer = csv.writer(bio)

		# header
		header = ['Course', 'SubInstance', 'Role', 'Setting', 'User', 'Email']
		csv_writer.writerow(header)

		for catalog_entry in catalog.iterCatalogEntries():
			course = ICourseInstance(catalog_entry)

			if ICourseSubInstance.providedBy(course):
				sub_name = course.__name__
				course_name = course.__parent__.__parent__.__name__
			else:
				course_name = course.__name__
				sub_name = ''

			roles = IPrincipalRoleMap(course, None)
			if roles is not None:
				for role_id, prin_id, setting in roles.getPrincipalsAndRoles():
					user = User.get_user(prin_id)
					profile = IUserProfile(user, None)
					email = getattr(profile, 'email', None)
					# write data
					row_data = [course_name, sub_name, role_id, setting, prin_id, email]
					csv_writer.writerow([_tx_string(x) for x in row_data])

		response = self.request.response
		response.body = bio.getvalue()
		response.content_disposition = b'attachment; filename="CourseRoles.csv"'
		return response

from nti.dataserver.interfaces import IUsernameSubstitutionPolicy

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
		result = substituter.replace(username) or username
		return result

	def __call__(self):
		params = CaseInsensitiveDict(self.request.params)
		context = _parse_course(params)
		course = ICourseInstance(context, None)
		if course is None:
			raise hexc.HTTPUnprocessableEntity(detail='Course not found')

		bio = BytesIO()
		csv_writer = csv.writer(bio)

		# header
		header = ['username', 'realname', 'email', 'scope', 'created']
		csv_writer.writerow(header)

		for record in ICourseEnrollments(course).iter_enrollments():
			scope = record.Scope

			user = principal = IPrincipal(record.Principal, None)
			username = principal.id if principal is not None else 'deleted'

			created = getattr(record, 'createdTime', None) or record.lastModified
			created = isodate.datetime_isoformat(datetime.fromtimestamp(created or 0))

			if principal is not None:
				user = User.get_user(username)
			profile = IUserProfile(user, None)
			email = getattr(profile, 'email', None)
			realname = getattr(profile, 'realname', None)

			row_data = [self._replace(username), realname, email, scope, created]
			csv_writer.writerow([_tx_string(x) for x in row_data])

		response = self.request.response
		response.body = bio.getvalue()
		response.content_disposition = b'attachment; filename="enrollments.csv"'
		return response

import collections
from cStringIO import StringIO

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalList

from ..interfaces import ICourseInstanceEnrollment

@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   context=IDataserverFolder,
			   permission=nauth.ACT_NTI_ADMIN,
			   name='AllEnrollments.csv')
class AllCourseEnrollmentRosterDownloadView(AbstractAuthenticatedView):
	"""
	Provides a downloadable table of all the enrollments
	present in the system. The table has columns
	for username, email address, and enrolled courses.
	"""

	def _iter_catalog_entries(self):
		"""
		Returns something that can be used to iterate across the
		:class:`.ICourseCatalogEntry` objects of interest.
		"""
		return component.getUtility(ICourseCatalog).iterCatalogEntries()

	def _make_enrollment_predicate(self):
		status_filter = self.request.GET.get('LegacyEnrollmentStatus')
		if not status_filter:
			return lambda course, user: True

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
		enrollment_predicate = self._make_enrollment_predicate()

		user_to_coursenames = collections.defaultdict(set)

		for catalog_entry in self._iter_catalog_entries():
			course_name = catalog_entry.Title

			course = ICourseInstance(catalog_entry)

			enrollments = ICourseEnrollments(course)

			for record in enrollments.iter_enrollments():
				user = IUser(record, None)
				if user is None:
					logger.error("Could not adapt record %r to user. " +
								 "Deleted User? Bad Instance?", record)
					continue
				if enrollment_predicate(course, record):
					user_to_coursenames[user].add(course_name)

		rows = LocatedExternalList()
		rows.__name__ = self.request.view_name
		rows.__parent__ = self.request.context
		def _e(s):
			return s.encode('utf-8') if s else s
		for user, enrolled_course_names in user_to_coursenames.items():
			profile = IUserProfile(user)
			row = [user.username,
				   _e(getattr(profile, 'alias', None)),
				   _e(getattr(profile, 'realname', None)),
				   _e(getattr(profile, 'email', None)),
				   ','.join(sorted(list(enrolled_course_names)))]
			rows.append(row)

		# Convert to CSV
		# In the future, we might switch based on the accept header
		# and provide it as json alternately
		buf = StringIO()
		writer = csv.writer(buf)
		writer.writerows(rows)

		self.request.response.body = buf.getvalue()
		self.request.response.content_disposition = b'attachment; filename="enrollments.csv"'

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
		try:
			return (ICourseCatalogEntry(self.request.context),)
		except TypeError:
			# A course instance that's no longer in the catalog
			raise hexc.HTTPNotFound("Course instance not in catalog")

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

@view_config(name='discussions')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   context=ICourseInstance,
			   permission=nauth.ACT_NTI_ADMIN)
class CourseDiscussionsView(AbstractAuthenticatedView):

	def _course(self):
		return self.request.Context

	def __call__(self):
		result = LocatedExternalDict()
		items = result[ITEMS] = {}
		discussions = ICourseDiscussions(self._course(), None) or {}
		for name, discussion in discussions.items():
			name = discussion.id or name
			items[name] = discussion
		return result

@view_config(name='discussions')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   context=ICourseCatalogEntry,
			   permission=nauth.ACT_NTI_ADMIN)
class CourseCatalogEntryDiscussionsView(CourseDiscussionsView):

	def _course(self):
		return ICourseInstance(self.request.context, None)

from nti.contenttypes.courses.interfaces import ICourseInstancePublicScopedForum
from nti.contenttypes.courses.interfaces import ICourseInstanceForCreditScopedForum

from ..discussions import get_topic_key

@view_config(name='DropCourseDiscussions')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   context=CourseAdminPathAdapter,
			   permission=nauth.ACT_NTI_ADMIN)
class DropCourseDiscussionsView(AbstractAuthenticatedView,
								ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		values =  ModeledContentUploadRequestUtilsMixin.readInput(self, value=value)
		return CaseInsensitiveDict(values)
	
	def __call__(self):
		values = self.readInput()
		courses = _parse_courses(values)
		if not courses:
			raise hexc.HTTPUnprocessableEntity(detail='Please specify a valid course')
		
		result = LocatedExternalDict()
		items = result[ITEMS] = {}
		for course in courses:
			course = ICourseInstance(course, None)
			entry = ICourseCatalogEntry(course, None)
			if course is None or entry is None:
				continue

			data = items[entry.ntiid] = {}
			course_discs = ICourseDiscussions(course, None) or {}
			course_discs = {get_topic_key(d) for d in course_discs.values()}
			if not course_discs:
				continue

			discussions = course.Discussions
			for forum in discussions.values():
				if 	not ICourseInstancePublicScopedForum.providedBy(forum) and \
					not ICourseInstanceForCreditScopedForum.providedBy(forum):
					continue
				
				for key in course_discs:
					if key in forum:
						del forum[key]
						data.setdefault(forum.__name__, [])
						data[forum.__name__].append(key)
		return result
