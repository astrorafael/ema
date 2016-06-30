import os
import os.path

from setuptools import setup, Extension
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


if os.name == "posix":
    
    import shlex

    # Some fixes before setup
    if not os.path.exists("/etc/logrotate_astro.d"):
      print("creating directory /etc/logrotate_astro.d")
      args = shlex.split( "mkdir /etc/logrotate_astro.d")
      subprocess.call(args)


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
          packages         = ["ema"],
          install_requires = ['twisted >= 16.2.0','twisted-mqtt','pyserial', 'service-identity'],
          data_files       = [ 
              ('/etc/init.d' ,     ['files/init.d/ema']),
              ('/etc/default',     ['files/etc/default/ema']),
              ('/etc/ema.d',       ['files/etc/ema.d/config']),
              ('/etc/logrotate.d', ['files/etc/logrotate.d/ema']),
              ('/usr/local/bin',   ['files/usr/local/bin/emacli', 
                                  'files/usr/local/bin/ema',
                                  'files/usr/local/bin/low-volt-sms+shutdown',
                                  'files/usr/local/bin/roof-script',
                                  'files/usr/local/bin//volt-script']),
            ],
        )


elif os.name == "nt":

    import sys
    import shlex

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
          packages         = ["ema"],
          install_requires = ['twisted >= 16.2.0','twisted-mqtt','pyserial', 'service-identity'],
          data_files       = [ 
            (r'C:\ema',          [r'files\winnt\ema.bat',r'files\winnt\winreload.py']),
            (r'C:\ema\log',      [r'files\winnt\placeholder.txt']),
            (r'C:\ema\config',   [r'files\winnt\config.example.ini',]),
            ]
          )

    args = shlex.split( "python -m ema --startup auto install")
    subprocess.call(args)

else:
  pass



