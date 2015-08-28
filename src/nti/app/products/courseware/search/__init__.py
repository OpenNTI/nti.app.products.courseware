#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import hashlib

from zope import component

from zope.traversing.interfaces import IEtcNamespace

import repoze.lru

from nti.dataserver.interfaces import IMemcacheClient

DEFAULT_EXP_TIME = 86400

def last_synchronized():
    hostsites = component.queryUtility(IEtcNamespace, name='hostsites')
    result = getattr(hostsites, 'lastSynchronized', 0)
    return result

def memcache_client():
    return component.queryUtility(IMemcacheClient)

def memcache_get(key, client=None):
    client = component.queryUtility(IMemcacheClient) if client is None else client
    if client is not None:
        try:
            return client.get(key)
        except:
            pass
    return None

def memcache_set(key, value, client=None, exp=DEFAULT_EXP_TIME):
    client = component.queryUtility(IMemcacheClient) if client is None else client
    if client is not None:
        try:
            client.set(key, value, time=exp)
            return True
        except:
            pass
    return False

@repoze.lru.lru_cache(200)
def encode_keys(*keys):
    result = hashlib.md5()
    for key in keys:
        result.update(str(key).lower())
    return result.hexdigest()
