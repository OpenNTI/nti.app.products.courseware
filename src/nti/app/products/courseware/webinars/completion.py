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

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset

from nti.app.products.webinar.interfaces import IWebinarProgressContainer
from nti.app.products.webinar.interfaces import IUserWebinarProgressContainer

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy

from nti.contenttypes.completion.policies import AbstractCompletableItemCompletionPolicy

from nti.contenttypes.completion.progress import Progress

from nti.contenttypes.completion.utils import update_completion

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import IUser

from nti.dataserver.users import User

from nti.externalization.persistence import NoPickle

logger = __import__('logging').getLogger(__name__)


@NoPickle
@component.adapter(IWebinarAsset, ICourseInstance)
@interface.implementer(ICompletableItemCompletionPolicy)
class WebinarAssetCompletionPolicy(AbstractCompletableItemCompletionPolicy):

    def __init__(self, asset, course):
        self.asset = asset
        self.course = course

    def is_complete(self, progress):
        result = None
        if progress is not None and progress.HasProgress:
            result = CompletedItem(Item=progress.Item,
                                   Principal=progress.User,
                                   CompletedDate=progress.LastModified)
        return result


def update_webinar_completion(asset, webinar, course):
    progress_container = IWebinarProgressContainer(webinar)
    for username in progress_container:
        user = User.get_user(username)
        if user is not None:
            update_completion(asset, asset.ntiid, user, course)


@component.adapter(IUser, IWebinarAsset, ICourseInstance)
@interface.implementer(IProgress)
def webinar_asset_progress(user, asset, course):
    result = None
    webinar = asset.webinar
    if webinar is None:
        return result

    user_container = component.queryMultiAdapter((user, webinar),
                                                 IUserWebinarProgressContainer)

    viewed_time = sum(x.attendanceTimeInSeconds
                      for x in user_container.values()
                      if x.attendanceTimeInSeconds)
    if viewed_time:
        # LastModified is the first leave time of the most recent session
        last_mod = None
        for webinar_progress in user_container.values():
            attendance = webinar_progress.attendance
            first_leave_time = min(x.leaveTime for x in attendance if x.leaveTime)
            if last_mod is None:
                last_mod = first_leave_time
            else:
                last_mod = max(last_mod, first_leave_time)
        progress = Progress(NTIID=asset.ntiid,
                            MaxPossibleProgress=None,
                            AbsoluteProgress=viewed_time,
                            HasProgress=True,
                            LastModified=last_mod,
                            Item=asset,
                            User=user,
                            CompletionContext=course)
        result = progress
    return result
