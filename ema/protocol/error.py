# ----------------------------------------------------------------------
# Copyright (C) 2016 by Rafael Gonzalez 
#
#  See the LICENSE file.
# ----------------------------------------------------------------------


# -------------------------------------------------------------------

class EMARangeError(ValueError):
    '''Command value out of range'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = '{0}: <{1}> ({2}) not in {3}'.format(s, self.args[0], self.args[1], self.args[2])
        s = '{0}.'.format(s)
        return s

class EMAReturnError(EMARangeError):
    '''Command return value out of range'''
    pass


class EMAError(Exception):
    '''Base class for all exceptions below'''
    pass


class EMATimeoutError(EMAError):
    '''EMA no responding to command'''
    def __str__(self):
        s = self.__doc__
        if self.args:
            s = "{0}: '{1}'".format(s, self.args[0])
        s = '{0}.'.format(s)
        return s
