#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views directly related to individual courses and course sub-objects.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import BTrees

from datetime import datetime

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest

from zope import component
from zope.catalog.interfaces import ICatalog
from zope.intid.interfaces import IIntIds

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.appserver.pyramid_authorization import is_readable

from nti.contenttypes.courses.interfaces import	ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import authorization as nauth

from nti.dataserver.metadata_index import IX_TOPICS
from nti.dataserver.metadata_index import TP_TOP_LEVEL_CONTENT
from nti.dataserver.metadata_index import CATALOG_NAME as METADATA_CATALOG_NAME

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import LocatedExternalList
from nti.externalization.interfaces import StandardExternalFields

from nti.intid.interfaces import ObjectMissingError

from nti.utils.property import CachedProperty

from . import VIEW_COURSE_RECURSIVE

ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS

@view_config( route_name='objects.generic.traversal',
			  context=ICourseInstance,
			  request_method='GET',
			  permission=nauth.ACT_READ,
			  renderer='rest',
			  name=VIEW_COURSE_RECURSIVE)
class CourseRecursiveStreamView(AbstractAuthenticatedView, BatchingUtilsMixin):
	"""
	Stream the relevant course instance objects to the user. This includes
	topics, top-level comments, and UGD shared with the user.
	"""

	@CachedProperty
	def _catalog(self):
		return component.getUtility(ICatalog, METADATA_CATALOG_NAME)

	@CachedProperty
	def _intids(self):
		return component.getUtility(IIntIds)

	@property
	def _family(self):
		return BTrees.family64

	def _intids_in_time_range(self):
# 		min_created_time, max_created_time = self._time_range
# 		if min_created_time is None and max_created_time is None:
# 			return None
#
# 		intids_in_time_range = self._catalog['createdTime'].apply({'between': (min_created_time, max_created_time,)})
# 		return intids_in_time_range
		pass

	def _get_topics(self, course):
		"Return a tuple of topic intids and ntiids."
		topic_ntiids = set()
		topic_intids = self._family.IF.LFSet()
		intids = self._intids

		for forum in course.Discussions.values():
			for topic in forum.values():
				# Make sure we have access to our topic.
				# We'll check comments elsewhere.
				if self._is_readable( topic ):
					topic_intids.add( intids.getId( topic ) )
					topic_ntiids.add( topic.NTIID )
		return topic_intids, topic_ntiids

	def _do_get_top_level_board_objects(self, course):
		"Do the actual topic/top-level comment fetching."
		catalog = self._catalog

		topic_intids, topic_ntiids = self._get_topics( course )
		toplevel_intids_extent = catalog[IX_TOPICS][TP_TOP_LEVEL_CONTENT].getExtent()

		# Comments for our topic ntiids.
		comment_intids = catalog['containerId'].apply({'any_of': topic_ntiids})
		toplevel_comment_intids = toplevel_intids_extent.intersection( comment_intids )

		result_intids = [toplevel_comment_intids, topic_intids]
		result_intids = catalog.family.IF.multiunion(result_intids)

		return result_intids

	def _get_top_level_board_objects(self, course):
		"""
		Get topic/top-level comment fetching for our course and
		parent course, if necessary.
		"""
		result_intids = self._do_get_top_level_board_objects( course )

		if ICourseSubInstance.providedBy( course ):
			parent_course = course.__parent__.__parent__
			parent_intids = self._do_get_top_level_board_objects( parent_course )

			result_intids = [result_intids, parent_intids]
			result_intids = self._catalog.family.IF.multiunion(result_intids)

		return result_intids

	def _security_check(self):
		return self.make_sharing_security_check()

	def filter_shared_with( self, obj ):
		# FIXME Need effective_principals?
		x_sharedWith = getattr( obj, 'sharedWith', ())
		##intids_shared_to_me = catalog['sharedWith'].apply({'all_of': (self.remoteUser.username,)})

	def _is_readable(self, obj):
		return is_readable( obj, self.request, skip_cache=True)

	def batch_before(self):
		pass

	def _get_intids(self, course):
		"Get all intids for this course's stream."
		results = self._get_top_level_board_objects( course )
		return results

	def _get_items(self, temp_results):
		"""
		Given a collection of tuples( obj, timestamp), return
		a sorted collection of objects.
		"""
		security_check = self._security_check()
		items = LocatedExternalList()

		def _intermediates_iter():
			for uid in temp_results:
				try:
					obj = self._intids.getObject( uid )
					timestamp = datetime.fromtimestamp( obj.createdTime )
					yield obj, timestamp
				except ObjectMissingError:
					logger.warn( 'Object missing from course stream (id=%s)', uid )

		for object_timestamp in _intermediates_iter():
			obj = object_timestamp[0]
			if security_check( obj ):
				items.append( object_timestamp )

		items = sorted(items, key=lambda x: x[1])
		return items

	_DEFAULT_BATCH_SIZE = 100
	_DEFAULT_BATCH_START = 0

	def __call__(self):
		# pre-flight the batch
		batch_size, batch_start = self._get_batch_size_start()
		limit = batch_start + batch_size + 2
		batch_before = None
		if self.request.params.get('batchBefore'):
			try:
				batch_before = float(self.request.params.get( 'batchBefore' ))
			except ValueError: # pragma no cover
				raise HTTPBadRequest()

		course = self.request.context
		result = LocatedExternalDict()

		intermediate_results = self._get_intids( course )
		items = self._get_items( intermediate_results )

		# Does our batching, as well as placing a link in result.
		self._batch_items_iterable(result, items,
								   number_items_needed=limit,
								   batch_size=batch_size,
								   batch_start=batch_start)

		#result[ITEMS] = items
		result['TotalItemCount'] = len( result[ITEMS] )
		result['Class'] = 'CourseRecursiveStream'

# 		view = _UGDView( self.request, self.request.remoteUser, None )
# 		view._force_apply_security = True
# 		view.ignore_broken = True
# 		view._needs_filtered = False
#
# 		result_dict = view._sort_filter_batch_objects( items )
# 		result_dict['Class'] = 'CourseRecursiveStream'

			# TODO
		# Sorting....
		# Batching....
		# Next-batch link...

		# batchBefore
		# batchAfter
		# batchSize
		# mimetype filter

		# last modified/etag support
		return result
