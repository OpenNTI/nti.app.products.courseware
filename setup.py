import codecs
from setuptools import setup, find_packages

entry_points = {
    'console_scripts': [
        "nti_acl_forum_creator = nti.app.products.courseware.scripts.nti_acl_forum_creator:main",
        "nti_unregister_invalid_nodes = nti.app.products.courseware.scripts.nti_unregister_invalid_nodes:main",
        "nti_course_enrollment_migrator = nti.app.products.courseware.scripts.nti_course_enrollment_migrator:main",
    ],
    "z3c.autoinclude.plugin": [
        'target = nti.app.products',
    ],
}


TESTS_REQUIRE = [
    'nti.app.testing',
    'nti.testing',
    'zope.dottedname',
    'zope.testrunner',
]


def _read(fname):
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()


setup(
    name='nti.app.products.courseware',
    version=_read('version.txt').strip(),
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="Umbrella product to support integrated courseware",
    long_description=(_read('README.rst') + '\n\n' + _read('CHANGES.rst')),
    license='Apache',
    keywords='pyramid products courses',
    classifiers=[
        'Framework :: Zope',
        'Framework :: Pyramid',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    url="https://github.com/NextThought/nti.app.products.courseware",
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti', 'nti.app', 'nti.app.products'],
    tests_require=TESTS_REQUIRE,
    install_requires=[
        'setuptools',
        'nti.contenttypes.courses',
    ],
    extras_require={
        'test': TESTS_REQUIRE,
    },
    entry_points=entry_points
)
