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

import time

from datetime import datetime
from datetime import timedelta

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest

from zope import component
from zope.catalog.interfaces import ICatalog
from zope.intid.interfaces import IIntIds

from ZODB.interfaces import IBroken
from ZODB.POSException import POSError

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.appserver.pyramid_authorization import is_readable

from nti.common.property import CachedProperty

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import	ICourseSubInstance

from nti.dataserver.interfaces import IUser

from nti.dataserver import authorization as nauth

from nti.dataserver.metadata_index import IX_CREATOR
from nti.dataserver.metadata_index import IX_TOPICS
from nti.dataserver.metadata_index import TP_DELETED_PLACEHOLDER
from nti.dataserver.metadata_index import TP_TOP_LEVEL_CONTENT
from nti.dataserver.metadata_index import CATALOG_NAME as METADATA_CATALOG_NAME

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import LocatedExternalList
from nti.externalization.interfaces import StandardExternalFields

from nti.intid.interfaces import ObjectMissingError

from nti.links.links import Link

from ..stream_ranking import _DEFAULT_TIME_FIELD
from ..stream_ranking import StreamConfidenceRanker

from . import VIEW_COURSE_RECURSIVE
from . import VIEW_COURSE_RECURSIVE_BUCKET

from ._utils import _get_containers_in_course

ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS

# TODO
# - mimetype filter
# - sorting params
# - caching (memcache?)
# - last modified/etag support

@view_config( route_name='objects.generic.traversal',
			  context=ICourseInstance,
			  request_method='GET',
			  permission=nauth.ACT_READ,
			  renderer='rest',
			  name=VIEW_COURSE_RECURSIVE)
class CourseDashboardRecursiveStreamView(AbstractAuthenticatedView, BatchingUtilsMixin):
	"""
	Stream the relevant course instance objects to the user. This includes
	topics, top-level comments, and UGD shared with the user.

	Using the following params, the client can request a window of objects
	within a time range (Oldest...MostRecent).

	Note: This is becoming close to what the notables do.

	MostRecent
		If given, this is the timestamp (floating point number in fractional
		unix seconds, as returned in ``Last Modified``) of the *youngest*
		change to consider returning. Thus, the most efficient way to page through
		this stream is to *not* use ``batchStart``, but instead to set ``MostRecent``
		to the timestamp of the *oldest* change in the previous batch (always leaving
		``batchStart`` at zero). Effectively, this defaults to the current time.
		(Note: the next/previous link relations do not currently take this into account.)

	Oldest
		If given, this is the timestamp (floating point number in fractional
		unix seconds, as returned in ``Last Modified``) of the *oldest*
		change to consider returning.
	"""

	_DEFAULT_BATCH_SIZE = 50
	_DEFAULT_BATCH_START = 0

	def __init__(self, context, request):
		super( CourseDashboardRecursiveStreamView, self ).__init__( request )
		self.course = context
		self.request = request
		self._set_params()
		self.ranker = StreamConfidenceRanker()

	def _batch_params(self):
		"Sets our batch params."
		self.batch_size, self.batch_start = self._get_batch_size_start()
		self.limit = self.batch_start + self.batch_size + 2
		self.batch_before = None
		self.batch_after = None
		if self.request.params.get('MostRecent'):
			try:
				self.batch_before = float(self.request.params.get( 'MostRecent' ))
			except ValueError: # pragma no cover
				raise HTTPBadRequest()

		if self.request.params.get('Oldest'):
			try:
				self.batch_after = float(self.request.params.get( 'Oldest' ))
			except ValueError: # pragma no cover
				raise HTTPBadRequest()

		if 		self.batch_before and self.batch_after \
			and	self.batch_before < self.batch_after:
			# This behavior is undefined.
			logger.warn( 'MostRecent time is before Oldest time (MostRecent=%s) (Oldest=%s)',
						self.batch_before, self.batch_after )

	def _set_params(self):
		self._batch_params()

	@CachedProperty
	def _catalog(self):
		return component.getUtility(ICatalog, METADATA_CATALOG_NAME)

	@CachedProperty
	def _intids(self):
		return component.getUtility(IIntIds)

	@property
	def _family(self):
		return BTrees.family64

	def _intids_in_time_range( self, min_created_time, max_created_time ):
		# A few different ways to do this; let's use the catalog
		# to awaken fewer objects.  Our timestamp normalizer
		# normalizes to the minute, which should be fine.
		if min_created_time is None and max_created_time is None:
			return None

		# None at boundaries should be ok.
		intids_in_time_range = self._catalog[ _DEFAULT_TIME_FIELD ].apply({'between': (min_created_time, max_created_time,)})
		return intids_in_time_range

	def _topic_is_relevant(self, topic):
		"Determines if our is topic stream worthy."
		creator = getattr( topic, 'creator', None )
		return IUser.providedBy( creator )

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
					# Return our topic if relevant, but make sure we
					# always return the ntiid for its comments.
					if self._topic_is_relevant( topic ):
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
		result_intids = catalog.family.IF.multiunion( result_intids )

		return result_intids

	def _get_top_level_board_objects(self):
		"""
		Get topic/top-level comment fetching for our course and
		parent course, if necessary.
		"""
		course = self.course
		result_intids = self._do_get_top_level_board_objects( course )

		if ICourseSubInstance.providedBy( course ):
			parent_course = course.__parent__.__parent__
			parent_intids = self._do_get_top_level_board_objects( parent_course )

			result_intids = [result_intids, parent_intids]
			result_intids = self._catalog.family.IF.multiunion(result_intids)

		return result_intids

	def _get_course_ugd(self):
		"Top-level notes, shared with me, in my course."
		course = self.course
		catalog = self._catalog
		# This gets our effective principals.
		user_ids = [self.remoteUser.username] + [x.NTIID for x in self.remoteUser.dynamic_memberships]
		intids_shared_to_me = catalog['sharedWith'].apply({'any_of': user_ids})

		toplevel_intids_extent = catalog[IX_TOPICS][TP_TOP_LEVEL_CONTENT].getExtent()
		top_level_shared_intids = toplevel_intids_extent.intersection( intids_shared_to_me )

		# Now grab our course notes
		container_ntiids = _get_containers_in_course( course )
		course_container_intids = catalog['containerId'].apply({'any_of': container_ntiids})
		intids_of_notes = catalog['mimeType'].apply({'any_of': ('application/vnd.nextthought.note',)})

		# Find collisions
		shared_note_intids = catalog.family.IF.intersection( top_level_shared_intids, intids_of_notes )
		results = catalog.family.IF.intersection( shared_note_intids, course_container_intids )
		return results

	def _security_check(self):
		"Make sure our user has permission on the object."
		return self.make_sharing_security_check()

	def _is_readable(self, obj):
		return is_readable( obj, self.request, skip_cache=True)

	def _do_get_intids(self):
		"""
		Return all 'relevant' intids for this course. We keep things
		the remoteUser created, since they may be a note/topic with recent
		replies, which may be important to our user.
		"""
		catalog = self._catalog
		top_level_results = self._get_top_level_board_objects()
		ugd_results = self._get_course_ugd()
		relevant_intids = catalog.family.IF.multiunion( [ugd_results, top_level_results] )

		# Exclude deleted items
		deleted_intids_extent = catalog[IX_TOPICS][TP_DELETED_PLACEHOLDER].getExtent()
		relevant_intids = relevant_intids - deleted_intids_extent
		return relevant_intids

	def _get_intids(self):
		"Get all intids for this course's stream."
		results = self._do_get_intids()

		catalog = self._catalog
		time_range_intids = self._intids_in_time_range( self.batch_after, self.batch_before )
		if time_range_intids is not None:
			results = catalog.family.IF.intersection( time_range_intids, results )
		return results

	def _rank_results(self, results):
		"Given a set of results; rank them and return in sorted priority."
		return self.ranker.rank( results )

	def _get_items(self, temp_results):
		"""
		Given a collection of intids, return a sorted/filtered/permissioned collection of objects.
		"""
		security_check = self._security_check()
		items = LocatedExternalList()

		def _intermediates_iter():
			for uid in temp_results:
				try:
					obj = self._intids.getObject( uid )
					if not IBroken.providedBy(obj):
						yield obj
				except (KeyError, ObjectMissingError):
					logger.warn( 'Object missing from course stream (id=%s)', uid )
				except (TypeError, POSError):
					logger.warn( 'Broken object missing from course stream (id=%s)', uid )

		for obj in _intermediates_iter():
			if security_check( obj ):
				items.append( obj )

		# Rank
		return self._rank_results( items )

	def __call__(self):
		result = LocatedExternalDict()

		intermediate_results = self._get_intids()
		items = self._get_items( intermediate_results )

		# Does our batching, as well as placing a link in result.
		self._batch_items_iterable(result, items,
								   number_items_needed=self.limit,
								   batch_size=self.batch_size,
								   batch_start=self.batch_start)

		result['TotalItemCount'] = len( result[ITEMS] )
		result['Class'] = 'CourseRecursiveStream'

		return result

@view_config( route_name='objects.generic.traversal',
			  context=ICourseInstance,
			  request_method='GET',
			  permission=nauth.ACT_READ,
			  renderer='rest',
			  name=VIEW_COURSE_RECURSIVE_BUCKET)
class CourseDashboardBucketingStreamView( CourseDashboardRecursiveStreamView ):
	"""
	A course recursive stream view that buckets according to params (currently
	hard-coded to bucket by week starting each Monday at 12 AM).  This view
	will start at the input timestamp and will travel backwards until it finds
	'n' buckets of course objects.

	MostRecent
		If given, this is the timestamp (floating point number in fractional
		unix seconds, as returned in ``Last Modified``) of the most recent
		items to get.  This timestamp is also indicative of the first bucket
		to be used.

	NonEmptyBucketCount
		If given, this is the number of non-empty buckets to return. It defaults
		to 2.

	BucketSize
		If given, this is the number of objects to return per bucket. It defaults
		to 50.
	"""

	_DEFAULT_BUCKET_COUNT = 2
	_DEFAULT_BUCKET_SIZE = 50
	# How many buckets will we look in for results before quitting.
	_MAX_BUCKET_CHECKS = 52

	_last_timestamp = None

	def _bucket_params(self):
		"Sets our bucket params."
		self.non_empty_bucket_count = self._DEFAULT_BUCKET_COUNT
		self.bucket_size = self._DEFAULT_BUCKET_SIZE

		if self.request.params.get('NonEmptyBucketCount'):
			try:
				self.non_empty_bucket_count = int(self.request.params.get( 'NonEmptyBucketCount' ))
			except ValueError: # pragma no cover
				raise HTTPBadRequest()

		if self.request.params.get('BucketSize'):
			try:
				self.bucket_size = int(self.request.params.get( 'BucketSize' ))
			except ValueError: # pragma no cover
				raise HTTPBadRequest()

	def _set_params(self):
		super( CourseDashboardBucketingStreamView,self )._set_params()
		self._bucket_params()

	def _get_bucket_batch_link(self, result, start_ts, end_ts):
		"""
		Copied from BatchingUtilsMixin, returns a link to VIEW_COURSE_RECURSIVE
		with params for this particular bucket.

		"""
		next_batch_start = self.bucket_size

		batch_params = self.request.GET.copy()
		# Pop some things that don't work
		for n in self._BATCH_LINK_DROP_PARAMS:
			batch_params.pop( n, None )
			batch_params.pop( 'BucketSize', None )

		batch_params['batchStart'] = next_batch_start
		# Our bucket_size is the de-facto batchSize.
		batch_params['batchSize'] = self.bucket_size
		batch_params['MostRecent'] = end_ts
		batch_params['Oldest'] = start_ts

		link_next = Link( self.request.context,
						rel='batch-next',
						elements=(VIEW_COURSE_RECURSIVE,),
						params=batch_params )
		result.setdefault( LINKS, [] ).append( link_next )

	def _get_first_time_range(self):
		"Return tuple of start/end timestamps for the first week."
		most_recent_date = None
		if self.batch_before is not None:
			most_recent_date = datetime.utcfromtimestamp( self.batch_before )

		the_time = datetime.utcnow() if not most_recent_date else most_recent_date
		# Monday is our default start
		start_of_week = the_time.date() - timedelta( days=the_time.weekday() )
		start_timestamp = time.mktime( start_of_week.timetuple() )
		end_timestamp = time.mktime( the_time.timetuple() )

		# Since we're working backwards, set our next end_timestamp to this
		# call's start_timestamp.
		self._last_timestamp = start_timestamp
		return start_timestamp, end_timestamp

	def _get_next_time_range(self):
		"After getting the first time range, return a tuple of the previous week."
		end_date = datetime.utcfromtimestamp( self._last_timestamp )
		start_date = end_date - timedelta( days=7 )
		start_timestamp = time.mktime( start_date.timetuple() )

		end_timestamp = self._last_timestamp
		# Set our next endcap.
		self._last_timestamp = start_timestamp
		return start_timestamp, end_timestamp

	def _get_time_range_func(self):
		return self._get_next_time_range if self._last_timestamp else self._get_first_time_range

	def _do_batching( self, intids, start_ts, end_ts ):
		"""
		Resolve the intids into objects and batch them.
		"""
		result_dict = {}
		objects = self._get_items( intids )

		self._batch_items_iterable(result_dict, objects,
								   number_items_needed=self.limit,
								   batch_size=self.bucket_size,
								   batch_start=self.batch_start)
		# The next-batch links returned here are irrelevant.
		result_dict.pop( LINKS, None )

		if len( objects ) > self.bucket_size:
			# We have more objects; provide a meaningful paging link.
			self._get_bucket_batch_link( result_dict, start_ts, end_ts )

		return result_dict

	def _do_bucketing(self, course_intids):
		"""
		For the given course intids, bucket accordingly, returning a ready
		to return dict.
		"""
		catalog = self._catalog
		bucket_checks = 0
		found_buckets = 0
		results = []
		start_ts = None

		# Now do our bucketing until:
		# 1. We get our count
		# 2. We are out of objects
		# 3. We reach our max number of buckets to check
		# 4. We are checking a date before the requested oldest timestamp
		while	found_buckets < self.non_empty_bucket_count \
			and bucket_checks < self._MAX_BUCKET_CHECKS \
			and (	start_ts is None
				or 	self.batch_after is None
				or 	start_ts > self.batch_after) \
			and course_intids:

			bucket_checks += 1
			# Get our bucket's time bound intids
			time_range_func = self._get_time_range_func()
			start_ts, end_ts = time_range_func()
			bucket_time_range_intids = self._intids_in_time_range( start_ts, end_ts )
			bucket_intids = catalog.family.IF.intersection( bucket_time_range_intids, course_intids )

			if bucket_intids:
				found_buckets += 1
				# Decrement our collection
				course_intids = catalog.family.IF.difference( course_intids, bucket_intids )

				bucket_dict = self._do_batching( bucket_intids, start_ts, end_ts )

				bucket_dict['OldestTimestamp'] = start_ts
				bucket_dict['MostRecentTimestamp'] = end_ts
				bucket_dict['BucketItemCount'] = len( bucket_dict[ITEMS] )
				bucket_dict['Class'] = 'CourseRecursiveStreamBucket'
				results.append( bucket_dict )

		if found_buckets < self.non_empty_bucket_count:
			logger.info( 'Only found %s buckets when asked for %s (buckets_checked=%s)',
						found_buckets,
						self.non_empty_bucket_count,
						bucket_checks )

		return results

	def _get_bucketed_objects(self):
		"Get the bucketed objects for this stream."
		course_intids = self._do_get_intids()
		results = {}

		if course_intids:
			# Ok we have something; let's bucket.
			results = self._do_bucketing( course_intids )
		return results

	def __call__(self):
		result = LocatedExternalDict()

		items = self._get_bucketed_objects()
		result[ITEMS] = items
		result['TotalBucketCount'] = len( items )
		result['Class'] = 'CourseRecursiveStreamByBucket'
		return result
