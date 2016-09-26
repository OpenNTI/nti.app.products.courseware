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

from zope import component
from zope import interface

from zope.traversing.interfaces import IPathAdapter

from pyramid import httpexceptions as hexc

from pyramid.interfaces import IRequest

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.authentication import is_anonymous_identity

from nti.app.base.abstract_views import AbstractView
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.interfaces import ICoursesWorkspace
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from nti.app.products.courseware.interfaces import IEnrolledCoursesCollection

from nti.app.products.courseware.views import MessageFactory as _
from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.appserver.pyramid_authorization import can_create

from nti.appserver.workspaces.interfaces import IUserService

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance

from nti.contenttypes.courses.utils import is_instructor_in_hierarchy

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
			return hexc.HTTPNotFound(_("There is no course by that name"))

		if not can_create(catalog_entry, request=self.request):
			raise hexc.HTTPForbidden()

		if is_instructor_in_hierarchy(catalog_entry, self.remoteUser):
			msg = _("Instructors cannot enroll in a course")
			return hexc.HTTPForbidden(msg)

		enrollment = do_course_enrollment(catalog_entry,
										  self.remoteUser,
										  parent=self.request.context,
										  request=self.request)

		entry = catalog_entry
		if enrollment is not None:
			entry = ICourseCatalogEntry(enrollment.CourseInstance, None)
		entry = catalog_entry if entry is None else entry

		logger.info("User %s has enrolled in course %s",
					self.remoteUser, entry.ntiid)

		return enrollment

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

@view_config(name='AnonymouslyButNotPubliclyAvailableCourseInstances')
@view_config(name='_AnonymouslyButNotPubliclyAvailableCourseInstances')
@view_defaults(name='_AnonymouslyButNotPubliclyAvailableCourseInstances',
			   route_name='objects.generic.traversal',
			   request_method='GET',
			   context=IDataserverFolder,
			   renderer='rest')
class AnonymouslyAvailableCourses(AbstractView):

	def _can_access(self):
		#TODO circle back around and do a more legitimate check here
		#identity = self.request.environ.get('repoze.who.identity')
		#return is_anonymous_identity(identity)
		return False

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
