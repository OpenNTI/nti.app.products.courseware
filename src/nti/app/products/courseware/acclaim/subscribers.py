#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseCompletedEvent

from nti.app.products.acclaim.interfaces import IAcclaimClient
from nti.app.products.acclaim.interfaces import IAcclaimIntegration

from nti.app.products.courseware.acclaim.interfaces import ICourseAcclaimBadgeContainer

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance, ICourseCompletedEvent)
def _award_badge_on_course_completion(course, event):
    # FIXM: Only award badge if tied to our current integration
    container = ICourseAcclaimBadgeContainer(course, None)
    if not container:
        return
    integration = component.queryUtility(IAcclaimIntegration)
    if not integration:
        return
    entry_ntiid = ICourseCatalogEntry(course).ntiid
    client = IAcclaimClient(integration)
    for badge in container.values():
        client.award_badge(event.user,
                           badge.template_id,
                           evidence_ntiid=entry_ntiid)
