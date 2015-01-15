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

from nti.contentsearch.interfaces import IBookContent
from nti.contentsearch.interfaces import INTICardContent
from nti.contentsearch.interfaces import ISearchHitPredicate
from nti.contentsearch.interfaces import IContainerIDResolver
from nti.contentsearch.interfaces import IAudioTranscriptContent
from nti.contentsearch.interfaces import IVideoTranscriptContent

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import is_ntiid_of_types

from nti.utils.property import Lazy

from .interfaces import ICourseOutlineCache

@interface.implementer(ISearchHitPredicate)
class _BasePredicate(object):

	def __init__(self, *args):
		pass

	@Lazy
	def cache(self):
		result = component.getUtility(ICourseOutlineCache)
		return result
	
	def _is_allowed(self, ntiid, query=None, now=None):
		result = self.cache._is_allowed(ntiid, query=query, now=now)
		return result

	def allow(self, item, score, query=None):
		raise NotImplementedError()

@component.adapter(IBookContent)
class _ContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = self._is_allowed(item.ntiid, query)
		if not result:
			logger.debug("Content ('%s') in container '%s' not allowed for search.", 
						 item.title, item.ntiid)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(IAudioTranscriptContent)
class _AudioContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = self._is_allowed(item.containerId, query)
		if not result:
			logger.debug("AudioContent ('%s') in container '%s' not allowed for search.", 
						 item.title, item.containerId)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(IVideoTranscriptContent)
class _VideoContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = self._is_allowed(item.containerId, query)
		if not result:
			logger.debug("VideoContent ('%s') in container '%s' not allowed for search.", 
						 item.title, item.containerId)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(INTICardContent)
class _NTICardContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = self._is_allowed(item.containerId, query) and \
				 self._is_allowed(item.target_ntiid, query)
		if not result:
			logger.debug("NTICardContent ('%s') in container '%s' not allowed for search.",
						 item.title, item.containerId)
		return result

@interface.implementer(ISearchHitPredicate)
class _CreatedContentHitPredicate(_BasePredicate):

	def _allowed(self, containerId, query):
		return bool(not containerId or \
					is_ntiid_of_types(containerId, (TYPE_OID,)) or \
					self._is_allowed(containerId, query))
			
	def allow(self, item, score, query=None):
		resolver = IContainerIDResolver(item, None)
		containerId = resolver.containerId if resolver is not None else None
		result = self._allowed(containerId, query)
		if not result:
			logger.debug("Object (%s) in container '%s' not allowed for search.",
						 item, containerId)
		return result
