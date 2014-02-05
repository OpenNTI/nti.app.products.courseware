#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from time import mktime
from datetime import datetime

from zope import component
from zope import interface

import repoze.lru

from nti.contentlibrary import interfaces as lib_interfaces

from nti.contentsearch import interfaces as search_interfaces

from . import interfaces as course_interfaces

def get_collection_root(ntiid):
	library = component.queryUtility(lib_interfaces.IContentPackageLibrary)
	paths = library.pathToNTIID(ntiid) if library and ntiid else None
	result = paths[0] if paths else None
	return result

def get_node(outline, ntiid):
	ntiid = ntiid.lower()
	def _recur(node):
		if getattr(node, 'ContentNTIID', u'').lower() == ntiid:
			return node
		result = None
		for child in node.values():
			result = _recur(child)
			if result is not None:
				break
		return result

	result = _recur(outline)
	return result

@repoze.lru.lru_cache(500)
def is_allowed(ntiid, now=None):
	now = now or datetime.utcnow()
	root = get_collection_root(ntiid)
	course = course_interfaces.ICourseInstance(root, None)
	if course is not None:
		outline_node = get_node(course.Outline, ntiid)
		if outline_node is not None:
			beginning = getattr(outline_node, 'AvailableBeginning', None) or now
			return mktime(now.timetuple()) >= mktime(beginning.timetuple())
	return True

@interface.implementer(search_interfaces.ISearchHitPredicate)
@component.adapter(search_interfaces.IBookContent)
class _ContentHitPredicate(object):
	
	__slots__ = ()

	def __init__(self, *args):
		pass

	def allow(self, item, score):
		return is_allowed(item.ntiid)

@interface.implementer(search_interfaces.ISearchHitPredicate)
@component.adapter(search_interfaces.IVideoTranscriptContent)
class _VideoContentHitPredicate(object):

	__slots__ = ()

	def __init__(self, *args):
		pass

	def allow(self, item, score):
		return is_allowed(item.containerId)

@interface.implementer(search_interfaces.ISearchHitPredicate)
@component.adapter(search_interfaces.INTICardContent)
class _NTICardContentHitPredicate(object):

	__slots__ = ()

	def __init__(self, *args):
		pass

	def allow(self, item, score):
		return is_allowed(item.containerId) and is_allowed(item.target_ntiid)
