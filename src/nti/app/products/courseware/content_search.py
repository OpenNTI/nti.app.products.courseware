#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from datetime import datetime

from zope import component
from zope import interface

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contentsearch.interfaces import IBookContent
from nti.contentsearch.interfaces import INTICardContent
from nti.contentsearch.interfaces import ISearchHitPredicate
from nti.contentsearch.interfaces import IContainerIDResolver
from nti.contentsearch.interfaces import IAudioTranscriptContent
from nti.contentsearch.interfaces import IVideoTranscriptContent

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import ICreated

from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

def _get_content_path(ntiid):
	result = ()
	library = component.queryUtility(IContentPackageLibrary)
	if library and ntiid:
		paths = library.pathToNTIID(ntiid)
		result = tuple(p.ntiid for p in paths) if paths else ()
	return result

def _get_outline_node(outline, ntiids=()):
	if not ntiids:
		return None

	def _recur(node):
		content_ntiid = getattr(node, 'ContentNTIID', None)
		if content_ntiid and content_ntiid in ntiids:
			return node

		result = None
		for child in node.values():
			result = _recur(child)
			if result is not None:
				break
		return result

	result = _recur(outline)
	return result

def _is_allowed(ntiid, query=None, now=None):
	if query is None:
		return True # allow by default

	context = query.context or {}
	course = context.get('course')
	if not course or not is_valid_ntiid_string(course):
		return True # allow by default
	
	course = find_object_with_ntiid(course)
	if not course or not ICourseInstance.providedBy(course):
		return True # allow by default
		
	result = True
	ntiids = _get_content_path(ntiid)
	node = _get_outline_node(course.Outline, ntiids)
	if node is not None:
		now = now or datetime.utcnow()
		beginning = getattr(node, 'AvailableBeginning', None) or now
		is_outline_stub_only = getattr(node, 'is_outline_stub_only', False)
		result = not is_outline_stub_only and now >= beginning
	return result

@interface.implementer(ISearchHitPredicate)
class _BasePredicate(object):

	def __init__(self, *args):
		pass

	def allow(self, item, score, query=None):
		raise NotImplementedError()

@component.adapter(IBookContent)
class _ContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = _is_allowed(item.ntiid, query)
		if not result:
			logger.debug("Content '%s' not allowed for search. %s", item.ntiid, item)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(IAudioTranscriptContent)
class _AudioContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = _is_allowed(item.containerId, query)
		if not result:
			logger.debug("Content '%s' not allowed for search. %s", item.containerId, item)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(IVideoTranscriptContent)
class _VideoContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = _is_allowed(item.containerId, query)
		if not result:
			logger.debug("Content '%s' not allowed for search. %s", item.containerId, item)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(INTICardContent)
class _NTICardContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = _is_allowed(item.containerId, query) and \
				 _is_allowed(item.target_ntiid, query)
		if not result:
			logger.debug("Content '%s' not allowed for search. %s", item.containerId, item)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(ICreated)
class _CreatedContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		resolver = IContainerIDResolver(item, None)
		containerId = resolver.containerId if resolver is not None else None
		result = _is_allowed(containerId, query) if containerId else True
		if not result:
			logger.debug("Content '%s' not allowed for search. %s", containerId, item)
		return result
