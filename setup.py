from setuptools import setup, Extension

classifiers = ['Development Status :: 3 - Alpha',
               'Operating System :: POSIX :: Linux',
               'License :: OSI Approved :: MIT License',
               'Intended Audience :: Developers',
               'Programming Language :: Python :: 2.7',
               'Operating System :: POSIX',
               'Topic :: Astronomy',
               'Topic :: Meteorology',
               'Topic :: Raspberry Pi',
               'Development Status :: 4 - Beta',
               ]

setup(name             = 'EMA',
      version          = '0.1.0',
      author           = 'Rafael Gonzalez',
      author_email     = 'astrorafael@yahoo.es',
      description      = 'A package to monitor & control EMA Weather Station',
      long_description = open('README.md').read(),
      license          = 'MIT',
      keywords         = 'EMA Astronomy Python RaspberryPi',
      url              = 'http://github.com/astrorafael/ema/',
      classifiers      = classifiers,
      packages         = ["ema", "ema.dev", "ema.server"],
      )
