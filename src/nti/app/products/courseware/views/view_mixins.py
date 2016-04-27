#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views directly related to individual courses and course sub-objects.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.recorder import get_transactions

ITEMS = StandardExternalFields.ITEMS
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

class AbstractRecursiveTransactionHistoryView(AbstractAuthenticatedView,
											  BatchingUtilsMixin):

	"""
	An abstract helper class to gather transaction history from course
	outline components, including nodes, lessons, etc. The result is a
	batched set of sorted transactions.

	Params:

	sortOrder - Either 'descending' or 'ascending'; defaults to ascending.
	"""

	_DEFAULT_BATCH_SIZE = 20
	_DEFAULT_BATCH_START = 0

	def _get_items(self):
		"""
		Subclasses should define this.
		"""
		raise NotImplementedError()

	def _get_transactions(self, obj):
		result = ()
		if obj is not None:
			result = get_transactions(obj, sort=False)
		return result

	def __get_number_items_needed(self, total_item_count):
		number_items_needed = total_item_count
		batch_size, batch_start = self._get_batch_size_start()
		if batch_size is not None and batch_start is not None:
			number_items_needed = min(batch_size + batch_start + 2, total_item_count)
		return number_items_needed

	def _accum_lesson_transactions(self, lesson_overview, accum):
		accum.extend(self._get_transactions(lesson_overview))
		for overview_group in lesson_overview.items or ():
			accum.extend(self._get_transactions(overview_group))
			for item in overview_group.items or ():
				accum.extend(self._get_transactions(item))

	def _get_node_items(self, origin_node):
		accum = list()

		def handle_node(node):
			accum.extend(self._get_transactions(node))
			for child in node.values() or ():
				handle_node(child)
			lesson_ntiid = node.LessonOverviewNTIID
			if lesson_ntiid:
				lesson_overview = component.queryUtility(INTILessonOverview,
														 name=lesson_ntiid)
				if lesson_overview is not None:
					self._accum_lesson_transactions(lesson_overview, accum)

		handle_node(origin_node)
		return accum

	@property
	def _sort_desc(self):
		sort_order_param = self.request.params.get('sortOrder', 'ascending')
		return sort_order_param.lower() == 'descending'

	def __call__(self):
		result = LocatedExternalDict()
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context

		items = self._get_items()
		if items:
			result[LAST_MODIFIED] = max((x.createdTime for x in items))
			items.sort(key=lambda t: t.createdTime, reverse=self._sort_desc)
		result['TotalItemCount'] = item_count = len(items)
		# Supply this number to batching to prevent batch-ext links from showing
		# up if we've exhausted our supply.
		number_items_needed = self.__get_number_items_needed(item_count)
		self._batch_items_iterable(result, items, number_items_needed=number_items_needed)
		result['ItemCount'] = len(result.get(ITEMS) or ())
		return result
