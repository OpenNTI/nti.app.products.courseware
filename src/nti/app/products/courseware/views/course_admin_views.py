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
import isodate
from io import BytesIO
from datetime import datetime

from zope import component
from zope.security.interfaces import IPrincipal
from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.security.management import endInteraction, restoreInteraction

from pyramid.view import view_config
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.internalization import read_body_as_external_object
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.interfaces import IUserService

from nti.common.property import Lazy
from nti.common.maps import CaseInsensitiveDict

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY
from nti.contenttypes.courses.enrollment import migrate_enrollments_from_course_to_course

from nti.dataserver.interfaces import IUser

from nti.dataserver import authorization as nauth

from nti.dataserver.users import User
from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.interfaces import LocatedExternalDict 
from nti.externalization.interfaces import StandardExternalFields 

from nti.ntiids.ntiids import find_object_with_ntiid

from ..utils import drop_any_other_enrollments

from ..interfaces import ICoursesWorkspace

from .catalog_views import get_enrollments
from .catalog_views import do_course_enrollment

from . import CourseAdminPathAdapter

ITEMS = StandardExternalFields.ITEMS

## HELPER admin views

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
	
def _parse_course(values):
	# get validate course entry
	ntiid = values.get('ntiid') or \
			values.get('entry') or \
			values.get('course')
	if not ntiid:
		raise hexc.HTTPUnprocessableEntity(detail='No course entry identifier')
	
	context = find_object_with_ntiid(ntiid)
	if context is None:
		try:
			catalog = component.getUtility(ICourseCatalog)
			context = catalog.getCatalogEntry(ntiid)
		except LookupError:
			raise hexc.HTTPUnprocessableEntity(detail='Catalog not found')
		except KeyError:
			context = None
		
	if context is None:
		raise hexc.HTTPUnprocessableEntity(detail='Course not found')
	
	return context
	
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

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='POST',
			 context=CourseAdminPathAdapter,
			 permission=nauth.ACT_NTI_ADMIN,
			 name='UserCourseEnroll')
class UserCourseEnrollView(AbstractCourseEnrollView):

	def __call__(self):
		values = self.readInput()
		catalog_entry, user = self.parseCommon(values)
		scope = values.get('scope', 'Public')
		if not scope or scope not in ENROLLMENT_SCOPE_VOCABULARY.by_token.keys():
			raise hexc.HTTPUnprocessableEntity(detail='Invalid scope')

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

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='POST',
			 context=CourseAdminPathAdapter,
			 permission=nauth.ACT_NTI_ADMIN,
			 name='UserCourseDrop')
class UserCourseDropView(AbstractCourseEnrollView):

	def __call__(self):
		values = self.readInput()
		catalog_entry, user = self.parseCommon(values)
		
		# Make sure we don't have any interaction.
		endInteraction()
		try:
			course_instance  = ICourseInstance(catalog_entry)
			enrollments = get_enrollments(course_instance, self.request)
			if enrollments.drop(user):
				logger.info("%s drop from %s", user, catalog_entry.ntiid)
		finally:
			restoreInteraction()

		return hexc.HTTPNoContent()

@view_config(route_name='objects.generic.traversal',
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
			course_instance  = ICourseInstance(catalog_entry)
			manager = ICourseEnrollmentManager(course_instance)
			dropped_records = manager.drop_all()
			items = result[ITEMS] = []
			for record in dropped_records:
				principal = IPrincipal(record.Principal, None)
				username = principal.id if principal is not None else 'deleted'
				items.append( {'Username': username, 'Scope': record.Scope} )
			logger.info("Dropped %d enrollment records of %s",
						len(dropped_records), catalog_entry.ntiid)
		finally:
			restoreInteraction()
		return result

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=CourseAdminPathAdapter,
			 permission=nauth.ACT_NTI_ADMIN,
			 name='UserCourseEnrollments')
class UserCourseEnrollmentsView(AbstractAuthenticatedView):

	def __call__(self):
		params = CaseInsensitiveDict(self.request.params)
		_, user = _parse_user(params)
		result = LocatedExternalDict()
		items = result[ITEMS] = []
		for enrollments in component.subscribers( (user,), IPrincipalEnrollments):
			for enrollment in enrollments.iter_enrollments():
				items.append(enrollment)
		return result
	
@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=CourseAdminPathAdapter,
			 permission=nauth.ACT_NTI_ADMIN,
			 name='CourseEnrollmentMigrator')
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

## REPORT admin views

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=CourseAdminPathAdapter,
			 request_method='GET',
			 permission=nauth.ACT_MODERATE,
			 name='CourseRoles')
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
			course = ICourseInstance( catalog_entry )

			if ICourseSubInstance.providedBy( course ):
				sub_name = course.__name__
				course_name = course.__parent__.__parent__.__name__
			else:
				course_name = course.__name__
				sub_name = ''

			roles = IPrincipalRoleMap( course, None )
			if roles is not None:
				for role_id, prin_id, setting in roles.getPrincipalsAndRoles():
					user = User.get_user( prin_id )
					profile = IUserProfile( user, None )
					email = getattr( profile, 'email', None )
					# write data
					row_data = [course_name, sub_name, role_id, setting, prin_id, email]
					csv_writer.writerow([_tx_string(x) for x in row_data])

		response = self.request.response
		response.body = bio.getvalue()
		response.content_disposition = b'attachment; filename="CourseRoles.csv"'
		return response

from nti.dataserver.interfaces import IUsernameSubstitutionPolicy

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=CourseAdminPathAdapter,
			 permission=nauth.ACT_NTI_ADMIN,
			 name='CourseEnrollments')
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
				user = User.get_user( username )
			profile = IUserProfile( user, None )
			email = getattr( profile, 'email', None )
			realname = getattr( profile, 'realname', None )
					
			row_data = [self._replace(username), realname, email, scope, created]
			csv_writer.writerow([_tx_string(x) for x in row_data])

		response = self.request.response
		response.body = bio.getvalue()
		response.content_disposition = b'attachment; filename="enrollments.csv"'
		return response
