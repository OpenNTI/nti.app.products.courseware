#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import time

from zope import component

from zope.component.hooks import site as current_site

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.internalization import read_body_as_external_object
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.common.maps import CaseInsensitiveDict

from nti.common.string import is_true

from nti.contenttypes.courses.interfaces import COURSE_OUTLINE_NAME

from nti.contenttypes.courses._outline_parser import outline_nodes
from nti.contenttypes.courses._outline_parser import unregister_nodes
from nti.contenttypes.courses._outline_parser import fill_outline_from_key

from nti.contenttypes.courses.interfaces import iface_of_node
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.utils import get_parent_course

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.intid.common import removeIntId

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.record import remove_transaction_history

from nti.site.hostpolicy import get_host_site

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import unregisterUtility

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS

def _parse_courses(values):
	ntiids = values.get('ntiid') or values.get('ntiids')
	if not ntiids:
		raise hexc.HTTPUnprocessableEntity(detail='No course entry identifier')

	if isinstance(ntiids, six.string_types):
		ntiids = ntiids.split()

	result = list()
	for ntiid in ntiids:
		context = find_object_with_ntiid(ntiid)
		context = ICourseInstance(context, None)
		if context is not None:
			result.append(context)
	return result

def _parse_course(values):
	result = _parse_courses(values)
	if not result:
		raise hexc.HTTPUnprocessableEntity(detail='Course not found')
	return result[0]

def read_input(request):
	if request.body:
		values = read_body_as_external_object(request)
	else:
		values = request.params
	result = CaseInsensitiveDict(values)
	return result
readInput = read_input

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_NTI_ADMIN,
			   name="ResetCourseOutline")
class ResetCourseOutlineView(AbstractAuthenticatedView,
				 			 ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		result = read_input(self.request)
		return result

	def _do_reset(self, course, registry, force):
		removed = []
		outline = course.Outline

		# unregister nodes
		removed.extend(unregister_nodes(outline,
										registry=registry,
										force=force))
		for node in removed:
			remove_transaction_history(node)

		outline.reset()
		ntiid = ICourseCatalogEntry(course).ntiid
		logger.info("%s node(s) removed from %s", len(removed), ntiid)

		root = course.root
		outline_xml_node = None
		outline_xml_key = root.getChildNamed(COURSE_OUTLINE_NAME)
		if not outline_xml_key:
			if course.ContentPackageBundle:
				for package in course.ContentPackageBundle.ContentPackages:
					outline_xml_key = package.index
					outline_xml_node = 'course'
					break

		fill_outline_from_key(course.Outline,
						  	  outline_xml_key,
						  	  registry=registry,
						  	  xml_parent_name=outline_xml_node,
						  	  force=force)

		result = {}
		registered = [x.ntiid for x in outline_nodes(course.Outline)]
		result['Registered'] = registered
		result['RemovedCount'] = len(removed)
		result['RegisteredCount'] = len(registered)
		logger.info("%s node(s) registered for %s", len(registered), ntiid)
		return result

	def _do_context(self, context, items):
		values = self.readInput()
		force = is_true(values.get('force'))

		course = ICourseInstance(context)
		if ILegacyCourseInstance.providedBy(course):
			return ()

		if ICourseSubInstance.providedBy(course):
			parent = get_parent_course(course)
			if parent.Outline == course.Outline:
				course = parent

		folder = find_interface(course, IHostPolicyFolder, strict=False)
		with current_site(get_host_site(folder.__name__)):
			registry = folder.getSiteManager()
			result = self._do_reset(course, registry, force)
			
		entry = ICourseCatalogEntry(context, None)
		if entry is not None:
			items[entry.ntiid] = result

		return result

	def __call__(self):
		now = time.time()
		result = LocatedExternalDict()
		items = result[ITEMS] = {}
		endInteraction()
		try:
			self._do_context(self.context, items)
		finally:
			restoreInteraction()
			result['TimeElapsed'] = time.time() - now
		return result

@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name='ResetAllCoursesOutlines',
			   permission=nauth.ACT_NTI_ADMIN)
class ResetAllCoursesOutlinesView(ResetCourseOutlineView):

	def _unregisterSite(self, name):
		count = 0
		with current_site(get_host_site(name)):
			registry = component.getSiteManager()
			for ntiid, node in list(registry.getUtilitiesFor(ICourseOutlineNode)):
				if unregisterUtility(registry,
								  	 name=ntiid,
						 		  	 provided=iface_of_node(node)):
					count += 1
					removeIntId(node)
		return count
	
	def _unregisterAll(self):
		"""
		Remove all outline nodes from all registries
		"""
		count = 0
		for name in get_component_hierarchy_names():
			count += self._unregisterSite(name)
		logger.info("%s node(s) unregistered", count)
	
	def __call__(self):
		now = time.time()
		result = LocatedExternalDict()
		items = result[ITEMS] = {}
		endInteraction()
		try:
			self._unregisterAll()
			catalog = component.getUtility(ICourseCatalog)
			for context in list(catalog.iterCatalogEntries()):
				self._do_context(context, items)
		finally:
			restoreInteraction()
			result['TimeElapsed'] = time.time() - now
		return result
