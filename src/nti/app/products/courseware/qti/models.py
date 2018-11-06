#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


class AbstractQTIItem(object):

    def __init__(self, question):
        self.question = question


class QTIAssessment(object):
    pass


class QTIChoice(AbstractQTIItem):

    def to_xml(self):
        """
        Converts to the appropriate xml format
        """
