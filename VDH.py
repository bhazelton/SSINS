import numpy as np
import scipy.stats
import os


class Hist:

    def __init__(self, data, flag_choice, freq_array, pols, vis_units, obs,
                 outpath, bins='auto'):

        args = {'flag_choice': flag_choice, 'freq_array': freq_array, 'pols': pols,
                'vis_units': vis_units, 'obs': obs, 'outpath': outpath}
        for attr in args:
            setattr(self, attr, args[attr])
        self.counts, self.bins = self.hist_make(data, bins=bins)
        self.MLEs, self.fits, self.errors = self.rayleigh_mixture_fit(data)
        for string in ['arrs', 'figs']:
            if not os.path.exists('%s/%s' % (self.outpath, string)):
                os.makedirs('%s/%s' % (self.outpath, string))

    def hist_make(self, data, bins='auto'):
        counts = np.zeros([data.shape[2], 2], dtype=object)
        bins = np.copy(counts)
        for spw in range(data.shape[2]):
            for i in range(1 + bool(self.flag_choice)):
                if i:
                    temp_counts, temp_bins = np.histogram(data[:, :, spw][np.logical_not(data[:, :, spw].mask)], bins=bins)
                else:
                    temp_counts, temp_bins = np.histogram(data[:, :, spw], bins=bins)
                counts[spw, i] = temp_counts
                bins[spw, i] = temp_bins
        return(counts, bins)

    def rayleigh_mixture_fit(self, data):
        MLEs = []
        fits = np.zeros([data.shape[2], 2], dtype=object)
        errors = np.copy(fits)
        for i in range(1 + bool(self.flag_choice)):
            if i:
                MLE = 0.5 * np.mean(data**2, axis=0)
                N = np.count_nonzero(np.logical_not(data.mask), axis=0)
            else:
                # copy does not copy the mask
                dat = np.copy(data)
                MLE = 0.5 * np.mean(dat**2, axis=0)
                N = np.count_nonzero(dat, axis=0)
            MLEs.append(MLE)
            for spw in data.shape[2]:
                Ntot = np.sum(N[:, spw])
                for mle, n in zip(MLE[:, spw].flatten(), N[:, spw].flatten()):
                    P += n / Ntot * (scipy.stats.rayleigh.cdf(self.bins[spw, i][1:], scale=np.sqrt(mle)) -
                                     scipy.stats.rayleigh.cdf(self.bins[spw, i][:-1], scale=np.sqrt(mle)))
                fit = Ntot * P
                error = np.sqrt(Ntot * P * (1 - P))
                fits[spw, i] = fit
                errors[spw, i] = error
        return(MLEs, fits, errors)

    def rev_ind(data, window):
        self.W_hist = []
        for i in range(1 + bool(self.flag_choice)):
            W = np.zeros(data.shape)
            if i:
                dat = data
            else:
                # Copying the array does not copy the mask
                dat = np.copy(data)
            W[np.logical_and(min(window) < dat, dat < max(window))] = 1
        self.W_hist.append(W.sum(axis=1))
