#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import hashlib
from datetime import datetime

import repoze.lru

from brownie.caching import LFUCache

from zope import component
from zope import interface

from zope.component.hooks import getSite

from zope.container.contained import Contained

from zope.intid import IIntIds

from zope.traversing.interfaces import IEtcNamespace

from nti.common.property import CachedProperty, Lazy

from nti.contentlibrary.indexed_data import get_catalog
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.presentation.interfaces import INTIAudio 
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTISlideDeck
	
from nti.dataserver.users import User
from nti.dataserver.interfaces import IMemcacheClient

from nti.ntiids.ntiids import ROOT
from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import TYPE_INTID
from nti.ntiids.ntiids import is_ntiid_of_types
from nti.ntiids.ntiids import find_object_with_ntiid

from ..utils import is_enrolled
from ..utils import ZERO_DATETIME

from .interfaces import ICourseOutlineCache

def last_synchronized():
	hostsites = component.queryUtility(IEtcNamespace, name='hostsites')
	result = getattr(hostsites, 'lastSynchronized', 0)
	return result
	
# memcache
	
EXP_TIME = 86400

def _memcache_client():
	return component.queryUtility(IMemcacheClient)

def _memcache_get(key, client=None):
	client = component.queryUtility(IMemcacheClient) if client is None else client
	if client is not None:
		try:
			return client.get(key)
		except:
			pass
	return None

def _memcache_set(key, value, client=None, exp=EXP_TIME):
	client = component.queryUtility(IMemcacheClient) if client is None else client
	if client is not None:
		try:
			client.set(key, value, time=exp)
			return True
		except:
			pass
	return False

@repoze.lru.lru_cache(100)
def _encode_keys(*keys):
	result = hashlib.md5()
	for key in keys:
		result.update(str(key).lower())
	return result.hexdigest()

# outline

def _check_ntiid(ntiid):
	result = ntiid and not is_ntiid_of_types(ntiid, (TYPE_OID, TYPE_UUID, TYPE_INTID))
	return bool(result)

def _outline_nodes(outline):
	result = []
	def _recur(node):
		if ICourseOutlineContentNode.providedBy(node) and node.ContentNTIID:
			result.append(node)
		for child in node.values():
			_recur(child)
	if outline is not None:
		_recur(outline)
	return result

def _index_node_data(node, result=None):
	result = {} if result is None else result
	
	# cache initial values
	contentNTIID = node.ContentNTIID
	beginning = node.AvailableBeginning or ZERO_DATETIME
	is_outline_stub_only = getattr(node, 'is_outline_stub_only', None) or False
	result[contentNTIID] = (beginning, is_outline_stub_only)

	library = component.queryUtility(IContentPackageLibrary)
	if library is None:
		return result

	catalog = get_catalog()
	intids = component.getUtility(IIntIds)

	# loop through container interfaces
	paths = library.pathToNTIID(contentNTIID)
	unit = paths[-1] if paths else None
	for item in catalog.search_objects(container_ntiids=(unit.ntiid,),
									   provided=(INTIVideo, INTIAudio, INTISlideDeck),
									   intids=intids):
		ntiid = None
		for name in ('target', 'ntiid'):
			check_ntiid = getattr(item, name, None)
			if _check_ntiid(check_ntiid):
				ntiid = check_ntiid
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
	return result

def _flatten_outline(outline):
	result = {}
	for node in _outline_nodes(outline):
		_index_node_data(node, result)
	return result

# content paths

def _get_content_path(ntiid, lastSync=None, client=None):
	lastSync = last_synchronized() if not lastSync else lastSync
	key = _encode_keys(getSite().__name__, "search", "pacakge_paths", ntiid, lastSync)
	result = _memcache_get(key, client=client)
	if result is None:
		result = ()
		library = component.queryUtility(IContentPackageLibrary)
		if library and ntiid:
			paths = library.pathToNTIID(ntiid)
			result = tuple(p.ntiid for p in paths) if paths else ()
		else:
			result = (ntiid,)
		_memcache_set(key, result, client=client)
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
		return last_synchronized()

	@Lazy
	def memcache(self):
		return _memcache_client()

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
		ntiids = _get_content_path(ntiid, self.lastSynchronized, self.memcache)
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

		username = query.username if query is not None else None
		user = User.get_user(username or u'')
		if not user:
			return False

		course, course_id = _get_course_from_search_query(query)
		if course is None or course_id is None:
			return True  # allow by default
		if not is_enrolled(course, user):
			return False  # check has access

		result = self._check_against_course_outline(course_id, course, ntiid)
		return result
