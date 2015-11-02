#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.intid import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.assessment.interfaces import ASSESSMENT_INTERFACES

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.recorder.index import IX_LOCKED
from nti.recorder import get_recorder_catalog

from nti.site.site import get_component_hierarchy_names

from nti.zope_catalog.catalog import ResultSet

ITEMS = StandardExternalFields.ITEMS

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   name='SyncLockedObjects',
			   permission=nauth.ACT_NTI_ADMIN)
class CourseSyncLockedObjectsView(AbstractAuthenticatedView):

	def _outline_nodes_uids(self, course, intids):
		result = set()
		def _recur(node):
			if not ICourseOutline.providedBy(node):
				result.add(intids.queryId(node))
			for child in node.values():
				_recur(child)

		outline = course.Outline
		if outline is not None:
			_recur(outline)
		result.discard(None)
		return result

	def _get_course_pacakge_ntiids(self, course):
		try:
			packs = course.ContentPackageBundle.ContentPackages
		except AttributeError:
			packs = (course.legacy_content_package,)
		result = [pack.ntiid for pack in packs]
		return result

	def _has_permission(self, obj):
		return True

	def _get_locked_objects(self, context):
		lib_catalog = get_library_catalog()
		course = ICourseInstance(context)
		entry = ICourseCatalogEntry(context)
		intids = component.getUtility(IIntIds)
		sites = get_component_hierarchy_names()
		pack_ntiids = self._get_course_pacakge_ntiids(course)

		all_ids = lib_catalog.family.IF.LFSet()

		# course outline nodes
		obj_ids = self._outline_nodes_uids(course, intids)
		all_ids.update(obj_ids)

		# presentation assets in course
		obj_ids = lib_catalog.get_references(
								container_ntiids=entry.ntiid,
								provided=ALL_PRESENTATION_ASSETS_INTERFACES,
								sites=sites)
		all_ids.update(obj_ids)

		# presentation assets in packages
		obj_ids = lib_catalog.get_references(
								namespace=pack_ntiids,
								provided=ALL_PRESENTATION_ASSETS_INTERFACES,
								sites=sites)
		all_ids.update(obj_ids)

		# assesments in packages
		obj_ids = lib_catalog.get_references(
								namespace=pack_ntiids,
								provided=ASSESSMENT_INTERFACES,
								sites=sites)

		recorder_catalog = get_recorder_catalog()
		locked_intids = recorder_catalog[IX_LOCKED].apply({'any_of': (True,)})

		doc_ids = recorder_catalog.family.IF.intersection(all_ids, locked_intids)
		result = ResultSet(doc_ids, intids, ignore_invalid=True)
		return result

	def __call__(self):
		result = LocatedExternalDict()
		items = result[ITEMS] = []
		items.extend(self._get_locked_objects(self.context))
		result['Total'] = result['ItemCount'] = len(items)
		return result
