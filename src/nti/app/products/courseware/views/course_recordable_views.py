#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import lifecycleevent

from zope.intid.interfaces import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.app.products.courseware import VIEW_RECURSIVE_AUDIT_LOG
from nti.app.products.courseware import VIEW_RECURSIVE_TX_HISTORY

from nti.app.products.courseware.views.view_mixins import AbstractRecursiveTransactionHistoryView

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseAssessmentItemCatalog

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.coremetadata.interfaces import IRecordableContainer

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder import get_recorder_catalog

from nti.recorder.index import IX_LOCKED
from nti.recorder.index import IX_CHILD_ORDER_LOCKED

from nti.site.site import get_component_hierarchy_names

from nti.zope_catalog.catalog import ResultSet

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

class CourseSyncLockedObjectsMixin(object):

	def _outline_nodes_uids(self, course, intids):
		result = set()
		def _recur(node):
			if not ICourseOutline.providedBy(node):
				result.add(intids.queryId(node))
			if ICourseOutlineNode.providedBy(node):
				lesson = find_object_with_ntiid(node.LessonOverviewNTIID or u'')
				result.add(intids.queryId(lesson) if lesson is not None else None)
			for child in node.values():
				_recur(child)

		outline = course.Outline
		if outline is not None:
			_recur(outline)
		result.discard(None)
		return result

	def _get_course_pacakge_ntiids(self, course):
		result = set()
		def _recur(unit):
			for child in unit.children or ():
				_recur(child)
			result.add(unit.ntiid)
		for pack in get_course_packages(course):
			_recur(pack)
		result.discard(None)
		return tuple(result)

	def _compute_locked_objects(self, context):
		lib_catalog = get_library_catalog()
		course = ICourseInstance(context)
		entry = ICourseCatalogEntry(context)
		intids = component.getUtility(IIntIds)
		sites = get_component_hierarchy_names()

		containers = [entry.ntiid]
		containers.extend(self._get_course_pacakge_ntiids(course))

		all_ids = lib_catalog.family.IF.LFSet()

		# course outline nodes
		obj_ids = self._outline_nodes_uids(course, intids)
		all_ids.update(obj_ids)

		# presentation assets in course
		obj_ids = lib_catalog.get_references(
								container_all_of=False,
								container_ntiids=containers,
								provided=ALL_PRESENTATION_ASSETS_INTERFACES,
								sites=sites)
		all_ids.update(obj_ids)

		# assesments in course
		catalog = ICourseAssessmentItemCatalog(course)
		obj_ids = {intids.queryId(item) for item in catalog.iter_assessment_items()}
		obj_ids.discard(None)
		all_ids.update(obj_ids)

		recorder_catalog = get_recorder_catalog()
		locked_intids = recorder_catalog[IX_LOCKED].apply({'any_of': (True,)})
		child_order_locked_intids = recorder_catalog[IX_CHILD_ORDER_LOCKED].apply({'any_of': (True,)})
		all_locked = recorder_catalog.family.IF.multiunion([locked_intids, child_order_locked_intids])

		doc_ids = recorder_catalog.family.IF.intersection(all_ids, all_locked)
		result = ResultSet(doc_ids, intids, ignore_invalid=True)
		return result

	def _get_locked_objects(self, context):
		return list(x for x in self._compute_locked_objects(context)
					if x.isLocked() or (IRecordableContainer.providedBy(x) and x.isChildOrderLocked()))

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   name='SyncLockedObjects',
			   permission=nauth.ACT_CONTENT_EDIT)
class CourseSyncLockedObjectsView(CourseSyncLockedObjectsMixin,
								  AbstractAuthenticatedView,
								  BatchingUtilsMixin):

	_DEFAULT_BATCH_SIZE = 20
	_DEFAULT_BATCH_START = 0

	@property
	def _sort_desc(self):
		sort_order_param = self.request.params.get('sortOrder', 'ascending')
		return sort_order_param.lower() == 'descending'

	def __call__(self):
		result = LocatedExternalDict()
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context
		items = result[ITEMS] = self._get_locked_objects(self.context)
		if items:  # check to sort
			result[LAST_MODIFIED] = max((getattr(x, 'lastModified', 0) for x in items))
			items.sort(key=lambda t: getattr(t, 'lastModified', 0), reverse=self._sort_desc)
			result.lastModified = result[LAST_MODIFIED]

		result['TotalItemCount'] = len(items)
		self._batch_items_iterable(result, items)
		result[ITEM_COUNT] = len(result.get(ITEMS, ()))
		return result

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name='UnlockSyncLockedObjects',
			   permission=nauth.ACT_CONTENT_EDIT)
class UnlockCourseSyncLockedObjectsView(CourseSyncLockedObjectsMixin,
								  		AbstractAuthenticatedView):

	def __call__(self):
		result = LocatedExternalDict()
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context
		items = result[ITEMS] = []
		for item in self._get_locked_objects(self.context):
			if item.isLocked():
				item.unlock()
			if IRecordableContainer.providedBy(item) and item.isChildOrderLocked():
				item.childOrderUnlock()
			items.append(item.ntiid)
			lifecycleevent.modified(item)
		result[TOTAL] = result[ITEM_COUNT] = len(items)
		return result

@view_config(name=VIEW_RECURSIVE_AUDIT_LOG)
@view_config(name=VIEW_RECURSIVE_TX_HISTORY)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_CONTENT_EDIT,
			   context=ICourseInstance)
class RecursiveCourseTransactionHistoryView(AbstractRecursiveTransactionHistoryView):
	"""
	A batched view to get all edits that have occurred in the course
	hierarchy, recursively.
	"""

	def _get_items(self):
		return self._get_node_items(self.context.Outline)
