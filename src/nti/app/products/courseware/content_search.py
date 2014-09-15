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

_package_path_cache = None
def _get_content_path(ntiid):
	global _package_path_cache
	if _package_path_cache is None:
		_package_path_cache = {}
		
	result = _package_path_cache.get(ntiid)
	if result is None:
		result = ()
		library = component.queryUtility(IContentPackageLibrary)
		if library and ntiid:
			paths = library.pathToNTIID(ntiid)
			result = tuple(p.ntiid for p in paths) if paths else ()
		_package_path_cache[ntiid] = result
	return result

def _flatten_outline(outline):
	result = {}
	def _recur(node, result):
		content_ntiid = getattr(node, 'ContentNTIID', None)
		if content_ntiid:
			beginning = getattr(node, 'AvailableBeginning', None) 
			is_outline_stub_only = getattr(node, 'is_outline_stub_only', False)
			result[content_ntiid] = (beginning, is_outline_stub_only)

		for child in node.values():
			_recur(child, result)
	_recur(outline, result)
	return result

_course_nodes_cache = None
def _check_against_course_outline(course_id, ntiid, now=None): 
	global _course_nodes_cache
	if _course_nodes_cache is None:
		_course_nodes_cache = {}
		
	nodes = _course_nodes_cache.get(course_id)
	if nodes is None:
		course = find_object_with_ntiid(course_id)
		if not course or not ICourseInstance.providedBy(course):
			return True
		nodes = _flatten_outline(course.Outline)
		_course_nodes_cache[course_id] = nodes
		
	now = now or datetime.utcnow()
	ntiids = _get_content_path(ntiid)
	for content_ntiid, data in nodes.items():
		beginning = data[0] or now
		is_outline_stub_only = data[1]
		if content_ntiid in ntiids:
			result = bool(not is_outline_stub_only and now >= beginning)
			return result
	return True
		
def _is_allowed(ntiid, query=None, now=None):
	if query is None:
		return True # allow by default

	context = query.context or {}
	course_id = context.get('course')
	if not course_id or not is_valid_ntiid_string(course_id):
		return True # allow by default
		
	result = _check_against_course_outline(course_id, ntiid)
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
