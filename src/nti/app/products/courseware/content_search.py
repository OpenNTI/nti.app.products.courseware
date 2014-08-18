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
from nti.contentlibrary.indexed_data.interfaces import IAudioIndexedDataContainer
from nti.contentlibrary.indexed_data.interfaces import IVideoIndexedDataContainer

from nti.contentsearch.interfaces import IBookContent
from nti.contentsearch.interfaces import INTICardContent
from nti.contentsearch.interfaces import ISearchHitPredicate
from nti.contentsearch.interfaces import IContainerIDResolver
from nti.contentsearch.interfaces import IAudioTranscriptContent
from nti.contentsearch.interfaces import IVideoTranscriptContent

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import ICreated

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

def find_content_path_from_ntiid(name):
	libray = component.queryUtility(IContentPackageLibrary)
	if not libray or not name or not name.startswith('tag:'):
		return None

	# find a content unit library
	path = libray.pathToNTIID(name)
	if path:
		return path

	# search media containers
	ifaces = (IAudioIndexedDataContainer, IVideoIndexedDataContainer)
	def _search(unit):
		for iface in ifaces:
			if iface(unit).contains_data_item_with_ntiid(name):
				return libray.pathToNTIID(unit.ntiid)

		for child in unit.children:
			result = _search(child)
			if result:
				return result

	for package in libray.contentPackages:
		result = _search(package)
		if result:
			return result

	# finally embedded nttiids
	paths = libray.pathsToEmbeddedNTIID(name)
	if paths:
		return paths[0]

def _find_course_and_unit_by_ntiid(name):
	"""
	Return an arbitrary course associated with the content ntiid
	"""
	course = None
	path = find_content_path_from_ntiid(name)
	for unit in reversed(path or ()):
		# The adapter function here is where the arbitraryness comes in
		course = ICourseInstance(unit, None)
		if course is not None:
			return course, unit
	return None, None

def _is_allowed(ntiid, now=None):
	# always allow
	result = True

	# find course and unit
	course, unit = _find_course_and_unit_by_ntiid(ntiid)

	# if we found a course check its outline
	if ICourseInstance.providedBy(course):
		ntiids = _get_content_path(ntiid) if unit is None else (unit.ntiid,)
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
		result = _is_allowed(item.ntiid)
		if not result:
			logger.debug("Content '%s' not allowed for search. %s", item.ntiid, item)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(IAudioTranscriptContent)
class _AudioContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = _is_allowed(item.containerId)
		if not result:
			logger.debug("Content '%s' not allowed for search. %s", item.containerId, item)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(IVideoTranscriptContent)
class _VideoContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = _is_allowed(item.containerId)
		if not result:
			logger.debug("Content '%s' not allowed for search. %s", item.containerId, item)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(INTICardContent)
class _NTICardContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		result = _is_allowed(item.containerId) and _is_allowed(item.target_ntiid)
		if not result:
			logger.debug("Content '%s' not allowed for search. %s", item.containerId, item)
		return result

@interface.implementer(ISearchHitPredicate)
@component.adapter(ICreated)
class _CreatedContentHitPredicate(_BasePredicate):

	def allow(self, item, score, query=None):
		resolver = IContainerIDResolver(item, None)
		containerId = resolver.containerId if resolver is not None else None
		result = _is_allowed(containerId) if containerId else True
		if not result:
			logger.debug("Content '%s' not allowed for search. %s", containerId, item)
		return result
