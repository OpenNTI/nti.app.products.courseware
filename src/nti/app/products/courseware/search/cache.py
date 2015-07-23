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

from zope.container.contained import Contained

from zope.traversing.interfaces import IEtcNamespace

from nti.common.property import CachedProperty

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.indexed_data.interfaces import CONTAINER_IFACES

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.ntiids.ntiids import ROOT
from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import TYPE_INTID
from nti.ntiids.ntiids import is_ntiid_of_types
from nti.ntiids.ntiids import find_object_with_ntiid

from ..utils import ZERO_DATETIME

from .interfaces import ICourseOutlineCache

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
		for item in container.values():
			ntiid = None
			for name in ('target', 'ntiid'):
				t_ntiid = getattr(item, name, None)
				if _check_ntiid(t_ntiid):
					ntiid = t_ntiid
					break
			if not ntiid:
				continue
			if ntiid not in result:
				result[ntiid] = (beginning, is_outline_stub_only)
			else:
				_begin, _stub = result[ntiid]
				_begin = max(beginning, _begin)  # max date
				_stub = is_outline_stub_only or _stub  # stub true
				result[ntiid] = (_begin, _stub)

	def _recur(node, result):
		content_ntiid = getattr(node, 'ContentNTIID', None)
		if content_ntiid:
			beginning = getattr(node, 'AvailableBeginning', None) or ZERO_DATETIME
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

	if outline is not None:
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

def _get_course_from_search_query(query):
	context = query.context or {}
	for course_id in (query.origin, context.get('course')):
		if not course_id or course_id == ROOT:
			continue
		course = find_object_with_ntiid(course_id)
		course = ICourseInstance(course, None)
		entry = ICourseCatalogEntry(course, None)
		if entry is not None:
			course_id = entry.ntiid
			return course, course_id
	return None, None

class _OutlineCacheEntry(Contained):

	def __init__(self , ntiid):
		self.ntiid = ntiid

	@property
	def lastSynchronized(self):
		result = self.__parent__.lastSynchronized
		return result

	@property
	def Outline(self):
		context = find_object_with_ntiid(self.ntiid)
		course = ICourseInstance(context, None)
		return course.Outline if course is not None else None

	@CachedProperty('lastSynchronized')
	def csPackagePaths(self):
		return dict()

	@CachedProperty('lastSynchronized')
	def csFlattenOutline(self):
		result = _flatten_outline(self.Outline)
		return result

@interface.implementer(ICourseOutlineCache)
class _CourseOutlineCache(object):

	max_cache_size = 10

	def __init__(self, *args):
		self.outline_cache = LFUCache(maxsize=self.max_cache_size)

	@property
	def lastSynchronized(self):
		hostsites = component.queryUtility(IEtcNamespace, name='hostsites')
		result = getattr(hostsites, 'lastSynchronized', 0)
		return result

	def _get_cached_entry(self, ntiid):
		entry = self.outline_cache.get(ntiid)
		if entry is None:
			entry = _OutlineCacheEntry(ntiid)
			entry.__parent__ = self
			self.outline_cache[ntiid] = entry
		return entry

	def _check_against_course_outline(self, course_id, course, ntiid, now=None):
		entry = self._get_cached_entry(course_id)
		nodes = entry.csFlattenOutline
		pacakge_paths_cache = entry.csPackagePaths
		ntiids = _get_content_path(pacakge_paths_cache, ntiid) or (ntiid,)
		# perform checking
		for content_ntiid, data in nodes.items():
			beginning, is_outline_stub_only = data
			if content_ntiid in ntiids:
				beginning = beginning or ZERO_DATETIME
				result = bool(not is_outline_stub_only) and \
						 datetime.utcnow() >= beginning
				return result
		return True  # no match then allow

	def is_allowed(self, ntiid, query=None, now=None):
		if query is None:
			return True  # allow by default

		course, course_id = _get_course_from_search_query(query)
		if course is None or course_id is None:
			return True  # allow by default

		result = self._check_against_course_outline(course_id, course, ntiid)
		return result
