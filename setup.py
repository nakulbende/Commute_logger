from setuptools import setup

setup(name='commute_logger',
      description='A python based logger for recording commute times using Google Directions API',
      url='https://github.com/nakulbende/Commute_logger',
      author='Nakul Bende',
      author_email='nakulbende@gmail.com',
      license='MIT, Copyright (c) 2021 Nakul Bende',
      packages=['commute_logger'],
      install_requires=[
          'googlemaps', 'datetime', 'pytz', 'pandas', 'altair', 'numpy',
      ],
      zip_safe=False)