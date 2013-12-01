#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views relating to the course catalog and the courses workspace.

The initial strategy is to use a path adapter named Courses. It will
return something that isn't traversable (in this case, the Courses
workspace). Named views will be registered based on that to implement
the workspace collections.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from zope.traversing.interfaces import IPathAdapter
from nti.dataserver.interfaces import IUser
from pyramid.interfaces import IRequest
from nti.appserver.interfaces import IUserService

from .interfaces import ICoursesWorkspace
from .interfaces import ICourseCatalogEntry
from .interfaces import ICourseCatalog
from .interfaces import IEnrolledCoursesCollection
from .interfaces import ICourseInstanceEnrollment
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from pyramid import httpexceptions as hexc
from pyramid.view import view_config
from nti.appserver.dataserver_pyramid_views import GenericGetView
from nti.appserver._view_utils  import AbstractAuthenticatedView
from nti.appserver._view_utils  import ModeledContentUploadRequestUtilsMixin

from nti.dataserver import authorization as nauth
from nti.dataserver import traversal

from . import VIEW_CONTENTS

@interface.implementer(IPathAdapter)
@component.adapter(IUser, IRequest)
def CoursesPathAdapter(context, request):
	service = IUserService(context)
	workspace = ICoursesWorkspace(service)

	return workspace


@view_config(context=ICourseCatalogEntry)
class CatalogGenericGetView(GenericGetView):
	pass


@view_config( route_name='objects.generic.traversal',
			  context=IEnrolledCoursesCollection,
			  request_method='POST',
			  permission=nauth.ACT_CREATE,
			  renderer='rest' )
class enroll_course_view(AbstractAuthenticatedView,
						 ModeledContentUploadRequestUtilsMixin):
	"""
	POSTing a course identifier to the enrolled courses
	collection enrolls you in it.

	At this writing, anyone is allowed to enroll in any course,
	so the only security on this is that the remote user
	has write permissions to the collection (which implies
	either its his collection or he's an admin).
	"""

	inputClass = object

	def __call__(self):
		catalog = component.getUtility(ICourseCatalog)
		identifier = self.readInput()
		catalog_entry = catalog[identifier]

		course_instance = ICourseInstance(catalog_entry)
		try:
			enrollments = component.getMultiAdapter( (course_instance, self.request),
													 ICourseEnrollmentManager )
		except LookupError:
			enrollments = ICourseEnrollmentManager(course_instance)
		freshly_added = enrollments.enroll( self.remoteUser )
		enrollment = ICourseInstanceEnrollment(course_instance)
		if not enrollment.__parent__:
			enrollment.__parent__ = self.request.context

		if freshly_added:
			self.request.response.status_int = 201 # HTTPCreated
			self.request.response.location = traversal.resource_path(enrollment)
		# Return our enrollment, whether fresh or not
		# TODO: This should probably be a multi-adapter
		return enrollment


@view_config( route_name='objects.generic.traversal',
			  context=ICourseInstanceEnrollment,
			  request_method='DELETE',
			  permission=nauth.ACT_DELETE,
			  renderer='rest' )
class drop_course_view(AbstractAuthenticatedView):
	"""
	Dropping a course consists of DELETEing its appearance
	in your enrolled courses view.

	For this to work, it requires that the IEnrolledCoursesCollection
	is not itself traversable to children.
	"""

	def __call__(self):

		course_instance = self.request.context.CourseInstance
		try:
			enrollments = component.getMultiAdapter( (course_instance, self.request),
													 ICourseEnrollmentManager )
		except LookupError:
			enrollments = ICourseEnrollmentManager(course_instance)
		enrollments.drop( self.remoteUser )

		return hexc.HTTPNoContent()

from nti.externalization.interfaces import ILocatedExternalSequence
from nti.externalization.externalization import to_external_object

@view_config( route_name='objects.generic.traversal',
			  context=ICourseOutline,
			  request_method='GET',
			  permission=nauth.ACT_READ,
			  renderer='rest',
			  name=VIEW_CONTENTS)
class course_outline_contents_view(AbstractAuthenticatedView):
	"""
	The view to get the actual contents of a course outline.

	We flatten all the children directly into the returned nodes at
	this level because the default externalization does not.
	"""
	# XXX: These are small, so we're not too concerned about rendering
	# time. Thus we don't do anything fancy with PreRenderResponseCacheController.
	# We also aren't doing anything user specific yet so we don't
	# do anything with tokens in the URL

	def __call__(self):
		values = self.request.context.values()
		result = ILocatedExternalSequence([])
		def _recur(the_list, the_nodes):
			for node in the_nodes:
				ext_node = to_external_object(node)
				ext_node['contents'] = _recur([], node.values() )
				# Pretty pointless to send these
				ext_node.pop('NTIID', None)
				ext_node.pop('OID', None)

				the_list.append( ext_node )
			return the_list

		_recur(result, values)
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context
		self.request.response.last_modified = self.request.context.lastModified
		return result
