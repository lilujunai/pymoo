import numpy as np
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans

from pymoo.model.indicator import Indicator
from pymoo.util.non_dominated_rank import NonDominatedRank


class RMetric(Indicator):
    def __init__(self, curr_pop, whole_pop, ref_points, problem, w=None):
        Indicator.__init__(self)
        self.curr_pop = curr_pop
        self.whole_pop = whole_pop
        self.ref_points = ref_points
        self.problem = problem
        w_ = np.ones(self.ref_points.shape[1]) if not w else w
        self.w_points = self.ref_points + 2 * w_


    def _filter(self):

        def check_dominance(a, b, n_obj):
            flag1 = False
            flag2 = False
            for i in range(n_obj):
                if a[i] < b[i]:
                    flag1 = True
                else:
                    if a[i] > b[i]:
                        flag2 = True
            if flag1 and not flag2:
                return 1
            elif not flag1 and flag2:
                return -1
            else:
                return 0

        num_objs = np.size(self.curr_pop, axis=1)
        index_array = np.zeros(np.size(self.curr_pop, axis=0))
        for i in range(np.size(self.curr_pop, 0)):
            for j in range(np.size(self.whole_pop, 0)):
                flag = check_dominance(self.curr_pop[i, :], self.whole_pop[j, :], num_objs)
                if flag == -1:
                    index_array[i] = 1
                    break
        final_index = np.logical_not(index_array)
        filtered_pop = self.curr_pop[final_index, :]

        return filtered_pop

    def _filter_fast(self):
        filtered_pop = NonDominatedRank.get_non_dominated(self.whole_pop, self.curr_pop)
        return filtered_pop

    def _preprocess(self, data, ref_point, w_point):

        datasize = np.size(data, 0)

        # Identify representative point
        ref_matrix = np.tile(ref_point, (datasize, 1))
        w_matrix = np.tile(w_point, (datasize, 1))
        # ratio of distance to the ref point over the distance between the w_point and the ref_point
        diff_matrix = (data-ref_matrix)/(w_matrix-ref_matrix)
        agg_value = np.amax(diff_matrix, axis=1)
        idx = np.argmin(agg_value)
        zp = [data[idx, :]]

        return zp,


    def _translate(self, zp, trimmed_data, ref_point, w_point):
        # Solution translation - Matlab reproduction
        # find k
        temp = ((zp[0]-ref_point)/(w_point - ref_point))
        kIdx = np.argmax(temp)

        # find zl
        temp = (zp[0][kIdx] - ref_point[kIdx])/(w_point[kIdx] - ref_point[kIdx])
        zl = ref_point + temp*(w_point - ref_point)

        temp = zl - zp
        shift_direction = np.tile(temp, (trimmed_data.shape[0], 1))
        # new_size = self.curr_pop.shape[0]
        return trimmed_data + shift_direction


    def _trim(self, pop, centeroid, range=0.2):
        popsize, objDim = pop.shape
        diff_matrix = pop - np.tile(centeroid,(popsize, 1))[0]
        flags = np.sum(abs(diff_matrix) < range/2, axis=1)
        filtered_matrix = pop[np.where(flags == objDim)]
        return filtered_matrix

    def _trim_fast(self, pop, centeroid, range=0.2):
        centeroid_matrix = cdist(pop, centeroid, metric='euclidean')
        filtered_matrix = pop[np.where(centeroid_matrix < range/2), :][0]
        return filtered_matrix

    def calc(self):

        translated = []
        final_PF = []

        # 1. Prescreen Procedure - NDS Filtering
        pop = self._filter_fast()

        solution = self.problem.calc_pareto_front()
        # solution = calc_PF(1, 10000, 2)

        labels = kmeans(pop, self.ref_points)
        # labels = np.argmin(cdist(pop, self.ref_points), axis=1)

        for i in range(len(self.ref_points)):
            cluster = pop[np.where(labels == i)]
            if len(cluster) != 0:

                # 2. Representative Point Identification
                zp = self._preprocess(cluster, self.ref_points[i], w_point=self.w_points[i])[0]
                # 3. Filtering Procedure - Filter points
                trimmed_data = self._trim(cluster, zp)
                # trimmed_data = self.trim_fast(data, zp, radius)  -- Broken
                # 4. Solution Translation
                pop_t = self._translate(zp, trimmed_data, self.ref_points[i], w_point=self.w_points[i])
                translated.extend(pop_t)

            # 5. R-Metric Computation
            target = self._preprocess(data=solution, ref_point=self.ref_points[i], w_point=self.w_points[i])
            PF = self._trim(solution, target)
            final_PF.extend(PF)

        translated = np.array(translated)

        if np.size(translated) == 0:
            igd = -1
            HV = -1
        else:
            # IGD Computation
            from pymoo.indicators.igd import IGD
            IGD_ = IGD(final_PF)
            igd = IGD_.calc(translated)
            # HV Computation

            nadir_point = np.amax(self.w_points, axis=0)
            front = translated

            # volume = hypervolume(front, nadir_point)
            # pop_ = pygmo.population(prob=pygmo.dtlz(prob_id=2), dim=14, fdim=5)

            # hv = pygmo.hypervolume(pop=pop_)
            # volume = hv.compute(nadir_point)
            # hv = HyperVolume(nadir_point)
            # volume = hv.compute(front)

        return igd, volume


def kmeans(data, k):

    # Number of clusters
    kmeans = KMeans(n_clusters=len(k))
    # Fitting the input data
    kmeans = kmeans.fit(data)
    # Getting the cluster labels
    labels = kmeans.predict(data)
    # Centroid values
    centroids = kmeans.cluster_centers_

    return labels

def calc_PF(problem_id, sample_size=10000, objDim=None):
    # ZDT 1
    if problem_id == 1:
        objDim = 2
        step = 1/(sample_size - 1)
        P = np.zeros((sample_size, objDim))
        f1 = np.arange(0, 1+step, step)[:, None]
        P[:, 0] = f1.T
        P[:, 1] = (np.ones((sample_size, 1)) - np.sqrt(P[:, 0])[:, None])[:,0]
        return P
    # ZDT 2
    if problem_id == 2:
        objDim = 2
        step = 1/(sample_size - 1)
        P = np.zeros((sample_size, objDim))
        f1 = np.arange(0, 1+step, step)[:, None]
        P = np.array([f1, 1 - np.power(f1, 2)]).T
        return P