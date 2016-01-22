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

from nti.common.string import TRUE_VALUES
from nti.common.maps import CaseInsensitiveDict

from nti.contenttypes.courses.interfaces import COURSE_OUTLINE_NAME

from nti.contenttypes.courses._outline_parser import outline_nodes
from nti.contenttypes.courses._outline_parser import unregister_nodes
from nti.contenttypes.courses._outline_parser import fill_outline_from_key

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.utils import get_parent_course

from nti.coremetadata.interfaces import IRecordable

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.record import remove_transaction_history

from nti.site.hostpolicy import get_site

from nti.site.interfaces import IHostPolicyFolder

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

def _is_true(v):
	return v and str(v).lower() in TRUE_VALUES

def read_input(request):
	if request.body:
		values = read_body_as_external_object(request)
	else:
		values = request.params
	result = CaseInsensitiveDict(values)
	return result
readInput = read_input

@view_config(name='ResetCourseOutline')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=CourseAdminPathAdapter,
			   permission=nauth.ACT_NTI_ADMIN)
class ResetCourseOutlineView(AbstractAuthenticatedView,
				 			 ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		result = read_input(self.request)
		return result

	def _do_reset(self, course, force, registry=None):
		removed = []
		outline = course.Outline
		registry = component.getSiteManager() if registry is None else registry
		
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

	def _do_call(self, result, courses=None):
		values = self.readInput()
		courses = courses if courses is not None else _parse_courses(values)

		to_process = set()
		items = result[ITEMS] = {}
		force = _is_true(values.get('force'))

		for course in courses or ():
			course = ICourseInstance(course)
			if ILegacyCourseInstance.providedBy(course):
				continue
			if ICourseSubInstance.providedBy(course):
				parent = get_parent_course(course)
				if parent.Outline == course.Outline:
					course = parent
			to_process.add(course)

		for course in to_process:
			folder = find_interface(course, IHostPolicyFolder, strict=False)
			with current_site(get_site(folder.__name__)):
				registry = folder.getSiteManager()
				ntiid = ICourseCatalogEntry(course).ntiid
				items[ntiid] = self._do_reset(course, force, registry)

		return to_process

	def __call__(self):
		now = time.time()
		result = LocatedExternalDict()
		endInteraction()
		try:
			self._do_call(result)
		finally:
			restoreInteraction()
			result['TimeElapsed'] = time.time() - now
		return result

@view_config(name='ResetAllCoursesOutlines')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=CourseAdminPathAdapter,
			   permission=nauth.ACT_NTI_ADMIN)
class ResetAllCoursesOutlinesView(ResetCourseOutlineView):

	def _do_call(self, result, courses=None):
		catalog = component.getUtility(ICourseCatalog)
		courses = list(catalog.iterCatalogEntries())
		return super(ResetAllCoursesOutlinesView, self)._do_call(result, courses)

@view_config(name='UnlockOutlineNodes')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=CourseAdminPathAdapter,
			   permission=nauth.ACT_NTI_ADMIN)
class UnlockOutlineNodesView(AbstractAuthenticatedView,
				 			 ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		result = read_input(self.request)
		return result

	def _do_call(self, result, courses=None):
		values = self.readInput()
		courses = courses if courses is not None else _parse_courses(values)

		to_process = set()
		items = result[ITEMS] = {}
		for course in courses or ():
			course = ICourseInstance(course)
			if ILegacyCourseInstance.providedBy(course):
				continue
			if ICourseSubInstance.providedBy(course):
				parent = get_parent_course(course)
				if parent.Outline == course.Outline:
					course = parent
			to_process.add(course)

		def _recur(node, unlocked):
			if IRecordable.providedBy(node) and node.locked:
				node.locked = False
				unlocked.append(node.ntiid)
			# parse children
			for child in node.values():
				_recur(child, unlocked)

		for course in to_process:
			unlocked = []
			_recur(course.Outline, unlocked)
			items[ICourseCatalogEntry(course).ntiid] = unlocked

		return to_process

	def __call__(self):
		now = time.time()
		result = LocatedExternalDict()
		endInteraction()
		try:
			self._do_call(result)
		finally:
			restoreInteraction()
			result['TimeElapsed'] = time.time() - now
		return result

@view_config(name='UnlockAllOutlineNodes')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=CourseAdminPathAdapter,
			   permission=nauth.ACT_NTI_ADMIN)
class UnlockAllOutlineNodesView(UnlockOutlineNodesView):

	def _do_call(self, result, courses=None):
		catalog = component.getUtility(ICourseCatalog)
		courses = list(catalog.iterCatalogEntries())
		return super(UnlockAllOutlineNodesView, self)._do_call(result, courses)
