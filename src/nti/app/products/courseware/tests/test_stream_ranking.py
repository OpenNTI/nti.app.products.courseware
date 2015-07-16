#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import contains
from hamcrest import has_length
from hamcrest import assert_that

import time
import fudge
from unittest import TestCase

from nti.app.products.courseware.interfaces import IRanker

from nti.app.products.courseware.stream_ranking import _DEFAULT_TIME_FIELD

from nti.app.products.courseware.stream_ranking import LastModifiedRanker
from nti.app.products.courseware.stream_ranking import StreamConfidenceRanker

from nti.testing.matchers import is_empty
from nti.testing.matchers import validly_provides
from nti.testing.time import time_monotonically_increases

class _ViewStats( object ):

	def __init__(self, view_count, new_reply_count_for_user=0 ):
		self.view_count = view_count
		self.new_reply_count_for_user = new_reply_count_for_user

class Object(object):
	def __str__(self):
		return str( self.__dict__ )

class TestStreamRanking( TestCase ):

	def _do_last_mod_tests(self, ranker):
		assert_that( ranker, validly_provides( IRanker ))

		results = ranker.rank( [] )
		assert_that( results, is_empty() )
		assert_that( results, has_length(0) )

		results = ranker.rank( None )
		assert_that( results, is_empty() )
		assert_that( results, has_length(0) )

		results = ranker.rank( [ object() ] )
		assert_that( results, has_length(1) )

		empty_obj = Object()
		first_obj = Object()
		setattr( first_obj, _DEFAULT_TIME_FIELD, 1 )
		second_obj = Object()
		setattr( second_obj, _DEFAULT_TIME_FIELD, time.time() )
		third_obj = Object()
		setattr( third_obj, _DEFAULT_TIME_FIELD, time.time() )

		results = ranker.rank( [ empty_obj, first_obj, third_obj, second_obj ] )
		assert_that( results, has_length( 4 ) )
		assert_that( results, contains( third_obj, second_obj, first_obj, empty_obj ))

	@time_monotonically_increases
	def test_last_mod(self):
		ranker = LastModifiedRanker()
		self._do_last_mod_tests( ranker )

	@time_monotonically_increases
	def test_confidence_without_attrs(self):
		ranker = StreamConfidenceRanker()
		# Same as last mod
		self._do_last_mod_tests( ranker )

	@fudge.patch( 'nti.dataserver.rating.rate_count' )
	@fudge.patch( 'nti.dataserver.liking.like_count' )
	@fudge.patch( 'nti.app.products.courseware.stream_ranking._get_view_stats')
	def test_confidence( self, mock_rate_count, mock_like_count, mock_view_stats ):

		# obj0 is totally empty
		# obj1 small upvotes but good ratio
		# obj2 no upvotes, but replies and low ratio
		# obj3 lots of upvotes/replies to views
		fake_like = mock_like_count.is_callable().returns( 0 )
		fake_like.next_call().returns( 0 )
		fake_like.next_call().returns( 0 )
		fake_like.next_call().returns( 5 )

		fake_rate = mock_rate_count.is_callable().returns( 0 )
		fake_rate.next_call().returns( 1 )
		fake_rate.next_call().returns( 0 )
		fake_rate.next_call().returns( 50 )

		fake_view = mock_view_stats.is_callable().returns( _ViewStats( 0 ) )
		fake_view.next_call().returns( _ViewStats( 1, 1 ) )
		fake_view.next_call().returns( _ViewStats( 10, 1 ) )
		fake_view.next_call().returns( _ViewStats( 10, 50 ) )

		ranker = StreamConfidenceRanker()
		assert_that( ranker, validly_provides( IRanker ))

		now = time.time()
		empty_obj = Object()
		setattr( empty_obj, _DEFAULT_TIME_FIELD, now )
		first_obj = Object()
		setattr( first_obj, _DEFAULT_TIME_FIELD, now )
		second_obj = Object()
		setattr( second_obj, _DEFAULT_TIME_FIELD, now )
		third_obj = Object()
		setattr( third_obj, _DEFAULT_TIME_FIELD, now )

		results = ranker.rank( [ empty_obj, first_obj, second_obj, third_obj ] )
		assert_that( results, has_length( 4 ) )
		assert_that( results, contains( third_obj, first_obj, second_obj, empty_obj ))

