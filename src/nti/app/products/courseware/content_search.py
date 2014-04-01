#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from datetime import datetime

from zope import component
from zope import interface

from pyramid.traversal import find_interface

import repoze.lru

from nti.contentlibrary import interfaces as lib_interfaces

from nti.dataserver import interfaces as nti_interfaces

from nti.contentsearch import interfaces as search_interfaces

from . import interfaces as course_interfaces

def get_paths(ntiid):
	library = component.queryUtility(lib_interfaces.IContentPackageLibrary)
	paths = library.pathToNTIID(ntiid) if library and ntiid else None
	return paths

def get_collection_root(ntiid):
	paths = get_paths(ntiid)
	result = paths[0] if paths else None
	return result

def get_node(outline, ntiids=()):
	def _recur(node):
		content_ntiid = getattr(node, 'ContentNTIID', None) or u''
		if content_ntiid in ntiids:
			return node
		result = None
		for child in node.values():
			result = _recur(child)
			if result is not None:
				break
		return result
	result = _recur(outline)
	return result

def get_ntiid_path(ntiid):
	result = ()
	library = component.queryUtility(lib_interfaces.IContentPackageLibrary)
	if library and ntiid:
		paths = library.pathToNTIID(ntiid)
		result = {p.ntiid for p in paths} if paths else ()
	return result

def _is_allowed(ntiid, course=None, now=None):
	result = True
	if course is not None:
		node = get_node(course.Outline, get_ntiid_path(ntiid))
		if node is not None:
			now = now or datetime.utcnow()
			beginning = getattr(node, 'AvailableBeginning', None) or now
			is_outline_stub_only = getattr(node, 'is_outline_stub_only', False)
			result = not is_outline_stub_only and now >= beginning
	return result

@repoze.lru.lru_cache(1000)
def is_allowed(ntiid, course=None, now=None):
	if course is None:
		root = get_collection_root(ntiid)
		course = course_interfaces.ICourseInstance(root, None)
	return _is_allowed(ntiid, course, now)

class _BasePredicate(object):

	__slots__ = ()

	def __init__(self, *args):
		pass

@interface.implementer(search_interfaces.ISearchHitPredicate)
@component.adapter(search_interfaces.IBookContent)
class _ContentHitPredicate(_BasePredicate):
	
	__slots__ = ()

	def allow(self, item, score):
		return is_allowed(item.ntiid)

@interface.implementer(search_interfaces.ISearchHitPredicate)
@component.adapter(search_interfaces.IVideoTranscriptContent)
class _VideoContentHitPredicate(_BasePredicate):

	__slots__ = ()

	def allow(self, item, score):
		return is_allowed(item.containerId)

@interface.implementer(search_interfaces.ISearchHitPredicate)
@component.adapter(search_interfaces.INTICardContent)
class _NTICardContentHitPredicate(_BasePredicate):

	__slots__ = ()

	def allow(self, item, score):
		return is_allowed(item.containerId) and is_allowed(item.target_ntiid)

@interface.implementer(search_interfaces.ISearchHitPredicate)
@component.adapter(nti_interfaces.ICreated)
class _CreatedContentHitPredicate(_BasePredicate):

	__slots__ = ()

	def allow(self, item, score):
		resolver = search_interfaces.IContainerIDResolver(item, None)
		containerId = resolver.containerId if resolver is not None else None
		if not containerId:
			return True

		# try walk up the tree to see if it gets us to either a CourseInstance
		# or a ContentPackage.
		found = find_interface(item, course_interfaces.ICourseInstance) or \
				find_interface(item, lib_interfaces.IContentPackage)
		course = course_interfaces.ICourseInstance(found, None)
		result = is_allowed(containerId, course)
		return result
