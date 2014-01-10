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
from zope import interface

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
		# NOTE: These items do not get __parent__ set, so
		# we get a lot of logging about not being able to render
		# links...sigh.
		items.extend((component.getMultiAdapter( (course, x),
												 ICourseInstanceEnrollment )
					  for x in ICourseEnrollments(course).iter_enrollments()))
		# TODO: We have no last modified for this
		return result


from .interfaces import ICourseCatalog
from nti.dataserver.interfaces import IDataserverFolder
from nti.dataserver.users.interfaces import IUserProfile

import collections
from nti.externalization.interfaces import LocatedExternalList
from cStringIO import StringIO
import csv

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN, # TODO: Better perm. This is generally used for admin
			 name='AllEnrollments')
class AllCourseEnrollmentRosterDownloadView(AbstractAuthenticatedView):
	"""
	Provides a downloadable table of all the enrollments
	present in the system. The table has columns
	for username, email address, and enrolled courses.
	"""


	def __call__(self):
		# Our approach is to find all the courses,
		# and get the enrollments in each course,
		# accumulating users as we go.
		# (NOTE: This winds up being an O(n^2) approach
		# due to the poor implementation of enrollments
		# for legacy courses.)

		user_to_coursenames = collections.defaultdict(set)

		catalog = component.getUtility(ICourseCatalog)

		for catalog_entry in catalog:
			course_name = catalog_entry.Title

			course = ICourseInstance(catalog_entry)

			enrollments = ICourseEnrollments(course)

			for user in enrollments.iter_enrollments():
				user_to_coursenames[user].add( course_name )

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
			rows.append( row )

		# Convert to CSV
		# In the future, we might switch based on the accept header
		# and provide it as json alternately
		buf = StringIO()
		writer = csv.writer(buf)
		writer.writerows(rows)

		self.request.response.body = buf.getvalue()
		self.request.response.content_disposition = b'attachment; filename="enrollments.csv"'

		return self.request.response


from zope.traversing.interfaces import IPathAdapter
from pyramid.interfaces import IRequest

@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def CourseActivityPathAdapter(context, request):
	return ICourseInstanceActivity(context)

from nti.externalization.externalization import decorate_external_mapping

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=ICourseInstanceActivity,
			 permission=nauth.ACT_READ)
class CourseActivityGetView(AbstractAuthenticatedView):

	def __call__(self):
		request = self.request
		context = request.context
		username = request.authenticated_userid
		course = context

		if not is_instructed_by_name(course, username):
			# Precondition may not be needed anymore, we can put an ACL on the activity
			raise hexc.HTTPForbidden()

		activity = ICourseInstanceActivity(course)
		# TODO: Very similar to ugd_query_views

		result = LocatedExternalDict()
		result.__parent__ = course
		result.__name__ = VIEW_COURSE_ACTIVITY
		result['TotalItemCount'] = total_item_count = len(activity)


		# NOTE: We could be more efficient by paging around
		# the timestamp rather than a size
		batch_size, batch_start = self._get_batch_size_start()

		number_items_needed = total_item_count
		if batch_size is not None and batch_start is not None:
			number_items_needed = min(batch_size + batch_start + 2, total_item_count)

		self._batch_tuple_iterable(result, activity.items(),
								   number_items_needed,
								   batch_size, batch_start)

		decorate_external_mapping(activity, result)

		last_modified = max(activity.lastModified, result['lastViewed'])
		result.lastModified = last_modified
		result['Last Modified'] = last_modified

		return result

from pyramid.threadlocal import get_current_request

from numbers import Number


from zope.annotation.interfaces import IAnnotations

from nti.zodb.containers import time_to_64bit_int
from nti.zodb.containers import bit64_int_to_time

import BTrees

from nti.appserver._view_utils import ModeledContentUploadRequestUtilsMixin

from nti.externalization.interfaces import StandardExternalFields
LINKS = StandardExternalFields.LINKS
from nti.dataserver.links import Link


@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='PUT',
			 context=ICourseInstanceActivity,
			 permission=nauth.ACT_READ,
			 name='lastViewed')
class CourseActivityLastViewedDecorator(AbstractAuthenticatedView,
										ModeledContentUploadRequestUtilsMixin):
	"""
	Because multiple administrators might have access to the course
	activity, we maintain a per-user lastViewed timestamp as an
	annotation on the activity object.

	The annotation itself is a :class:`BTrees.OLBTree`, with usernames as
	keys and the values being int-encoded time values.

	This object is both a view callable for updating that value,
	and a decorator for putting that value in the object.
	"""

	inputClass = Number

	KEY = 'nti.app.products.courseware.decorators._CourseInstanceActivityLastViewedDecorator'

	def __init__(self, request=None):
		if IRequest.providedBy(request): # as a view
			super(CourseActivityLastViewedDecorator,self).__init__(request)
		# otherwise, we're a decorator and no args are passed


	def _precondition(self, context, request):
		username = None
		if request:
			username = request.authenticated_userid
		if not is_instructed_by_name(context, username):
			return False
		return username


	def decorateExternalMapping(self, context, result):
		username = self._precondition(context, get_current_request())
		if not username:
			return

		annot = IAnnotations(context)
		mapping = annot.get(self.KEY)
		if mapping is None or username not in mapping:
			result['lastViewed'] = 0
		else:
			result['lastViewed'] = bit64_int_to_time(mapping[username])

		# And tell them where to PUT it :)
		links = result.setdefault( LINKS, [] )
		links.append( Link( context,
							rel='lastViewed',
							elements=('lastViewed',),
							method='PUT' ) )


	def __call__(self):
		context = self.request.context
		username = self._precondition(context, self.request)
		# Precondition may not be needed anymore, we can put an ACL on the activity
		if not username:
			raise hexc.HTTPForbidden()

		annot = IAnnotations(context)
		mapping = annot.get(self.KEY)
		if mapping is None:
			mapping = BTrees.OLBTree.BTree()
			annot[self.KEY] = mapping

		now = self.readInput()
		mapping[username] = time_to_64bit_int(now)
		return now
