from setuptools import setup, find_packages
import codecs

VERSION = '0.0.0'

entry_points = {
}

setup(
	name='nti.app.products.courseware',
	version=VERSION,
	author='Jason Madden',
	author_email='jason@nextthought.com',
	description="Umbrella product to support integrated courseware",
	long_description=codecs.open('README.rst', encoding='utf-8').read(),
	license='Proprietary',
	keywords='pyramid preference',
	# url = 'https://github.com/NextThought/nti.nose_traceback_info',
	classifiers=[
		'Intended Audience :: Developers',
		'Natural Language :: English',
		'Operating System :: OS Independent',
		'Programming Language :: Python :: 2',
		'Programming Language :: Python :: 2.7',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.3',
		'Topic :: Software Development :: Testing'
		'Framework :: Pyramid',
		],
	packages=find_packages('src'),
	package_dir={'': 'src'},
	namespace_packages=['nti', 'nti.app', 'nti.app.products'],
	install_requires=[
		'setuptools',
		'nti.app.testing',
		'nti.testing',
		# Undeclared dep on parts of nti.dataserver
	],
	entry_points=entry_points
)
