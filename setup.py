from setuptools import setup, Extension
import versioneer

classifiers = [
    'Environment :: No Input/Output (Daemon)',
    'Intended Audience :: Science/Research',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python :: 2.7',
    'Topic :: Scientific/Engineering :: Astronomy'
'    Topic :: Scientific/Engineering :: Atmospheric Science'
    'Development Status :: 4 - Beta',
]


setup(name             = 'ema',
      version          = versioneer.get_version(),
      cmdclass         = versioneer.get_cmdclass(),
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
