#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from zope import interface

from nti.schema.field import Bool
from nti.schema.field import ValidDatetime


class ICourseCompletedNotification(interface.Interface):
    """
    A notification to the user that they have successfully completed
    all requirements for a course.
    """

    IsAcknowledged = Bool(title=u"Indicates the user has acknowledged completion.",
                          default=False)

    AcknowledgedDate = ValidDatetime(title=u"The acknowledged date",
                                     description=u"The date on which the item was "
                                                 u"acknowledge as completed by the user",
                                     default=None,
                                     required=False)

    def acknowledge():
        """
        Acknowledge that the user has been notified of the completion.
        """

    def reset_acknowledgement():
        """
        Remove completion acknowledgement for the associated user and course.
        """
