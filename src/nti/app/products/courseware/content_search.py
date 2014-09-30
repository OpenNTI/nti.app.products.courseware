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

from nti.utils.property import CachedProperty

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

def _check_against_course_outline(course_id, ntiid, now=None): 
	course = find_object_with_ntiid(course_id)
	if not ICourseInstance.providedBy(course):
		return True
	_set_course_properties(course)
	now = now or datetime.utcnow()
	nodes = course._v_csFlattenOutline 
	ntiids = _get_content_path(course, ntiid)
	for content_ntiid, data in nodes.items():
		beginning = data[0] or now
		is_outline_stub_only = data[1]
		if content_ntiid in ntiids:
			result = bool(not is_outline_stub_only and now >= beginning)
			return result
	return False
		
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
