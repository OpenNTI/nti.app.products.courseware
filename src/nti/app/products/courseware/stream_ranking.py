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

from pyramid.security import authenticated_userid
from pyramid.threadlocal import get_current_request

from zope import component

from nti.dataserver import rating
from nti.dataserver import liking

from nti.dataserver.users import User

from .interfaces import IRanker
from .interfaces import IViewStats

_DEFAULT_TIME_FIELD = 'lastModified'

def _get_likes(obj):
	return liking.like_count(obj)

def _get_favorites(obj):
	return rating.rate_count(obj, 'favorites')

def _safe_check(func, obj):
	"Some objects may not have ratings. Return zero in those cases."
	result = 0
	try:
		result = func(obj)
	except (TypeError, LookupError):
		pass
	return result

def _get_ratings(obj):
	like_count = _safe_check(_get_likes, obj)
	favorite_count = _safe_check(_get_favorites, obj)
	return like_count, favorite_count

def _get_time_field(obj):
	return getattr(obj, _DEFAULT_TIME_FIELD, 0)

def _get_view_stats(obj, user):
	if not user:
		result = IViewStats(obj, None)
	else:
		result = component.queryMultiAdapter( (obj, user), IViewStats )
	return result

@interface.implementer(IRanker)
class StreamConfidenceRanker(object):
	"""
	Modeled after the reddit comment ranking system that relies on the
	fraction of upvotes versus downvotes to base confidence in a 'ranking'.

	Since we do not currently have downvotes, we modify this to rank based
	on the upvotes versus total number of votes on our items.

	See: http://amix.dk/blog/post/19588
	"""
	user = None

	def _get_remote_user(self):
		if self.user is None:
			request = get_current_request()
			username = authenticated_userid( request ) if request else None
			if username:
				self.user = User.get_user( username )
		return self.user

	def _obj_ranking(self, obj):
		"""
		We rank on the ratio of upvotes and replies to views, secondarily
		on last modified.  Items with heavy interactions will bubble to top.
		If there is little activity, new items should generally have a favorable
		ratio and bubble to top.
		"""
		likes, favorites = _get_ratings(obj)
		interactions = likes + favorites
		obj_time = _get_time_field(obj)

		view_stats = _get_view_stats(obj, self._get_remote_user())
		view_count = 0
		if view_stats:
			view_count = view_stats.view_count
			interactions += view_stats.new_reply_count_for_user

		score = (interactions * 1.0) / view_count if view_count else 1

		# The actual algorithm logarithmically adjusts the upvotes
		# (log10 makes votes 11-100 count as much as votes 1-10). For
		# our current scale, the pure ratio may be enough.
		return (score, obj_time)

	def rank(self, items):
		if items is None:
			return []
		items.sort(key=self._obj_ranking, reverse=True)
		return items

@interface.implementer(IRanker)
class LastModifiedRanker(object):
	"""
	A simple ranker that ranks items based a time field. Newer objects
	(e.g. created or LastModified) will rank higher than older objects.
	"""

	def rank(self, items):
		if items is None:
			return []

		items.sort(reverse=True, key=_get_time_field)
		return items
