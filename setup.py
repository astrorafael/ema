from setuptools import setup, Extension, find_packages
import versioneer

# Default description in markdown
long_description = open('README.md').read()
 
# Converts from makrdown to rst using pandoc
# and its python binding.
# Docunetation is uploaded in PyPi when registering
# by issuing `python setup.py register`

try:
    import subprocess
    import pandoc
 
    process = subprocess.Popen(
        ['which pandoc'],
        shell=True,
        stdout=subprocess.PIPE,
        universal_newlines=True
    )
 
    pandoc_path = process.communicate()[0]
    pandoc_path = pandoc_path.strip('\n')
 
    pandoc.core.PANDOC_PATH = pandoc_path
 
    doc = pandoc.Document()
    doc.markdown = long_description
 
    long_description = doc.rst
 
except:
    pass
   



classifiers = [
    'Environment :: No Input/Output (Daemon)',
    'Intended Audience :: Science/Research',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python :: 2.7',
    'Topic :: Scientific/Engineering :: Astronomy',
    'Topic :: Scientific/Engineering :: Atmospheric Science',
    'Topic :: Communications',
    'Topic :: Internet',
    'Development Status :: 4 - Beta',
]


setup(name             = 'ema',
      version          = versioneer.get_version(),
      cmdclass         = versioneer.get_cmdclass(),
      author           = 'Rafael Gonzalez',
      author_email     = 'astrorafael@yahoo.es',
      description      = 'A package to monitor & control EMA Weather Station',
      long_description = long_description,
      license          = 'MIT',
      keywords         = 'EMA Astronomy Python RaspberryPi',
      url              = 'http://github.com/astrorafael/ema/',
      classifiers      = classifiers,
      packages         = find_packages(exclude=[]),
      install_requires = ['paho-mqtt','pyserial'],
      data_files       = [ 
          ('/etc/init.d' ,   ['init.d/ema']),
          ('/etc/default',   ['default/ema']),
          ('/etc/ema',       ['config/config']),
          ('/usr/local/bin', ['scripts/emacli', 
                              'scripts/ema',
                              'scripts/emacli',
                              'scripts/low-volt-sms+shutdown',
                              'scripts/roof-script',
                              'scripts/volt-script']),
      ],
  )
