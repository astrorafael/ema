# ----------------------------------------------------------------------
# Copyright (C) 2016 by Rafael Gonzalez 
#
#  See the LICENSE file.
# ----------------------------------------------------------------------


# ------------------------------------------------------------

class TimeoutValueError(ValueError):
    '''Protocol timeout value out of range'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: {1}".format(s, self.args[0])
        s = '{0}.'.format(s)
        return s

class WindowValueError(ValueError):
    '''Max. number of allowed in-flight messages out of range'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: {1}".format(s, self.args[0])
        s = '{0}.'.format(s)
        return s


class ColourError(ValueError):
    '''Colour out of range [0..255]'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: name={1} value={2}".format(s, self.args[0], self.args[1])
        s = '{0}.'.format(s)
        return s

class RetriesError(ValueError):
    '''Too high max. number of retries [0..10]'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: {1}".format(s, self.args[0])
        s = '{0}.'.format(s)
        return s

# -------------------------------------------------------------------

class EMAError(Exception):
    '''Base class for all exceptions below'''
    pass


class EMAWindowError(EMAError):
    '''Request exceeded maximun window size'''
    def __str__(self):
        return self.__doc__


class EMATimeoutError(EMAError):
    '''EMA no responding in time to expected command'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: '{1}'".format(s, self.args[0])
        s = '{0}.'.format(s)
        return s
