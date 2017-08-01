#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views directly related to individual courses and course sub-objects.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from requests.structures import CaseInsensitiveDict

from pyramid import httpexceptions as hexc

from zope import component

from zope.event import notify

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import MessageFactory as _

from nti.app.publishing import TRX_TYPE_PUBLISH
from nti.app.publishing import TRX_TYPE_UNPUBLISH

from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.record import get_transactions

ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT
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
    _FILTER_NODE_TYPES = (TRX_TYPE_PUBLISH, TRX_TYPE_UNPUBLISH)

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
            number_items_needed = min(
                batch_size + batch_start + 2, total_item_count)
        return number_items_needed

    def _accum_lesson_transactions(self, lesson_overview, accum):
        accum.extend(self._get_transactions(lesson_overview))
        for overview_group in lesson_overview or ():
            accum.extend(self._get_transactions(overview_group))
            for item in overview_group or ():
                item = IConcreteAsset(item, item)
                accum.extend(self._get_transactions(item))

    def _filter_node_transactions(self, transactions):
        # Exclude publish/unpublish node events, since these are essential
        # dupes of lesson publish/unpublish.
        for transaction in transactions:
            if transaction.type not in self._FILTER_NODE_TYPES:
                yield transaction

    def _get_node_items(self, origin_node):
        accum = list()

        def handle_node(node):
            node_transactions = self._get_transactions(node)
            node_transactions = self._filter_node_transactions(
                node_transactions)
            accum.extend(node_transactions)
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
            result[LAST_MODIFIED] = max(x.createdTime for x in items)
            items.sort(key=lambda t: t.createdTime, reverse=self._sort_desc)
        result['TotalItemCount'] = item_count = len(items)
        # Supply this number to batching to prevent batch-ext links from showing
        # up if we've exhausted our supply.
        number_items_needed = self.__get_number_items_needed(item_count)
        self._batch_items_iterable(
            result, items, number_items_needed=number_items_needed)
        result[ITEM_COUNT] = len(result.get(ITEMS) or ())
        return result


class AbstractChildMoveView(AbstractAuthenticatedView,
                            ModeledContentUploadRequestUtilsMixin):
    """
    Move a given object between two parents in a course. The source
    and target NTIIDs must exist beneath the given context (no
    nodes are allowed to move between roots).

    Body elements:

    ObjectNTIID
            The NTIID of the object being moved.

    ParentNTIID
            The NTIID of the new parent node of the object being moved.

    Index
            (Optional) The index at which to insert the node in our parent.

    OldParentNTIID
            (Optional) The NTIID of the old parent of our moved
            node.

    :raises HTTPUnprocessableEntity if the parents do not exist, if the item
            does not exist in the old parent, or if moving between roots.
    """

    # The notify event on move.
    notify_type = None

    def _get_children_ntiids(self, parent_ntiid=None):
        """
        Subclasses should implement this to allow
        validation of movements within this context.
        """
        return ()

    def _get_context_ntiid(self):
        """
        Subclasses should implement this to define the contextual ntiid.
        Can return null.
        """
        return getattr(self.context, 'ntiid', None)

    def _remove_from_parent(self, parent, obj):
        """
        Define how to remove an item from a parent.
        """
        raise NotImplementedError()

    def _get_object_to_move(self, ntiid, old_parent=None):
        obj = find_object_with_ntiid(ntiid)
        if obj is None:
            raise hexc.HTTPUnprocessableEntity(_('Object no longer exists.'))
        return obj

    def _get_old_parent(self, old_parent_ntiid):
        result = None
        if old_parent_ntiid:
            result = find_object_with_ntiid(old_parent_ntiid)
            if result is None:
                raise hexc.HTTPUnprocessableEntity(
                    _('Old item parent no longer exists.'))
        return result

    def _get_new_parent(self, context_ntiid, new_parent_ntiid):
        if new_parent_ntiid == context_ntiid:
            new_parent = self.context
        else:
            new_parent = find_object_with_ntiid(new_parent_ntiid)

        if new_parent is None:
            # Really shouldn't happen if we validate this object is in our
            # outline.
            raise hexc.HTTPUnprocessableEntity(_('New parent does not exist.'))
        return new_parent

    def _validate_parents(self, old_parent_ntiid=None, new_parent_ntiid=None,
                          context_ntiid=None, *args, **kwargs):
        children_ntiids = self._get_children_ntiids(context_ntiid)
        if 		new_parent_ntiid not in children_ntiids \
                or (old_parent_ntiid
                    and old_parent_ntiid not in children_ntiids):
            raise hexc.HTTPUnprocessableEntity(
                _('Cannot move between root objects.'))

    def __call__(self):
        values = CaseInsensitiveDict(self.readInput())
        index = values.get('Index')
        ntiid = values.get('ObjectNTIID')
        new_parent_ntiid = values.get('ParentNTIID')
        old_parent_ntiid = values.get('OldParentNTIID')
        context_ntiid = self._get_context_ntiid()

        new_parent = self._get_new_parent(context_ntiid, new_parent_ntiid)
        old_parent = self._get_old_parent(old_parent_ntiid)
        if old_parent is None:
            old_parent = new_parent
        self._validate_parents(old_parent=old_parent,
                               new_parent=new_parent,
                               old_parent_ntiid=old_parent_ntiid,
                               new_parent_ntiid=new_parent_ntiid,
                               context_ntiid=context_ntiid)

        if index is not None and index < 0:
            raise hexc.HTTPBadRequest(_('Invalid index.'))
        obj = self._get_object_to_move(ntiid, old_parent)
        new_parent.insert(index, obj)

        # Make sure they don't move the object within the same node and
        # attempt to delete from that node.
        if old_parent_ntiid and old_parent_ntiid != new_parent_ntiid:
            did_remove = self._remove_from_parent(old_parent, obj)
            if not did_remove:
                raise hexc.HTTPUnprocessableEntity(
                    _('Moved item does not exist in old parent.'))
            old_parent.childOrderLock()

        if self.notify_type:
            notify(self.notify_type(obj, self.remoteUser.username,
                                    index, old_parent_ntiid=old_parent_ntiid))
        logger.info('Moved item (%s) at index (%s) (to=%s) (from=%s)',
                    ntiid, index, new_parent_ntiid, old_parent_ntiid)
        new_parent.childOrderLock()
        return self.context


class IndexedRequestMixin(object):

    def _get_index(self):
        """
        If the user supplies an index, we expect it to exist on the
        path: '.../index/<index_number>'
        """
        index = None
        if self.request.subpath and self.request.subpath[0] == 'index':
            try:
                index = self.request.subpath[1]
                index = int(index)
            except (TypeError, IndexError):
                raise hexc.HTTPUnprocessableEntity(
                    _('Invalid index %s' % index))
        index = index if index is None else max(index, 0)
        return index


class NTIIDPathMixin(object):

    def _get_ntiid(self):
        """
        Looks for a user supplied ntiid in the context path: '.../ntiid/<ntiid>'.
        """
        result = None
        if self.request.subpath and self.request.subpath[0] == 'ntiid':
            try:
                result = self.request.subpath[1]
            except (TypeError, IndexError):
                pass
        if result is None or not is_valid_ntiid_string(result):
            raise hexc.HTTPUnprocessableEntity(_('Invalid ntiid %s' % result))
        return result


class DeleteChildViewMixin(NTIIDPathMixin):
    """
    A view to delete a child underneath the given context.

    index
            This param will be used to indicate which object should be
            deleted. If the object described by `ntiid` is no longer at
            this index, the object will still be deleted, as long as it
            is unambiguous.

    :raises HTTPConflict if state has changed out from underneath user
    """

    def _get_children(self):
        return self.context

    def _is_target(self, obj, ntiid):
        return ntiid == getattr(obj, 'ntiid', '')

    def _validate(self):
        pass

    def _remove(self, item=None, index=None):
        """
        Subclasses should override to implement removal.
        """
        raise NotImplementedError()

    def _get_item(self, ntiid, index):
        """
        Find the item or index to delete for the given ntiid and index.
        """
        found = []
        for idx, child in enumerate(self._get_children()):
            if self._is_target(child, ntiid):
                if idx == int(index):
                    # We have an exact ref hit.
                    return None, idx
                else:
                    found.append(child)

        if len(found) == 1:
            # Inconsistent match, but it's unambiguous.
            return found[0], None

        if found:
            # Multiple matches, none at index
            raise hexc.HTTPConflict(
                _('Ambiguous item ref no longer exists at this index.'))

    def __call__(self):
        self._validate()
        values = CaseInsensitiveDict(self.request.params)
        index = values.get('index')
        ntiid = self._get_ntiid()
        found = self._get_item(ntiid, index)

        if found:
            to_delete, index = found
            self._remove(to_delete, index)
            self.context.childOrderLock()
        return hexc.HTTPOk()
