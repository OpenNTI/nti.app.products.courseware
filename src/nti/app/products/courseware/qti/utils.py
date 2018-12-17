#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os

from bs4 import BeautifulSoup

from six.moves import urllib_parse

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


def is_internal_resource(href):
    return not bool(urllib_parse.urlparse(href).scheme) and not href.startswith('#')


def update_external_resources(html, path_prefix='dependencies'):
    soup = BeautifulSoup(html, features='html.parser')
    deps = []
    to_be_extracted = []
    for tag in soup.recursiveChildGenerator():
        if hasattr(tag, 'name') and tag.name == 'a' and \
                hasattr(tag, 'attrs') and 'href' in tag.attrs:
            href = tag.attrs['href']
            if is_internal_resource(href):
                deps.append(href)
                href = os.path.join(path_prefix, href)
                tag.attrs['href'] = os.path.join('$IMS-CC-FILEBASE$', href)
            elif href.startswith('#'):
                to_be_extracted.append(tag)
        if hasattr(tag, 'name') and tag.name == 'img' and \
                hasattr(tag, 'attrs') and 'src' in tag.attrs:
            src = tag.attrs['src']
            if is_internal_resource(src):
                deps.append(src)
                src = os.path.join(path_prefix, src)
                tag.attrs['src'] = os.path.join('$IMS-CC-FILEBASE$', src)
    for tag in to_be_extracted:
        tag.extract()
    return soup.decode(), deps


def mathjax_parser(html):
    soup = BeautifulSoup(html, features='html.parser')
    mathjax = soup.find_all('span', class_='mathjax math tex2jax_process')
    for mj in mathjax:
        nobr = mj.find_all('nobr')
        for tag in nobr:
            # nobr isn't supported in canvas. We replace it with a valid css property
            tag.name = 'span'
            tag.attrs = {'style': 'white-space: nowrap; font-size: 14px;'}
    return soup.decode()
