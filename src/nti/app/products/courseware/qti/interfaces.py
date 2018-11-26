#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from zope import interface

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


class IQTIAssessment(interface.Interface):
    """
    A QTI Assessment
    """


class IQTIItem(interface.Interface):
    """
    One unit of QTI Assessment
    """


class ICanvasMeta(interface.Interface):
    pass
