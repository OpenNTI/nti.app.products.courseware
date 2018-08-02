#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zc.intid.interfaces import IAfterIdAddedEvent

from zope.intid.interfaces import IIntIdRemovedEvent

from zope.lifecycleevent import IObjectModifiedEvent

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset
from nti.app.products.courseware.webinars.interfaces import ICourseWebinarContainer

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import IPresentationAssetMovedEvent
from nti.contenttypes.presentation.interfaces import IPresentationAssetCreatedEvent

from nti.solr.common import queue_add
from nti.solr.common import queue_remove
from nti.solr.common import queue_modified
from nti.solr.common import single_index_job
from nti.solr.common import single_unindex_job

from nti.solr.interfaces import IIndexObjectEvent
from nti.solr.interfaces import IUnindexObjectEvent

from nti.solr.presentation import ASSETS_QUEUE

logger = __import__('logging').getLogger(__name__)


@component.adapter(IWebinarAsset, IPresentationAssetCreatedEvent)
def _on_webinar_asset_created(asset, unused_event):
    course = ICourseInstance(asset)
    container = ICourseWebinarContainer(course)
    original_webinar = asset.webinar
    # pylint: disable=too-many-function-args
    normalized_webinar = container.get_or_create_webinar(original_webinar)
    asset.webinar = normalized_webinar


@component.adapter(IWebinarAsset, IAfterIdAddedEvent)
def _asset_added(obj, unused_event=None):
    queue_add(ASSETS_QUEUE, single_index_job, obj)


@component.adapter(IWebinarAsset, IObjectModifiedEvent)
def _asset_modified(obj, unused_event=None):
    queue_modified(ASSETS_QUEUE, single_index_job, obj)


@component.adapter(IWebinarAsset, IIntIdRemovedEvent)
def _asset_removed(obj, unused_event=None):
    queue_remove(ASSETS_QUEUE, single_unindex_job, obj=obj)


@component.adapter(IWebinarAsset, IPresentationAssetMovedEvent)
def _asset_moved(obj, unused_event=None):
    queue_modified(ASSETS_QUEUE, single_index_job, obj=obj)


@component.adapter(IWebinarAsset, IIndexObjectEvent)
def _index_asset(obj, unused_event=None):
    _asset_added(obj, None)


@component.adapter(IWebinarAsset, IUnindexObjectEvent)
def _unindex_asset(obj, unused_event=None):
    _asset_removed(obj, None)
