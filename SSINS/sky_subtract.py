from __future__ import absolute_import, division, print_function

import numpy as np
from pyuvdata import UVData
import os
from SSINS import util
from SSINS import INS
from SSINS import MF
from SSINS import VDH
from SSINS import ES
import scipy.stats
import warnings


class SS:

    def __init__(self, obs=None, outpath=None, UV=None, inpath=None,
                 bad_time_indices=None, read_kwargs={}, flag_choice=None,
                 INS=None, custom=None, diff=True):

        self.obs = obs
        self.outpath = outpath
        for attr in ['obs', 'outpath']:
            if getattr(self, attr) is None:
                warnings.warn('In order to save outputs and use Catalog_Plot.py,\
                               please supply %s keyword other than None' % (attr))

        if UV is None:
            assert inpath is not None, 'Either supply a valid UVData object for\
                                        the UV keyword, or supply a path to a \
                                        valid UVData file for the inpath keyword'

            self.UV = UVData()

            self.flag_choice = flag_choice
            self.UV.read(inpath, **read_kwargs)

            assert self.UV.Nblts == self.UV.Nbls * self.UV.Ntimes, 'Nblts != Nbls * Ntimes'
            cond = np.all([self.UV.baseline_array[:self.UV.Nbls] ==
                           self.UV.baseline_array[k * self.UV.Nbls:(k + 1) * self.UV.Nbls]
                           for k in range(1, self.UV.Ntimes - 1)])
            assert cond, 'Baseline array slices do not match!'

            if bad_time_indices is not None:
                bool_ind = np.ones(self.UV.Ntimes, dtype=bool)
                bool_ind[bad_time_indices] = 0
                times = np.unique(self.UV.time_array)[bool_ind]
                self.UV.select(times=times)

        else:
            self.UV = UV
            self.flag_choice = flag_choice

        pol_keys = list(range(-8, 5))
        pol_keys.remove(0)
        pol_values = ['YX', 'XY', 'YY', 'XX', 'LR', 'RL', 'LL', 'RR', 'I', 'Q',
                      'U', 'V']
        pol_dict = dict(zip(pol_keys, pol_values))
        self.pols = np.array([pol_dict[self.UV.polarization_array[k]] for k in
                              range(self.UV.Npols)])

        if diff:
            self.UV.data_array = np.ma.masked_array(np.absolute(np.diff(np.reshape(self.UV.data_array,
                                                    [self.UV.Ntimes, self.UV.Nbls, self.UV.Nspws,
                                                     self.UV.Nfreqs, self.UV.Npols]), axis=0)))

            self.UV.flag_array = np.reshape((self.UV.flag_array[:-self.UV.Nbls] +
                                             self.UV.flag_array[self.UV.Nbls:]) > 0,
                                            [self.UV.Ntimes - 1, self.UV.Nbls,
                                             self.UV.Nspws, self.UV.Nfreqs,
                                             self.UV.Npols]).astype(bool)

        if self.flag_choice is not None:
            self.apply_flags(choice=self.flag_choice, INS=INS, custom=custom)

    def apply_flags(self, choice=None, INS=None, custom=None):
        if choice is 'original':
            self.UV.data_array.mask = self.UV.flag_array
        elif choice is 'INS':
            ind = np.where(INS.data.mask)
            self.UV.data_array[ind[0], :, ind[1], ind[2], ind[3]] = np.ma.masked
        elif choice is 'custom':
            self.UV.data_array[custom] = np.ma.masked
        elif np.any(self.UV.data_array.mask):
            self.UV.data_array.mask = False

    def save_meta(self):

        path = '%s/metadata'
        if not os.path.exists(path):
            os.makedirs(path)
        assert os.path.exists(path), 'Output directory, %s, could not be created.\
                                      Check permissions.' % (path)
        np.save('%s/%s_pols.npy' % (path, self.obs), self.pols)
        for meta in ['vis_units', 'freq_array']:
            np.save('%s/metadata/%s_%s.npy' %
                    (self.outpath, self.obs, meta), getattr(self.UV, meta))
        for meta in ['time_array', 'lst_array']:
            np.save('%s/metadata/%s_%s.npy' % (self.outpath, self.obs, meta),
                    np.unique(getattr(self.UV, meta)))

    def save_data(self):

        for attr in ['INS', 'VDH', 'ES']:
            if hasattr(self, attr):
                getattr(getattr(self, attr), 'save')()

    def INS_prepare(self):
        data = self.UV.data_array.mean(axis=1)
        if np.any(self.UV.data_array.mask):
            Nbls = np.count_nonzero(np.logical_not(self.UV.data_array.mask), axis=1)
        else:
            Nbls = self.UV.Nbls * np.ones(data.shape)
        kwargs = {'data': data,
                  'Nbls': Nbls,
                  'freq_array': self.UV.freq_array,
                  'pols': self.pols,
                  'vis_units': self.UV.vis_units,
                  'obs': self.obs,
                  'outpath': self.outpath,
                  'flag_choice': self.flag_choice}
        self.INS = INS(**kwargs)

    def VDH_prepare(self, bins='auto', fit=True, window=None):

        kwargs = {'data': self.UV.data_array,
                  'flag_choice': self.flag_choice,
                  'freq_array': self.UV.freq_array,
                  'pols': self.pols,
                  'vis_units': self.UV.vis_units,
                  'obs': self.obs,
                  'outpath': self.outpath,
                  'bins': bins,
                  'fit': fit}
        self.VDH = VDH(**kwargs)
        if window is not None:
            self.VDH.rev_ind(self.UV.data_array, window)

    def MF_prepare(self, sig_thresh=None, shape_dict={}, N_thresh=0, alpha=None,
                   tests=['match']):

        if not hasattr(self, 'INS'):
            self.INS_prepare()
        self.MF = MF(self.INS, sig_thresh=sig_thresh, shape_dict=shape_dict,
                     N_thresh=N_thresh, alpha=alpha)
        if tests is not None:
            for test in tests:
                getattr(self.MF, 'apply_%s_test' % (test))()

    def ES_prepare(self, grid_lim=None, INS=None, sig_thresh=None, shape_dict={},
                   N_thresh=0, alpha=None, tests=['match'], choice=None, fit=True,
                   bins='auto', custom=None, MC_iter=int(1e4), grid_dim=50,
                   R_thresh=10):

        # Make a match filtered noise spectrum if one is not already passed
        if INS is None:
            MF_kwargs = {'sig_thresh': sig_thresh,
                         'shape_dict': shape_dict,
                         'N_thresh': N_thresh,
                         'alpha': alpha,
                         'tests': tests}
            self.MF_prepare(**MF_kwargs)
        else:
            self.INS = INS

        # Calculate MLE's with the INS flags in mind, and then apply choice of
        # non-INS flags to the data
        self.apply_flags(choice='INS', INS=self.INS)
        VDH_kwargs = {'bins': bins,
                      'fit': fit}
        self.VDH_prepare(**VDH_kwargs)
        self.apply_flags(choice=choice, custom=custom)

        ES_kwargs = {'data': self.UV.data_array,
                     'flag_choice': choice,
                     'events': self.INS.match_events,
                     'MLE': self.VDH.MLEs[-1],
                     'uvw_array': self.UV.uvw_array,
                     'vis_units': self.UV.vis_units,
                     'obs': self.obs,
                     'pols': self.pols,
                     'outpath': self.outpath,
                     'MC_iter': MC_iter,
                     'grid_dim': grid_dim,
                     'grid_lim': grid_lim,
                     'R_thresh': R_thresh,
                     'freq_array': self.UV.freq_array}

        self.ES = ES(**ES_kwargs)

        self.UV.data_array.mask = np.logical_and(self.UV.data_array.mask, self.ES.mask)
