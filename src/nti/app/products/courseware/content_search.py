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

from nti.contentlibrary.indexed_data.interfaces import IAudioIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import IVideoIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import IRelatedContentIndexedDataContainer

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import ICreated

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import TYPE_INTID
from nti.ntiids.ntiids import is_ntiid_of_types
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.utils.property import CachedProperty

ZERO_DATE = datetime.utcfromtimestamp(0)

CONTAINER_IFACES = (IRelatedContentIndexedDataContainer,
					IVideoIndexedDataContainer,
					IAudioIndexedDataContainer)

def _has_content(ntiid, library):
	result = bool(ntiid and \
			 	  not is_ntiid_of_types(ntiid, (TYPE_OID, TYPE_UUID, TYPE_INTID)) and \
			 	  library.pathToNTIID(ntiid))
	return result

def _flatten_outline(outline):
	result = {}
	library = component.queryUtility(IContentPackageLibrary)

	def _indexed_data(iface, result, unit, beginning, is_outline_stub_only):
		container = iface(unit, None)
		if not container:
			return
		for item in container.get_data_items():
			ntiid = item.get('target-ntiid') 
			if not _has_content(ntiid, library):
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

def _get_content_path(course, ntiid):
	pacakge_paths_cache = course._v_csPackagePaths
	result = pacakge_paths_cache.get(ntiid)
	if result is None:
		result = ()
		library = component.queryUtility(IContentPackageLibrary)
		if library and ntiid:
			paths = library.pathToNTIID(ntiid)
			result = tuple(p.ntiid for p in paths) if paths else ()
		pacakge_paths_cache[ntiid] = result
	return result
	
@property	
def _v_csOutlineLastModififed(self):
	return getattr(self.Outline, 'lastModified', 0)

@CachedProperty('_v_csOutlineLastModififed')
def _v_csPackagePaths(self):
	return dict()

@CachedProperty('_v_csOutlineLastModififed')
def _v_csFlattenOutline(self):
	nodes = _flatten_outline(self.Outline)
	return nodes

def _set_course_properties(course):
	clazz = course.__class__
	if not hasattr(clazz, '_v_csOutlineLastModififed'):
		clazz._v_csOutlineLastModififed = _v_csOutlineLastModififed
	if not hasattr(clazz, '_v_csFlattenOutline'):
		clazz._v_csFlattenOutline = _v_csFlattenOutline
	if not hasattr(clazz, '_v_csPackagePaths'):
		clazz._v_csPackagePaths = _v_csPackagePaths

def _check_against_course_outline(course, ntiid, now=None): 
	_set_course_properties(course)
	now = now or datetime.utcnow()
	nodes = course._v_csFlattenOutline 
	ntiids = _get_content_path(course, ntiid)
	for content_ntiid, data in nodes.items():
		beginning, is_outline_stub_only= data
		if content_ntiid in ntiids:
			result = bool(not is_outline_stub_only and now >= beginning)
			return result
	return False
		
def _get_context_course(query):
	context = query.context or {}
	course_id = context.get('course')
	if course_id and is_valid_ntiid_string(course_id):
		course = find_object_with_ntiid(course_id)
		course = ICourseInstance(course, None)
		return course
	return None

def _is_allowed(ntiid, query=None, now=None):
	if query is None:
		return True # allow by default

	course = _get_context_course(query)
	if course is None:
		return True # allow by default

	result = _check_against_course_outline(course, ntiid)
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
@component.adapter(ICreated)
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
