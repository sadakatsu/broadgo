from typing import Union

import numpy as np
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

MAX_MISTAKE = 361. * 2.
MIDDLE = MAX_MISTAKE * 4.
BUCKETS = int(MAX_MISTAKE * 8 + 1)


class ScoringProcedure:
    def __init__(self, hyperparameters_path):
        with open(hyperparameters_path, 'rb') as infile:
            configuration = np.load(infile, allow_pickle=True)
            self._lda: LinearDiscriminantAnalysis = configuration['lda'].item()
            self._magnitude: float = configuration['magnitude'].item()
            self._pca: PCA = configuration['pca'].item()
            self._reference: np.array = configuration['reference']
            self._start: np.array = configuration['start']
            self._worst: float = configuration['worst'].item()
            self._scale = configuration['best'] - self._worst

    def score(self, performance) -> Union[float, np.array]:
        features = ScoringProcedure._transform_to_features(performance)
        pca_space = self._pca.transform(features)
        lda_space = self._lda.transform(pca_space)
        proportion = (lda_space - self._start).dot(self._reference) / self._magnitude

        # I have shunted the scale so that they should usually be from 0 to 100 from now on.
        real_qs = 100. * (proportion - self._worst) / self._scale
        return 100. * (real_qs + 69.56979359) / (111.1304904 + 69.56979359)

    @staticmethod
    def _transform_to_features(performance) -> np.array:
        """The feature vector's composition:
            Number of moves / 200 (attempted normalization)
            p(Mistake)
            Distribution for deltas
            Cumulative proportion of moves better than the referred move score
            Cumulative proportion of moves worse than the referred move score"""
        moves = len(performance)
        total_observations = moves + 1

        observations = np.full(BUCKETS, 1. / BUCKETS)
        for move in performance:
            clamped = round(ScoringProcedure._clamp(move, -MAX_MISTAKE, MAX_MISTAKE) * 4)
            index = int(clamped + MIDDLE)
            observations[index] += 1
        distribution = observations / total_observations

        better = np.zeros(BUCKETS)
        worse = np.zeros(BUCKETS)
        for i, proportion in enumerate(distribution):
            if i > 0:
                better[i] = distribution[i - 1] + better[i - 1]
            if i < moves:
                worse[i] = 1. - better[i] - distribution[i]

        return np.append(
                [moves / 200., np.sum(performance >= 0.5) / moves],
                [distribution, better, worse]
            ).reshape(1, -1)

    @staticmethod
    def _clamp(value, minimum, maximum):
        if value < minimum:
            result = minimum
        elif value > maximum:
            result = maximum
        else:
            result = value
        return result
