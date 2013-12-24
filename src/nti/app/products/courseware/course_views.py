#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views directly related to individual courses and course sub-objects.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from .interfaces import ICourseInstanceActivity
from .interfaces import ICourseInstanceEnrollment
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutline


from pyramid import httpexceptions as hexc
from pyramid.view import view_config
from nti.appserver._view_utils  import AbstractAuthenticatedView

from nti.dataserver import authorization as nauth

from . import VIEW_CONTENTS
from . import VIEW_COURSE_ENROLLMENT_ROSTER
from . import VIEW_COURSE_ACTIVITY



from nti.contenttypes.courses.interfaces import is_instructed_by_name
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.externalization.interfaces import LocatedExternalDict

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



@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=ICourseInstance,
			 permission=nauth.ACT_READ,
			 name=VIEW_COURSE_ENROLLMENT_ROSTER)
class CourseEnrollmentRosterGetView(AbstractAuthenticatedView):

	def __call__(self):
		request = self.request
		context = request.context
		username = request.authenticated_userid
		course = context

		if not is_instructed_by_name(course, username):
			raise hexc.HTTPForbidden()

		result = LocatedExternalDict()
		result.__name__ = request.view_name
		result.__parent__ = course
		items = result['Items'] = []
		items.extend((component.getMultiAdapter( (course, x),
												 ICourseInstanceEnrollment )
					  for x in ICourseEnrollments(course).iter_enrollments()))
		# TODO: We have no last modified for this
		return result


@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=ICourseInstance,
			 permission=nauth.ACT_READ,
			 name=VIEW_COURSE_ACTIVITY)
class CourseActivityGetView(AbstractAuthenticatedView):

	def __call__(self):
		request = self.request
		context = request.context
		username = request.authenticated_userid
		course = context

		if not is_instructed_by_name(course, username):
			raise hexc.HTTPForbidden()

		activity = ICourseInstanceActivity(course)
		# TODO: Very similar to ugd_query_views

		result = LocatedExternalDict()
		result.__parent__ = course
		result.__name__ = VIEW_COURSE_ACTIVITY
		result['TotalItemCount'] = total_item_count = len(activity)

		result.lastModified = activity.lastModified
		result['Last Modified'] = result.lastModified

		# NOTE: We could be more efficient by paging around
		# the timestamp rather than a size
		batch_size, batch_start = self._get_batch_size_start()

		number_items_needed = total_item_count
		if batch_size is not None and batch_start is not None:
			number_items_needed = min(batch_size + batch_start + 2, total_item_count)

		self._batch_tuple_iterable(result, activity.items(),
								   number_items_needed,
								   batch_size, batch_start)

		return result
