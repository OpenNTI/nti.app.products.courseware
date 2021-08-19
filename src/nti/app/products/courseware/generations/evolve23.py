#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface
from zope.annotation import IAnnotations

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware.calendar.attendance import CourseCalendarEventAttendanceContainer

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEventAttendanceContainer

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

EVENT_ATTENDANCE = u'EventAttendance'

generation = 23

logger = __import__('logging').getLogger(__name__)


def _process_calendar(calendar):
    processed = 0
    for event in calendar.values():
        annotations = IAnnotations(event)

        # Don't create attendance container if not already created
        if EVENT_ATTENDANCE not in annotations:
            continue

        # Anything already implementing course-specific iface can be ignored
        attendance_container = annotations[EVENT_ATTENDANCE]
        if ICourseCalendarEventAttendanceContainer.providedBy(attendance_container):
            continue

        attendance_container.__class__ = CourseCalendarEventAttendanceContainer
        attendance_container._p_changed = True

        annotations['EventAttendance'] = attendance_container

        for name, attendance in attendance_container.items():
            attendance.__parent__ = attendance_container

        processed += 1

    return processed


def _process_site(current, intids, seen):
    with current_site(current):
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is None or catalog.isEmpty():
            return
        for entry in catalog.iterCatalogEntries():
            course = ICourseInstance(entry)
            doc_id = intids.queryId(course)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)

            calendar = ICourseCalendar(course)
            processed = _process_calendar(calendar)
            if processed:
                logger.info('Processed %d attendance containers for course %s',
                            processed, entry.ProviderUniqueID)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warn("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
        return None


def do_evolve(context, generation=generation):
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with current_site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
            "Hooks not installed?"

        seen = set()
        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)
        for current in get_all_host_sites():
            _process_site(current, intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 23 by migrating all attendance containers to
    course-specific versions for course calendar events
    """
    do_evolve(context)
