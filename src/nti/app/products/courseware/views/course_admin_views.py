#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views related to administration of courses.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from . import MessageFactory as _

import csv
from io import BytesIO

from zope import component
from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.security.management import endInteraction, restoreInteraction

from pyramid.view import view_config
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.internalization import read_body_as_external_object
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.interfaces import IUserService

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY
from nti.contenttypes.courses.enrollment import migrate_enrollments_from_course_to_course

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserverFolder

from nti.dataserver import authorization as nauth

from nti.dataserver.users import User
from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.interfaces import LocatedExternalDict 
from nti.externalization.interfaces import StandardExternalFields 

from nti.utils.maps import CaseInsensitiveDict

from ..utils import drop_any_other_enrollments

from ..interfaces import ICoursesWorkspace

from .catalog_views import get_enrollments
from .catalog_views import do_course_enrollment

ITEMS = StandardExternalFields.ITEMS

## HELPER admin views

def _parse_user(values):
	username = values.get('username') or values.get('user')
	if not username:
		raise hexc.HTTPUnprocessableEntity(detail=_('No username'))

	user = User.get_user(username)
	if not user or not IUser.providedBy(user):
		raise hexc.HTTPNotFound(detail=_('User not found'))
	
	return username, user
		
class AbstractCourseEnrollView(AbstractAuthenticatedView,
							   ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		values = super(AbstractCourseEnrollView, self).readInput(value=value)
		result = CaseInsensitiveDict(values)
		return result

	def parseCommon(self, values):
		# get / validate user
		_, user = _parse_user(values)

		# get validate course entry
		ntiid = values.get('ntiid') or \
				values.get('EntryNTIID') or \
				values.get('CourseEntryNIID') or \
				values.get('ProviderUniqueID')
		if not ntiid:
			raise hexc.HTTPUnprocessableEntity(detail=_('No course entry identifier'))

		# get catalog entry
		try:
			catalog = component.getUtility(ICourseCatalog)
			catalog_entry = catalog.getCatalogEntry(ntiid)
		except LookupError:
			raise hexc.HTTPNotFound(detail=_('Catalog not found'))
		except KeyError:
			raise hexc.HTTPNotFound(detail=_('Course not found'))

		return (catalog_entry, user)

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='POST',
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN,
			 name='AdminUserCourseEnroll')
class AdminUserCourseEnrollView(AbstractCourseEnrollView):

	def __call__(self):
		values = self.readInput()
		catalog_entry, user = self.parseCommon(values)
		scope = values.get('scope', 'Public')
		if not scope or scope not in ENROLLMENT_SCOPE_VOCABULARY.by_token.keys():
			raise hexc.HTTPUnprocessableEntity(detail=_('Invalid scope'))

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
										  request=self.request)
		finally:
			restoreInteraction()
		return result

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='POST',
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN,
			 name='AdminUserCourseDrop')
class AdminUserCourseDropView(AbstractCourseEnrollView):

	def __call__(self):
		values = self.readInput()
		catalog_entry, user = self.parseCommon(values)
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
			 request_method='GET',
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN,
			 name='AdminUserCourseEnrollments')
class AdminUserCourseEnrollmentsView(AbstractAuthenticatedView):

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
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN,
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
			raise hexc.HTTPNotFound(detail=_('Catalog not found'))
			
		params = {}
		values = self.readInput()
		for name, alias in (('source', 'source'), ('target', 'dest')):
			ntiid = values.get(name) or values.get(alias)
			if not ntiid:
				msg = 'No %s course entry specified' % name
				raise hexc.HTTPUnprocessableEntity(detail=_(msg))
			try:
				entry = catalog.getCatalogEntry(ntiid)
				params[name] = entry
			except KeyError:
				raise hexc.HTTPUnprocessableEntity(detail=_('Course not found'))
			
		if params['source'] == params['target']:
			raise hexc.HTTPUnprocessableEntity(detail=_('Source and target course are the same'))
		
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
			 context=IDataserverFolder,
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
					csv_writer.writerow(row_data)

		response = self.request.response
		response.body = bio.getvalue()
		response.content_disposition = b'attachment; filename="CourseRoles.csv"'
		return response
