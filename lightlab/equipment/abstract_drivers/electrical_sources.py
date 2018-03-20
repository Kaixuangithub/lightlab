import lightlab.util.io as io

import numpy as np
from lightlab import logger


class MultiModalSource(object):
    ''' Checks modes for sources with multiple ways to specify.

        Also checks ranges

        Default class constants come from NI PCI source array
    '''
    supportedModes = {'milliamp', 'amp', 'mwperohm', 'wattperohm', 'volt', 'baseunit'}
    baseUnitBounds = [0, 1] # Scaled voltage
    baseToVoltCoef = 10 # This ends up setting the volt bounds
    v2maCoef = 4  # current (milliamps) = v2maCoef * voltage (volts)
    exceptOnRangeError = False # If False, it will constrain it and print a warning

    @classmethod
    def enforceRange(cls, val, mode):
        ''' Returns clipped value. Raises RangeError
        '''
        bnds = [cls.baseUnit2val(vBnd, mode) for vBnd in cls.baseUnitBounds]
        enforcedValue = np.clip(val, *bnds)
        if enforcedValue != val:
            logger.warning('Warning: value out of range was constrained.\n' +
                           'Requested ' + str(val) +
                           '. Allowed range is' + str(bnds) + ' in ' + mode + 's.')
            if cls.exceptOnRangeError:
                raise io.RangeError('Current sources requested out of range.')
        return enforcedValue

    @classmethod
    def _checkMode(cls, mode):
        ''' Returns mode in lower case
        '''
        if mode not in cls.supportedModes:
            raise TypeError('Invalid mode: ' + str(mode) + '. Valid: ' + str(cls.supportedModes))
        else:
            return mode.lower()

    @classmethod
    def val2baseUnit(cls, value, mode):
        """Converts to the voltage value that will be applied at the PCI board
        Depends on the current mode state of the instance

            Args:
                value (float or dict)
        """
        mode = cls._checkMode(mode)
        valueWasDict = isinstance(value, dict)
        if not valueWasDict:
            value = {-1: value}
        baseVal = dict()
        for ch, vEl in value.items():
            if mode == 'baseunit':
                baseVal[ch] = vEl
            if mode == 'volt':
                baseVal[ch] = vEl / cls.baseToVoltCoef
            elif mode == 'milliamp':
                baseVal[ch] = cls.val2baseUnit(vEl, 'volt') / cls.v2maCoef
            elif mode == 'amp':
                baseVal[ch] = cls.val2baseUnit(vEl, 'milliamp') * 1e3
            elif mode == 'wattperohm':
                baseVal[ch] = np.sign(vEl) * np.sqrt(abs(cls.val2baseUnit(vEl, 'amp')))
            elif mode == 'mwperohm':
                baseVal[ch] = cls.val2baseUnit(vEl, 'wattperohm') / 1e3
        if valueWasDict:
            return baseVal
        else:
            return baseVal[-1]

    @classmethod
    def baseUnit2val(cls, baseVal, mode):
        """Converts the voltage value that will be applied at the PCI board back into the units of th instance
        This is useful for bounds checking

            Args:
                baseVal (float or dict)
        """
        mode = cls._checkMode(mode)
        baseValWasDict = isinstance(baseVal, dict)
        if not baseValWasDict:
            baseVal = {-1: baseVal}
        value = dict()
        for ch, bvEl in baseVal.items():
            if mode == 'baseunit':
                value[ch] = bvEl
            elif mode == 'volt':
                value[ch] = bvEl * cls.baseToVoltCoef
            elif mode == 'milliamp':
                value[ch] = cls.baseUnit2val(bvEl, 'volt') * cls.v2maCoef
            elif mode == 'amp':
                value[ch] = cls.baseUnit2val(bvEl, 'milliamp') * 1e-3
            elif mode == 'wattperohm':
                value[ch] = np.sign(bvEl) * (cls.baseUnit2val(bvEl, 'amp')) ** 2
            elif mode == 'mwperohm':
                value[ch] = cls.baseUnit2val(bvEl, 'wattperohm') * 1e3
        if baseValWasDict:
            return value
        else:
            return value[-1]


class ElectricalSource(object):
    """ This thing basically holds a dict state and provides some critical methods

        There is no mode

        Checks for channel compliance. Handles range exceptions
    """
    maxChannel = None  # number of dimensions that the current sources are expecting

    def __init__(self, useChans=None, *args, **kwargs):
        if useChans is None:
            useChans = list()
        self.stateDict = dict([ch, 0] for ch in useChans)

        # Check that the requested channels are available to be blocked out
        if type(self).maxChannel is not None:
            if any(ch > type(self).maxChannel - 1 for ch in self.getChannels()):
                raise Exception(
                    'Requested channel is more than there are available')

    def getChannels(self):
        return list(self.stateDict.keys())

    def setChannelTuning(self, chanValDict, *args, **kwargs):
        ''' Sets a number of channel values and updates hardware

            Args:
                chanValDict (dict): A dictionary specifying {channel: value}
                waitTime (float): time in ms to wait after writing, default (None) is defined in the class

            Returns:
                (bool): was there a change in value
        '''
        if type(chanValDict) is not dict:
            raise TypeError(
                'The argument for setChannelTuning must be a dictionary')

        # Check channels
        for chan in chanValDict.keys():
            if chan not in self.stateDict.keys():
                raise io.ChannelError('Channel index not blocked out. ' +
                                      'Requested ' + str(chan) +
                                      ', Available ' + str(self.stateDict.keys()))

        # Change our *internal* state
        self.stateDict.update(chanValDict)

    def getChannelTuning(self, *args, **kwargs):
        ''' The inverse of setChannelTuning

            Args:
                mode (str): units of the value in ('mwperohm', 'milliamp', 'volt')

            Returns:
                (dict): the full state of blocked out channels in units determined by mode argument
        '''
        return self.stateDict.copy()

    def off(self, *setArgs):
        """Turn all voltages to zero, but maintain the session
        """
        self.setChannelTuning(dict([ch, 0] for ch in self.stateDict.keys()), *setArgs)


# class ElectricalSenseSource(ElectricalSource):
#     ''' Also provides measureVoltage

#         Todo:
#             make sure mode is in milliamps for query
#     '''
#     def __init__(self, resistiveDict, voltQueryMethod=None, **kwargs):
#         ''' In this one, current is in amps

#             Args:
#                 resistiveDict (dict): keys are useChans, values are objects that provide
#                 voltQueryMethod is unbound method with one argument: current

#         '''
#         super().__init__(useChans=list(resistiveDict.keys()), **kwargs)
#         self.resistors = resistiveDict
#         resType = type(resistors.values()[0])
#         if voltQueryMethod is None:
#             try:
#                 self.voltQuery = resType.getVoltage
#             except AttributeError as err:
#                 print(resType, 'does not have getVoltage(self, current)')
#                 raise err
#         else:
#             try:
#                 resType.voltQueryMethod(resistors.values()[0])
#             except AttributeError as err:
#                 print(resType, 'has no unbound method', str(voltQueryMethod))
#             self.voltQuery = voltQueryMethod

#     setCurrent = setChannelTuning

#     def measureVoltage(self):
#         voltDict = dict()
#         for ch, ival in self.stateDict.items():
#             voltDict[ch] = self.voltQuery(self.resistors[ch], ival)
#         return voltDict


# class SingleSenseSource(ElectricalSenseSource):
#     def __init__(self, resistive, voltQueryMethod=None, **kwargs):
#         super().__init__({0, resistive}, voltQueryMethod=voltQueryMethod, **kwargs)

#     def setCurrent(self, curr):
#         return super().setChannelTuning({0: curr})

#     def measureVoltage(self):
#         voltDict = super().measureVoltage()
#         return voltDict[0]

