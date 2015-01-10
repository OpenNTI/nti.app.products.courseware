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
from . import VIEW_COURSE_RECURSIVE_BUCKET

ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS

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

	@CachedProperty
	def _catalog(self):
		return component.getUtility(ICatalog, METADATA_CATALOG_NAME)

	@CachedProperty
	def _intids(self):
		return component.getUtility(IIntIds)

	@property
	def _family(self):
		return BTrees.family64

	def _intids_in_time_range(self, min_created_time, max_created_time ):
		# A few different ways to do this; let's use the catalog
		# to awaken fewer objects.  Our timestamp normalizer
		# normalizes to the minute, which should be fine.
		if min_created_time is None and max_created_time is None:
			return None

		# None at boundaries should be ok.
		intids_in_time_range = self._catalog['createdTime'].apply({'between': (min_created_time, max_created_time,)})
		return intids_in_time_range

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
		"Make sure our user has permission on the object."
		return self.make_sharing_security_check()

	def filter_shared_with( self, obj ):
		# FIXME Need effective_principals?
		x_sharedWith = getattr( obj, 'sharedWith', ())
		##intids_shared_to_me = catalog['sharedWith'].apply({'all_of': (self.remoteUser.username,)})

	def _is_readable(self, obj):
		return is_readable( obj, self.request, skip_cache=True)

	def _do_get_intids(self, course):
		results = self._get_top_level_board_objects( course )
		return results

	def _get_intids(self, course):
		"Get all intids for this course's stream."
		results = self._do_get_intids(self, course)

		catalog = self._catalog
		time_range_intids = self._intids_in_time_range( self.batch_after, self.batch_before )
		if time_range_intids is not None:
			results = catalog.family.IF.intersection( time_range_intids, results )
		return results

	def _get_items(self, temp_results):
		"""
		Given a collection of tuples( obj, timestamp), return
		a sorted/filtered collection of objects.
		"""
		security_check = self._security_check()
		items = LocatedExternalList()

		def _intermediates_iter():
			for uid in temp_results:
				try:
					obj = self._intids.getObject( uid )
					timestamp = obj.createdTime
					yield obj, timestamp
				except ObjectMissingError:
					logger.warn( 'Object missing from course stream (id=%s)', uid )

		for object_timestamp in _intermediates_iter():
			obj = object_timestamp[0]
			if security_check( obj ):
				items.append( object_timestamp )

		# Filter/sort
		items = sorted( items, key=lambda x: x[1], reverse=True)
		return items

	_DEFAULT_BATCH_SIZE = 100
	_DEFAULT_BATCH_START = 0

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

	def __call__(self):
		self._set_params()
		course = self.request.context
		result = LocatedExternalDict()

		intermediate_results = self._get_intids( course )
		items = self._get_items( intermediate_results )

		# Does our batching, as well as placing a link in result.
		self._batch_items_iterable(result, items,
								   number_items_needed=self.limit,
								   batch_size=self.batch_size,
								   batch_start=self.batch_start)

		result['TotalItemCount'] = len( result[ITEMS] )
		result['Class'] = 'CourseRecursiveStream'

		# TODO
		# mimetype filter
		# sorting params
		# last modified/etag support
		# UGD
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
	hard-coded to bucket by week starting each Monday at 12 AM).
	"""

	_DEFAULT_BUCKET_COUNT = 2
	_DEFAULT_BUCKET_SIZE = 100
	# How many buckets will we look in for results before quitting.
	_MAX_BUCKET_CHECKS = 52

	_last_timestamp = None

	def _get_first_time_range(self):
		"Return tuple of start/end timestamps for the first week."
		most_recent_date = None
		if self.batch_before is not None:
			most_recent_date = datetime.utcfromtimestamp( self.batch_before )

		the_time = datetime.utcnow() if not most_recent_date else most_recent_date
		the_weekday = the_time.isoweekday() - 1 # Monday is our default start
		start_of_week = the_time.date() - timedelta( days=the_weekday )
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

	def _do_batching( self, intids ):
		"""
		Resolve the intids into objects and batch them.
		"""
		result_dict = {}
		objects = self._get_items( intids )

		# TODO The next-batch links returned here are irrelevant.
		self._batch_items_iterable(result_dict, objects,
								   number_items_needed=self.limit,
								   batch_size=self.batch_size,
								   batch_start=self.batch_start)
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

		# Now do our bucketing until we get our count or
		# we bail or we are out of objects.
		while	found_buckets < self.non_empty_bucket_count \
			and bucket_checks < self._MAX_BUCKET_CHECKS \
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

				bucket_dict = self._do_batching( bucket_intids )

				bucket_dict['StartTimestamp'] = start_ts
				bucket_dict['EndTimestamp'] = end_ts
				bucket_dict['BucketItemCount'] = len( bucket_dict[ITEMS] )
				bucket_dict['Class'] = 'CourseRecursiveStreamBucket'
				results.append( bucket_dict )
		return results

	def _get_bucketed_objects(self, course):
		"Get the bucketed objects for this stream."
		course_intids = self._do_get_intids( course )
		results = {}

		if course_intids:
			# Ok we have something; let's bucket.
			results = self._do_bucketing( course_intids )
		return results

	def __call__(self):
		self._set_params()
		course = self.request.context
		result = LocatedExternalDict()

		items = self._get_bucketed_objects( course )
		result[ITEMS] = items
		result['TotalBucketCount'] = len( items )
		result['Class'] = 'CourseRecursiveStreamByBucket'
		return result
