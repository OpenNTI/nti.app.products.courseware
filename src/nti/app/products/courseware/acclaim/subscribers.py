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
    container = ICourseAcclaimBadgeContainer(course, None)
    if not container:
        return
    integration = component.queryUtility(IAcclaimIntegration)
    if not integration:
        return
    entry_ntiid = ICourseCatalogEntry(course).ntiid
    client = IAcclaimClient(integration)
    current_organization_id = getattr(integration.organization, 'organization_id', None)
    if not current_organization_id:
        logger.warn('No organization tied to acclaim integration')
    for badge in container.values():
        # Only award badge if tied to our current integration
        if badge.organization_id != current_organization_id:
            logger.info('Badge not linked to current organization (%s) (badge_org=%s) (current_org=%s)',
                        badge.template_id,
                        badge.organization_id,
                        current_organization_id)
            continue
        client.award_badge(event.user,
                           badge.template_id,
                           evidence_ntiid=entry_ntiid)
