#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views directly related to individual courses and course sub-objects.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.dataserver import rating
from nti.dataserver import liking

from .interfaces import IRanker

_DEFAULT_TIME_FIELD = 'lastModified'

def _get_likes( obj ):
	return liking.like_count( obj )

def _get_favorites( obj ):
	return rating.rate_count( obj, 'favorites' )

def _safe_check( func, obj ):
	"Some objects may not have ratings. Return zero in those cases."
	result = 0
	try:
		result = func( obj )
	except (TypeError, LookupError):
		pass
	return result

def _get_ratings( obj ):
	like_count = _safe_check( _get_likes, obj )
	favorite_count = _safe_check( _get_favorites, obj )
	return like_count, favorite_count

def _get_time_field( obj ):
	return getattr( obj, _DEFAULT_TIME_FIELD, 0 )

@interface.implementer( IRanker )
class StreamConfidenceRanker( object ):
	"""
	Modeled after the reddit comment ranking system that relies on the
	fraction of upvotes versus downvotes to base confidence in a 'ranking'.

	Since we do not currently have downvotes, we modify this to rank based
	on the upvotes versus total number of votes on our items.

	http://amix.dk/blog/post/19588
	"""

# 	def _obj_ranking(self, obj):
# 		likes, favorites = get_ratings( obj )
# 		total_count = likes + favorites
#
# 		if total_count == 0:
# 			return 0
#
# 		z = 1.0 #1.0 = 85%, 1.6 = 95%
# 		phat = float( likes + favorites ) / total_count
# 		return sqrt(phat+z*z/(2*total_count)-z*((phat*(1-phat)+z*z/(4*total_count))/total_count)) \
# 					/(1+z*z/total_count)

	def _obj_ranking(self, obj):
		"""
		First rank based on total upvotes. Secondarily rank
		based on time.
		"""
		likes, favorites = _get_ratings( obj )
		total_count = likes + favorites
		obj_time = _get_time_field( obj )
		return (total_count, obj_time)

	def rank(self, items):
		if items is None:
			return []

		items.sort( key=self._obj_ranking, reverse=True )
		return items

@interface.implementer( IRanker )
class LastModifiedRanker( object ):
	"""
	A simple ranker that ranks items based a time field. Newer objects
	(e.g. created or LastModified) will rank higher than older objects.
	"""

	def rank(self, items):
		if items is None:
			return []

		items.sort( reverse=True, key=_get_time_field )
		return items
