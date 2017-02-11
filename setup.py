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
          packages         = ["ema",  "ema.service", "ema.test", ],
          install_requires = ['twisted >= 16.3.0','twisted-mqtt','pyserial', 'klein'],
          data_files       = [ 
              ('/etc/init.d' ,     ['files/etc/init.d/ema']),
              ('/etc/ema',         ['files/etc/ema/config.example','files/etc/ema/passwd.example']),
              ('/etc/logrotate.d', ['files/etc/logrotate.d/ema']),
              ('/usr/local/bin',   ['files/usr/local/bin/ema',
                                    'files/usr/local/bin/emapasswd',
                                    'files/usr/local/bin/ema-activity-10.example',
                                    'files/usr/local/bin/ema-activity-30.example',
                                    'files/usr/local/bin/ema-activity-50.example',
                                    'files/usr/local/bin/ema-activity-70.example',
                                    'files/usr/local/bin/ema-activity-90.example',
                                    'files/usr/local/bin/ema-low-volt-sms+shutdown.example',
                                    'files/usr/local/bin/ema-roof-script.example',
                                    'files/usr/local/bin/ema-volt-script.example']),
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
          packages         = ["ema", "ema.service", "ema.test"],
          install_requires = ['twisted >= 16.3.0','twisted-mqtt','pyserial', 'klein' ],
          data_files       = [ 
            (r'C:\ema',          [r'files\winnt\emad.bat',
                                  r'files\winnt\winreload.py',
                                  r'files\winnt\emapasswd.py',]),
            (r'C:\ema\log',      [r'files\winnt\placeholder.txt', ]),
            (r'C:\ema\config',   [r'files\winnt\config.example.ini', r'files\winnt\passwd.example']),
            (r'C:\ema\scripts',  [r'files\winnt\ema-low-volt-sms-shutdown.py',
                                  r'files\winnt\ema-roof-script.py',
                                  r'files\winnt\ema-shutdown.py',
                                  r'files\winnt\ema-volt-script.py',
                                  ]),
            ]
          )

    args = shlex.split( "python -m ema --startup auto install")
    subprocess.call(args)

else:
  pass



