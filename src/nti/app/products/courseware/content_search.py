#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from datetime import datetime

from brownie.caching import LFUCache

from zope import component
from zope import interface

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contentsearch.interfaces import IBookContent
from nti.contentsearch.interfaces import INTICardContent
from nti.contentsearch.interfaces import ISearchHitPredicate
from nti.contentsearch.interfaces import IContainerIDResolver
from nti.contentsearch.interfaces import IAudioTranscriptContent
from nti.contentsearch.interfaces import IVideoTranscriptContent

from nti.contentlibrary.indexed_data.interfaces import IAudioIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import IVideoIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import ITimelineIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import IRelatedContentIndexedDataContainer

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import TYPE_INTID
from nti.ntiids.ntiids import is_ntiid_of_types
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

ZERO_DATE = datetime.utcfromtimestamp(0)

CONTAINER_IFACES = (IRelatedContentIndexedDataContainer,
					ITimelineIndexedDataContainer,
					IVideoIndexedDataContainer,
					IAudioIndexedDataContainer)

def _check_ntiid(ntiid):
	result = ntiid and not is_ntiid_of_types(ntiid, (TYPE_OID, TYPE_UUID, TYPE_INTID))
	return bool(result)

def _flatten_outline(outline):
	result = {}
	library = component.queryUtility(IContentPackageLibrary)

	def _indexed_data(iface, result, unit, beginning, is_outline_stub_only):
		container = iface(unit, None)
		if not container:
			return
		for item in container.get_data_items():
			ntiid = None
			for name in ('target-ntiid', 'ntiid'):
				t_ntiid = item.get(name)
				if _check_ntiid(t_ntiid):
					ntiid = t_ntiid
					break
			if not ntiid:
				continue
			if ntiid not in result:	
				result[ntiid] = (beginning, is_outline_stub_only)
			else:
				_begin, _stub = result[ntiid]
				_begin = max(beginning, _begin) 		# max date
				_stub = is_outline_stub_only or _stub	# stub true
				result[ntiid] = (_begin, _stub)
				
	def _recur(node, result):
		content_ntiid = getattr(node, 'ContentNTIID', None)
		if content_ntiid:
			beginning = getattr(node, 'AvailableBeginning', None) or ZERO_DATE
			is_outline_stub_only = getattr(node, 'is_outline_stub_only', None) or False
			result[content_ntiid] = (beginning, is_outline_stub_only)
			# parse any container data
			if library is not None:
				paths = library.pathToNTIID(content_ntiid)
				unit = paths[-1] if paths else None
				for iface in CONTAINER_IFACES:
					_indexed_data(iface, result, unit, beginning, is_outline_stub_only)
					
		# parse children
		for child in node.values():
			_recur(child, result)
	_recur(outline, result)
	return result

def _get_content_path(pacakge_paths_cache, ntiid):
	result = pacakge_paths_cache.get(ntiid)
	if result is None:
		result = ()
		library = component.queryUtility(IContentPackageLibrary)
		if library and ntiid:
			paths = library.pathToNTIID(ntiid)
			result = tuple(p.ntiid for p in paths) if paths else ()
		pacakge_paths_cache[ntiid] = result
	return result

class _OutlineCacheEntry(object):
	
	__slots__ = ('ntiid', 'cPackagePaths', 'csFlattenOutline', 'lastSynchronized')
	
	def __init__(self , ntiid, lastSynchronized=None):
		self.ntiid = ntiid
		self.cPackagePaths = None
		self.csFlattenOutline = None
		self.lastSynchronized = lastSynchronized

	def _v_checkLastSynchronized(self, course):
		courseLastSynchronized = course.lastSynchronized
		if self.lastSynchronized != courseLastSynchronized:
			self.cPackagePaths = None
			self.csFlattenOutline = None
			self.lastSynchronized = courseLastSynchronized
		
	def _v_csPackagePaths(self, course):
		self._v_checkLastSynchronized(course)
		if self.cPackagePaths is None:
			self.cPackagePaths = dict()
		return self.cPackagePaths

	def _v_csFlattenOutline(self, course):
		self._v_checkLastSynchronized(course)
		if self.csFlattenOutline is None:
			self.csFlattenOutline = _flatten_outline(course.Outline)
		return self.csFlattenOutline
	
## Cache size
max_cache_size = 10

## CS: We cache the outline nodes item ntiids of a course
## we only keep the [max_cache_size] most used items. 
outline_cache = LFUCache(maxsize=max_cache_size)

def _get_cached_entry(course_id):
	entry = outline_cache.get(course_id)
	if entry is None:
		entry = outline_cache[course_id] = _OutlineCacheEntry(course_id)
	return entry
	
def _check_against_course_outline(course_id, course, ntiid, now=None): 
	# get/prepare cache entry
	entry = _get_cached_entry(course_id)
	nodes = entry._v_csFlattenOutline(course)
	pacakge_paths_cache = entry._v_csPackagePaths(course)
	ntiids = _get_content_path(pacakge_paths_cache, ntiid) or (ntiid,)
	# perform checking
	for content_ntiid, data in nodes.items():
		_, is_outline_stub_only= data
		if content_ntiid in ntiids:
			result = bool(not is_outline_stub_only)
			return result
	return False
		
def _get_context_course(query):
	context = query.context or {}
	course_id = context.get('course')
	if course_id and is_valid_ntiid_string(course_id):
		course = find_object_with_ntiid(course_id)
		course = ICourseInstance(course, None)
		return course, course_id
	return None, None

def _is_allowed(ntiid, query=None, now=None):
	if query is None:
		return True # allow by default

	course, course_id = _get_context_course(query)
	if course is None:
		return True # allow by default

	result = _check_against_course_outline(course_id, course, ntiid)
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
			logger.debug("Content ('%s') in container '%s' not allowed for search.", 
						 item.title, item.ntiid)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(IAudioTranscriptContent)
class _AudioContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = _is_allowed(item.containerId, query)
		if not result:
			logger.debug("AudioContent ('%s') in container '%s' not allowed for search.", 
						 item.title, item.containerId)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(IVideoTranscriptContent)
class _VideoContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = _is_allowed(item.containerId, query)
		if not result:
			logger.debug("VideoContent ('%s') in container '%s' not allowed for search.", 
						 item.title, item.containerId)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(INTICardContent)
class _NTICardContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = _is_allowed(item.containerId, query) and \
				 _is_allowed(item.target_ntiid, query)
		if not result:
			logger.debug("NTICardContent ('%s') in container '%s' not allowed for search.",
						 item.title, item.containerId)
		return result

@interface.implementer(ISearchHitPredicate)
class _CreatedContentHitPredicate(_BasePredicate):

	def _is_allowed(self, containerId, query):
		return bool(not containerId or \
					is_ntiid_of_types(containerId, (TYPE_OID,)) or \
					_is_allowed(containerId, query))
			
	def allow(self, item, score, query=None):
		resolver = IContainerIDResolver(item, None)
		containerId = resolver.containerId if resolver is not None else None
		result = self._is_allowed(containerId, query)
		if not result:
			logger.debug("Object (%s) in container '%s' not allowed for search.",
						 item, containerId)
		return result
