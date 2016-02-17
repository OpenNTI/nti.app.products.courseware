#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.component.hooks import getSite

from nti.app.products.courseware.search import encode_keys
from nti.app.products.courseware.search import memcache_get
from nti.app.products.courseware.search import memcache_set
from nti.app.products.courseware.search import memcache_client
from nti.app.products.courseware.search import last_synchronized

from nti.app.products.courseware.search.interfaces import ICourseOutlineCache

from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQAssessmentItemContainer

from nti.common.property import Lazy

from nti.contentlibrary.interfaces import IContentUnit

from nti.contentsearch.interfaces import IBookContent
from nti.contentsearch.interfaces import INTICardContent
from nti.contentsearch.interfaces import ISearchHitPredicate
from nti.contentsearch.interfaces import IContainerIDResolver
from nti.contentsearch.interfaces import IAudioTranscriptContent
from nti.contentsearch.interfaces import IVideoTranscriptContent

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import is_ntiid_of_types
from nti.ntiids.ntiids import find_object_with_ntiid

@interface.implementer(ISearchHitPredicate)
class _BasePredicate(object):

	def __init__(self, *args):
		pass

	@Lazy
	def cache(self):
		result = component.getUtility(ICourseOutlineCache)
		return result

	def _is_allowed(self, ntiid, query=None, now=None):
		result = self.cache.is_allowed(ntiid, query=query, now=now)
		return result

	def allow(self, item, score, query=None):
		raise NotImplementedError()

@component.adapter(IBookContent)
class _ContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = self._is_allowed(item.ntiid, query)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(IAudioTranscriptContent)
class _AudioContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = self._is_allowed(item.containerId, query)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(IVideoTranscriptContent)
class _VideoContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = self._is_allowed(item.containerId, query)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(INTICardContent)
class _NTICardContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result =	 self._is_allowed(item.containerId, query) \
				 and self._is_allowed(item.target_ntiid, query)
		return result

@interface.implementer(ISearchHitPredicate)
class _CreatedContentHitPredicate(_BasePredicate):

	def _allowed(self, containerId, query):
		return bool(	not containerId
					or	is_ntiid_of_types(containerId, (TYPE_OID,))
					or	self._is_allowed(containerId, query))

	def allow(self, item, score, query=None):
		resolver = IContainerIDResolver(item, None)
		containerId = resolver.containerId if resolver is not None else None
		result = self._allowed(containerId, query)
		return result

@component.adapter(IBookContent)
class _ContentAssesmentHitPredicate(_BasePredicate):

	@Lazy
	def memcache(self):
		return memcache_client()

	def has_assesments(self, ntiid):
		context = find_object_with_ntiid(ntiid or u'')
		if IContentUnit.providedBy(context):
			container = IQAssessmentItemContainer(context, None)
			if container is None:
				return False
			for item in container.assessments():
				if IQAssignment.providedBy(item) or IQSurvey.providedBy(item):
					return True
		return False

	def cache_key(self, ntiid):
		site = getSite().__name__
		clazz = self.__class__.__name__
		lastSync = last_synchronized()
		result = '/search/%s' % encode_keys(site, clazz, ntiid, lastSync)
		return result

	def _is_allowed(self, ntiid, query=None, now=None):
		key = self.cache_key(ntiid)
		result = memcache_get(key, self.memcache)
		if result is None:
			result = not self.has_assesments(ntiid)
			memcache_set(key, result)
		return result

	def allow(self, item, score, query=None):
		result = self._is_allowed(item.ntiid, query)
		return result
