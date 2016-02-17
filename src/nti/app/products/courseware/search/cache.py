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

from zope.component.hooks import getSite

from zope.intid.interfaces import IIntIds

from pyramid.threadlocal import get_current_request

from nti.app.products.courseware.search import encode_keys
from nti.app.products.courseware.search import memcache_get
from nti.app.products.courseware.search import memcache_set
from nti.app.products.courseware.search import memcache_client
from nti.app.products.courseware.search import last_synchronized
from nti.app.products.courseware.search.interfaces import ICourseOutlineCache

from nti.app.products.courseware.utils import ZERO_DATETIME

from nti.common.property import Lazy

from nti.contentlibrary.indexed_data import get_library_catalog
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import get_course_packages
from nti.contenttypes.courses.utils import is_course_instructor

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation import PACKAGE_CONTAINER_INTERFACES
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.users import User

from nti.ntiids.ntiids import ROOT
from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import TYPE_UUID
from nti.ntiids.ntiids import TYPE_INTID
from nti.ntiids.ntiids import is_ntiid_of_types
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.site import get_component_hierarchy_names

# memcache

def _encode(*keys):
	return '/search/%s' % encode_keys(*keys)

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

def get_lesson_package_assets(lesson):
	result = []
	for group in lesson:
		for item in group:
			provided = iface_of_asset(item)
			if provided in PACKAGE_CONTAINER_INTERFACES:
				result.append(item)
	return result

def _index_node_data(node, result=None):
	result = {} if result is None else result

	# cache initial values
	contentNTIID = node.ContentNTIID
	if not contentNTIID:
		return result # pragma no cover

	beginning = node.AvailableBeginning or ZERO_DATETIME
	is_outline_stub_only = getattr(node, 'is_outline_stub_only', None) or False
	result[contentNTIID] = (beginning, is_outline_stub_only)

	library = component.queryUtility(IContentPackageLibrary)
	if library is None:
		return result # pragma no cover

	# loop through container interfaces
	paths = library.pathToNTIID(contentNTIID)
	unit = paths[-1] if paths else None
	if unit is not None:
		catalog = get_library_catalog()
		intids = component.getUtility(IIntIds)
		sites = get_component_hierarchy_names()
		package_assets =  catalog.search_objects(sites=sites,
												 container_ntiids=(unit.ntiid,),
									  			 provided=PACKAGE_CONTAINER_INTERFACES,
									   			 intids=intids)
	else:
		context = find_object_with_ntiid(contentNTIID)
		if INTILessonOverview.providedBy(context):
			package_assets = get_lesson_package_assets(context)
		else:
			package_assets = ()

	for item in package_assets:
		# Make sure we get both target and ntiid.
		for name in ('target', 'ntiid'):
			check_ntiid = getattr(item, name, None)
			if _check_ntiid(check_ntiid):
				ntiid = check_ntiid
				if ntiid not in result:
					result[ntiid] = (beginning, is_outline_stub_only)
				else:
					_begin, _stub = result[ntiid]
					_begin = max(beginning, _begin)  # max date
					_stub = is_outline_stub_only or _stub  # stub true
					result[ntiid] = (_begin, _stub)
	return result

def _outline_lastModified(context):
	course = ICourseInstance(context, None)
	outline = course.Outline if course is not None else None
	return outline.lastModified if outline is not None else 0

def _flatten_outline(outline):
	result = {}
	for node in _outline_nodes(outline):
		_index_node_data(node, result)
	return result

def _course_timestamp(context=None):
	context = ICourseInstance(context, None)
	result = max(last_synchronized(context), _outline_lastModified(context))
	return result

def _flatten_and_cache_outline(course, client=None):
	cached = True
	site = getSite().__name__
	lastSync = _course_timestamp(course)
	ntiid = ICourseCatalogEntry(course).ntiid

	# flatter and cache
	result = _flatten_outline(course.Outline)
	for key, value in result.items():
		key = _encode(site, ntiid, "outline", key, lastSync)
		cached = cached and memcache_set(key, value, client=client)

	# add main course pkg ntiids
	for pkg in get_course_packages(course):
		key = _encode(site, ntiid, "outline", pkg.ntiid, lastSync)
		cached = cached and memcache_set(key, (ZERO_DATETIME, False), client=client)

	# mark as cached
	key = _encode(site, ntiid, "outline", "cached", lastSync)
	cached = cached and memcache_set(key, 1, client=client)

	# return data and flag
	return result, cached

def _is_outline_cached(course, entry, client=None):
	site = getSite().__name__
	lastSync = _course_timestamp(course)
	key = _encode(site, entry, "outline", "cached", lastSync)
	return memcache_get(key, client) == 1

def _get_outline_cache_entry(ntiid, course, entry=None, client=None):
	result = None
	request = get_current_request()
	local = getattr(request, '_v_flatten_outline', None)
	if local is not None:
		result = local.get(ntiid)
	else:
		entry = ICourseCatalogEntry(course).ntiid if not entry else entry
		if not _is_outline_cached(course, entry, client):
			data, cached = _flatten_and_cache_outline(course, client)
			if not cached:
				if request is not None:
					setattr(request, '_v_flatten_outline', data)
			result = data.get(ntiid) if data is not None else None
		else:
			site = getSite().__name__
			lastSync = _course_timestamp(course)
			key = _encode(site, entry, "outline", ntiid, lastSync)
			result = memcache_get(key, client)
	return result

# content paths

def _get_content_path(ntiid, lastSync=None, client=None):
	site = getSite().__name__
	lastSync = last_synchronized() if lastSync is None else lastSync
	key = _encode(site, "pacakge_paths", ntiid, lastSync)
	result = memcache_get(key, client=client)
	if result is None:
		library = component.queryUtility(IContentPackageLibrary)
		if library and ntiid:
			paths = library.pathToNTIID( ntiid )
			result = tuple(p.ntiid for p in paths) if paths else ()
		result = result or (ntiid,)
		memcache_set(key, result, client=client)
	return result

# search query

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

@interface.implementer(ICourseOutlineCache)
class _CourseOutlineCache(object):

	@Lazy
	def memcache(self):
		return memcache_client()

	def _check_against_course_outline(self, entry, course, ntiid, now=None):
		ntiids = _get_content_path(ntiid, _course_timestamp(course), self.memcache)
		for ntiid in ntiids or ():
			data = _get_outline_cache_entry(ntiid, course, entry, client=self.memcache)
			if data:
				beginning, is_outline_stub_only = data
				beginning = beginning or ZERO_DATETIME
				if 	bool(not is_outline_stub_only) and \
					datetime.utcnow() >= beginning:
					return True
		return False # no match set false

	def is_allowed(self, ntiid, query=None, now=None):
		if query is None:
			return True  # allow by default

		username = query.username if query is not None else None
		user = User.get_user(username or u'')
		if not user:
			return False

		course, entry = _get_course_from_search_query(query)
		if course is None or not entry or is_course_instructor(course, user):
			return True  # allow by default
		if not is_enrolled(course, user):
			return False  # check has access
		result = self._check_against_course_outline(entry, course, ntiid)
		return result
