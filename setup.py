
from setuptools import setup, find_packages


setup(
    name='calculette_impots_m_language_parser',
    version='2.0.0',

    author='Etalab',
    author_email='info@data.gouv.fr',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering :: Information Analysis',
        ],
    description='Parseur du langage M de la calculette des impôts',
    keywords='calculette impôts tax language parser',
    license='http://www.fsf.org/licensing/licenses/agpl-3.0.html',
    url='https://git.framasoft.org/openfisca/calculette-impots-m-language-parser',

    install_requires=[
        'Arpeggio >= 1.2.1',
        'toolz >= 0.7.4',
        'numpy >= 1.13',
        ],
    packages=find_packages(exclude=['calculette_impots_m_language_parser.tests*']),
    tests_require=['nose'],
    test_suite='nose.collector',
    )
