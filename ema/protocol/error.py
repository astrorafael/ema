# ----------------------------------------------------------------------
# Copyright (C) 2016 by Rafael Gonzalez 
#
#  See the LICENSE file.
# ----------------------------------------------------------------------


# -------------------------------------------------------------------

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
