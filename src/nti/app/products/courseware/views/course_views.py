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

from zope.traversing.interfaces import IPathAdapter

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid.interfaces import IRequest
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.appserver.pyramid_authorization import has_permission
from nti.appserver.ugd_edit_views import ContainerContextUGDPostView

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import ILocatedExternalSequence

from nti.externalization.externalization import to_external_object

from ..interfaces import ACT_VIEW_ROSTER
from ..interfaces import ICourseInstanceActivity
from ..interfaces import ICourseInstanceEnrollment

from . import VIEW_CONTENTS
from . import VIEW_COURSE_ACTIVITY
from . import VIEW_COURSE_ENROLLMENT_ROSTER

ITEMS = StandardExternalFields.ITEMS

@view_config(route_name='objects.generic.traversal',
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
				ext_node['contents'] = _recur([], node.values())
				# Pretty pointless to send these
				ext_node.pop('NTIID', None)
				ext_node.pop('OID', None)

				the_list.append(ext_node)
			return the_list

		_recur(result, values)
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context
		self.request.response.last_modified = self.request.context.lastModified

		return result

from zope.intid.interfaces import IIntIds
from zope.container.contained import Contained

from nti.appserver.interfaces import IIntIdUserSearchPolicy

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.common.property import alias

from nti.dataserver.interfaces import IUser
from nti.dataserver.users.interfaces import IFriendlyNamed

@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
class CourseEnrollmentRosterPathAdapter(Contained):
	"""
	We use a path adapter for the enrollment object so that we
	can traverse to actual course enrollment objects for enrolled users,
	thus letting us have named views or further traversing
	for those objects.
	"""

	def __init__(self, course, request):
		self.__parent__ = course
		self.__name__ = VIEW_COURSE_ENROLLMENT_ROSTER

	course = alias('__parent__')

	def __getitem__(self, username):
		username = username.lower()
		# XXX: We can do better than this interface now
		enrollments_iter = ICourseEnrollments(self.__parent__).iter_enrollments()

		for record in enrollments_iter:
			user = IUser(record)
			if user.username.lower() == username:
				enrollment = component.getMultiAdapter((self.__parent__, record),
														ICourseInstanceEnrollment)

				if enrollment.__parent__ is None:
					# Typically it will be, lets give it the right place
					enrollment.xxx_fill_in_parent()
					enrollment.CourseInstance = None
				return enrollment

		raise KeyError(username)

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=CourseEnrollmentRosterPathAdapter,
			 permission=ACT_VIEW_ROSTER)
class CourseEnrollmentRosterGetView(AbstractAuthenticatedView,
									BatchingUtilsMixin):
	"""
	Support retrieving the enrollment status of members of the class.
	Any extra path is taken as the username to lookup and only that
	user's record is returned (or a 404 if the user is not found
	enrolled); query parameters are ignored.

	The return dictionary will have the following entries:

	Items
		A list of enrollment objects.

	FilteredTotalItemCount
		The total number of items that match the filter, if specified;
		identical to TotalItemCount if there is no filter.

	TotalItemCount
		How many total enrollments there are. If any filter, sorting
		or paging options are specified, this will be the same as the
		number of enrolled students in the class (because we will
		ultimately return that many rows due to the presence of null
		rows for non-submitted students).

	The following query parameters are supported:

	sortOn
		The field to sort on. Options are ``realname`` to sort on the parts
		of the user's realname (\"lastname\" first; note that this is
		imprecise and likely to sort non-English names incorrectly.);
		username``.

	sortOrder
		The sort direction. Options are ``ascending`` and
		``descending``. If you do not specify, a value that makes the
		most sense for the ``sortOn`` parameter will be used by
		default.

	filter
		Whether to filter the returned data in some fashion. Several
		values are defined:

		* ``LegacyEnrollmentStatusForCredit``: Only students that are
		  enrolled for credit are returned. An entry in the dictionary is
		  returned for each such student, even if they haven't submitted;
		  the value for students that haven't submitted is null.

		* ``LegacyEnrollmentStatusOpen``: Only students that are
		  enrolled NOT for credit are returned. An entry in the dictionary is
		  returned for each such student, even if they haven't submitted;
		  the value for students that haven't submitted is null.

	usernameSearchTerm
		If provided, only users that match this search term
		will be returned. This search is based on the username and
		realname and alias, and does prefix matching, the same as
		the normal search algorithm for users. This is independent
		of filtering.

	batchSize
		Integer giving the page size. Must be greater than zero.
		Paging only happens when this is supplied together with
		``batchStart`` (or ``batchAround`` for those views that support it).

	batchStart
		Integer giving the index of the first object to return,
		starting with zero. Paging only happens when this is
		supplied together with ``batchSize``.

	"""
	def __call__(self):
		request = self.request
		context = request.context.course
		course = context

		result = LocatedExternalDict()
		result.__name__ = request.view_name
		result.__parent__ = course
		items = result[ITEMS] = []

		enrollments_iter = ICourseEnrollments(course).iter_enrollments()

		filter_name = self.request.params.get('filter')
		sort_name = self.request.params.get('sortOn')
		sort_reverse = self.request.params.get('sortOrder', 'ascending') == 'descending'
		username_search_term = self.request.params.get('usernameSearchTerm')

		if sort_name == 'realname':
			# An alternative way to do this would be to get the
			# intids of the users (available from the EntityContainer)
			# and then have an index on the reverse name in the entity
			# catalog (we have the name parts, but keyword indexes are
			# not sortable)
			def _key(record):
				user = IUser(record)
				parts = IFriendlyNamed(user).get_searchable_realname_parts()
				if not parts:
					return ''
				parts = reversed(parts)  # last name first
				return ' '.join(parts).lower()

			enrollments_iter = sorted(enrollments_iter,
									  key=_key,
									  reverse=sort_reverse)
		elif sort_name == 'username':
			_key = lambda x: IUser(x).username
			enrollments_iter = sorted(enrollments_iter,
									  key=_key,
									  reverse=sort_reverse)
		elif sort_name:  # pragma: no cover
			# We're not silently ignoring because in the past
			# we've had clients send in the wrong value for a long time
			# before anybody noticed
			raise hexc.HTTPBadRequest("Unsupported sort option")

		items.extend((component.getMultiAdapter((course, x),
												 ICourseInstanceEnrollment)
					  for x in enrollments_iter))
		result['FilteredTotalItemCount'] = result['TotalItemCount'] = len(result['Items'])

		# We could theoretically be more efficient with the user of
		# the IEnumerableEntity container and the scopes, especially
		# if we did that FIRST, before getting the enrollments, and
		# paging that range of usernames, and doing the entity
		# username search on the intid set it returns. However, this
		# is good enough for now. Sorting is maintained from above.
		# Note that it will blow up once we have non-legacy courses.

		if filter_name == 'LegacyEnrollmentStatusForCredit':
			items = [x for x in items if x.LegacyEnrollmentStatus == 'ForCredit']
			result['FilteredTotalItemCount'] = len(items)
		elif filter_name == 'LegacyEnrollmentStatusOpen':
			items = [x for x in items if x.LegacyEnrollmentStatus == 'Open']
			result['FilteredTotalItemCount'] = len(items)
		elif filter_name:  # pragma: no cover
			raise hexc.HTTPBadRequest("Unsupported filteroption")

		if username_search_term:
			policy = component.getAdapter(self.remoteUser, 
										  IIntIdUserSearchPolicy,
										  name='comprehensive')
			id_util = component.getUtility(IIntIds)
			matched_ids = policy.query_intids(username_search_term.lower())
			items = [x for x in items if id_util.getId(IUser(x)) in matched_ids]
			result['FilteredTotalItemCount'] = len(items)

		self._batch_tuple_iterable(result, items,
								   selector=lambda x: x)

		# NOTE: Rendering the same CourseInstance over and over is hugely
		# expensive, and massively bloats the response...77 students
		# can generate 12MB of response. So we don't include the course instance
		for i in result[ITEMS]:
			if i.__parent__ is None:
				# Typically it will be, lets give it the right
				# place
				i.xxx_fill_in_parent()
			i.CourseInstance = None

		# TODO: We have no last modified for this
		return result

@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def CourseActivityPathAdapter(context, request):
	return ICourseInstanceActivity(context)

from nti.externalization.externalization import decorate_external_mapping

from ..interfaces import ACT_VIEW_ACTIVITY

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=ICourseInstanceActivity,
			 permission=ACT_VIEW_ACTIVITY)
class CourseActivityGetView(AbstractAuthenticatedView,
							BatchingUtilsMixin):

	def __call__(self):
		request = self.request
		context = request.context
		course = context

		activity = ICourseInstanceActivity(course)

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

import BTrees

from numbers import Number

from zope.annotation.interfaces import IAnnotations

from pyramid.threadlocal import get_current_request

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.common.time import time_to_64bit_int
from nti.common.time import bit64_int_to_time

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='PUT',
			 context=ICourseInstanceActivity,
			 permission=ACT_VIEW_ACTIVITY,
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
		if IRequest.providedBy(request):  # as a view
			super(CourseActivityLastViewedDecorator, self).__init__(request)
		# otherwise, we're a decorator and no args are passed

	def decorateExternalMapping(self, context, result):
		request = get_current_request()
		if request is None or not request.authenticated_userid:
			return

		if not has_permission(ACT_VIEW_ACTIVITY, context, request):
			return False

		username = request.authenticated_userid

		annot = IAnnotations(context)
		mapping = annot.get(self.KEY)
		if mapping is None or username not in mapping:
			result['lastViewed'] = 0
		else:
			result['lastViewed'] = bit64_int_to_time(mapping[username])

		# And tell them where to PUT it :)
		links = result.setdefault(LINKS, [])
		links.append(Link(context,
						  rel='lastViewed',
						  elements=('lastViewed',),
						  method='PUT'))

	def __call__(self):
		context = self.request.context
		username = self.request.authenticated_userid

		annot = IAnnotations(context)
		mapping = annot.get(self.KEY)
		if mapping is None:
			mapping = BTrees.OLBTree.BTree()
			annot[self.KEY] = mapping

		now = self.readInput()
		mapping[username] = time_to_64bit_int(now)
		return now

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='POST',
			 context=ICourseInstance,
			 permission=nauth.ACT_READ,
			 name='Pages')
class CoursePagesView(ContainerContextUGDPostView):
	"""
	A pages view on the course.  We subclass ``ContainerContextUGDPostView`` in
	order to intervene and annotate our ``IContainerContext``
	object with the course context.

	Reading/Editing/Deleting will remain the same.
	"""

from ..utils import get_enrollment_options

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   name="EnrollmentOptions",
			   permission=ACT_VIEW_ROSTER)
class CourseEnrollmentOptionsGetView(AbstractAuthenticatedView):

	def __call__(self):
		options = get_enrollment_options(self.context)
		return options
