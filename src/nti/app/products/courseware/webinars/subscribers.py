#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset
from nti.app.products.courseware.webinars.interfaces import ICourseWebinarContainer

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import IPresentationAssetCreatedEvent

from nti.externalization.interfaces import IObjectModifiedFromExternalEvent

logger = __import__('logging').getLogger(__name__)


@component.adapter(IWebinarAsset, IPresentationAssetCreatedEvent)
def _on_webinar_asset_created(asset, unused_event):
    course = ICourseInstance(asset)
    container = ICourseWebinarContainer(course)
    original_webinar = asset.webinar
    # pylint: disable=too-many-function-args
    normalized_webinar = container.get_or_create_webinar(original_webinar)
    asset.webinar = normalized_webinar
    # Ghost it?
    # if normalized_webinar != original_webinar:
    #     original_webinar._p_changed = None


@component.adapter(IWebinarAsset, IObjectModifiedFromExternalEvent)
def _on_webinar_asset_modified(asset, unused_event):
    _on_webinar_asset_created(asset, unused_event)