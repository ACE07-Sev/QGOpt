import tensorflow as tf
from QGOpt.manifolds import base_manifold
from QGOpt.manifolds.utils import adj
from QGOpt.manifolds.utils import _lower
from QGOpt.manifolds.utils import _pull_back_chol
from QGOpt.manifolds.utils import _pull_back_log
from QGOpt.manifolds.utils import _push_forward_log
from QGOpt.manifolds.utils import _f_matrix


class PositiveCone(base_manifold.Manifold):
    """The manifold of Hermitian positive definite matrices of size nxn.
    The manifold is equipped with two types of metric: Log-Cholesky metric
    and Log-Euclidean metric. The geometry of the manifold with Log-Cholesky
    metric is taken from

    Lin, Z. (2019). Riemannian Geometry of Symmetric Positive Definite Matrices
    via Cholesky Decomposition. SIAM Journal on Matrix Analysis and Applications,
    40(4), 1353-1370.

    The geometry of the manifold with Log-Euclidean metric is described for
    instance in

    Huang, Z., Wang, R., Shan, S., Li, X., & Chen, X. (2015, June).
    Log-euclidean metric learning on symmetric positive definite manifold
    with application to image set classification. In International
    conference on machine learning (pp. 720-729).

    Args:
        metric: string specifies type of a metric, Defaults to 'log_cholesky'
            Types of metrics are available: 'log_cholesky', 'log_euclidean.'"""

    def __init__(self, metric='log_cholesky'):

        list_of_metrics = ['log_cholesky', 'log_euclidean']
        if metric not in list_of_metrics:
            raise ValueError("Incorrect metric")
        self.metric = metric

    def inner(self, u, vec1, vec2):
        """Returns manifold wise inner product of vectors from
        a tangent space.

        Args:
            u: complex valued tensor of shape (..., n, n),
                a set of points from the manifold.
            vec1: complex valued tensor of shape (..., n, n),
                a set of tangent vectors from the manifold.
            vec2: complex valued tensor of shape (..., n, n),
                a set of tangent vectors from the manifold.

        Returns:
            complex valued tensor of shape (..., 1, 1),
                manifold wise inner product."""

        if self.metric == 'log_euclidean':
            lmbd, U = tf.linalg.eigh(u)
            W = _pull_back_log(vec1, U, lmbd)
            V = _pull_back_log(vec2, U, lmbd)

            prod = tf.math.real(tf.linalg.trace(adj(W) @ V))
            prod = prod[..., tf.newaxis, tf.newaxis]
            prod = tf.cast(prod, dtype=u.dtype)

            return prod

        elif self.metric == 'log_cholesky':
            L = tf.linalg.cholesky(u)
            inv_L = tf.linalg.inv(L)

            X = _pull_back_chol(vec1, L, inv_L)
            Y = _pull_back_chol(vec2, L, inv_L)

            diag_inner = tf.math.conj(tf.linalg.diag_part(X)) *\
                tf.linalg.diag_part(Y) / (tf.linalg.diag_part(L) ** 2)
            diag_inner = tf.reduce_sum(diag_inner, axis=-1)
            triag_inner = tf.reduce_sum(tf.math.conj(_lower(X)) * _lower(Y),
                                        axis=(-2, -1))

            prod = tf.math.real(diag_inner + triag_inner)
            prod = prod[..., tf.newaxis, tf.newaxis]
            prod = tf.cast(prod, dtype=u.dtype)

            return prod

    def proj(self, u, vec):
        """Returns projection of vectors on a tangen space
        of the manifold.

        Args:
            u: complex valued tensor of shape (..., n, n),
                a set of points from the manifold.
            vec: complex valued tensor of shape (..., n, n),
                a set of vectors to be projected.

        Returns:
            complex valued tensor of shape (..., n, n),
            a set of projected vectors."""

        return (vec + adj(vec)) / 2

    def egrad_to_rgrad(self, u, egrad):
        """Returns the Riemannian gradient from an Euclidean gradient.

        Args:
            u: complex valued tensor of shape (..., n, n),
                a set of points from the manifold.
            egrad: complex valued tensor of shape (..., n, n),
                a set of Euclidean gradients.

        Returns:
            complex valued tensor of shape (..., n, n),
            the set of Reimannian gradients."""

        if self.metric == 'log_euclidean':
            lmbd, U = tf.linalg.eigh(u)
            f = _f_matrix(lmbd)
            # Riemannian gradient
            E = adj(U) @ ((egrad + adj(egrad)) / 2) @ U
            R = U @ (E * f * f) @ adj(U)
            return R

        elif self.metric == 'log_cholesky':
            n = u.shape[-1]
            dtype = u.dtype
            L = tf.linalg.cholesky(u)

            half = tf.ones((n, n),
                           dtype=dtype) - tf.linalg.diag(tf.ones((n,), dtype))
            G = tf.linalg.band_part(half, -1, 0) +\
                tf.linalg.diag(tf.linalg.diag_part(L) ** 2)

            R = L @ adj(G * (egrad @ L))
            R = 2 * (R + adj(R))

            return R

    def retraction(self, u, vec):
        """Transports a set of points from the manifold via a
        retraction map.

        Args:
            u: complex valued tensor of shape (..., n, n), a set
                of points to be transported.
            vec: complex valued tensor of shape (..., n, n),
                a set of direction vectors.

        Returns:
            complex valued tensor of shape (..., n, n),
            a set of transported points."""

        if self.metric == 'log_euclidean':
            lmbd, U = tf.linalg.eigh(u)
            # geodesic in S
            Su = U @ tf.linalg.diag(tf.math.log(lmbd)) @ adj(U)
            Svec = _pull_back_log(vec, U, lmbd)
            Sresult = Su + Svec

            return tf.linalg.expm(Sresult)

        elif self.metric == 'log_cholesky':
            L = tf.linalg.cholesky(u)
            inv_L = tf.linalg.inv(L)

            X = _pull_back_chol(vec, L, inv_L)

            inv_diag_L = tf.linalg.diag(1 / tf.linalg.diag_part(L))

            cholesky_retraction = _lower(L) + _lower(X) +\
                tf.linalg.band_part(L, 0, 0) *\
                tf.exp(tf.linalg.band_part(X, 0, 0) * inv_diag_L)

            return cholesky_retraction @ adj(cholesky_retraction)

    def vector_transport(self, u, vec1, vec2):
        """Returns a vector tranported along an another vector
        via vector transport.

        Args:
            u: complex valued tensor of shape (..., n, n),
                a set of points from the manifold, starting points.
            vec1: complex valued tensor of shape (..., n, n),
                a set of vectors to be transported.
            vec2: complex valued tensor of shape (..., n, n),
                a set of direction vectors.

        Returns:
            complex valued tensor of shape (..., n, n),
            a set of transported vectors."""

        if self.metric == 'log_euclidean':
            lmbd, U = tf.linalg.eigh(u)
            # geoidesic in S
            Su = U @ tf.linalg.diag(tf.math.log(lmbd)) @ adj(U)
            Svec2 = _pull_back_log(vec2, U, lmbd)
            Sresult = Su + Svec2
            # eig decomposition of a new point from S
            log_new_lmbd, new_U = tf.linalg.eigh(Sresult)
            # new lmbd
            new_lmbd = tf.exp(log_new_lmbd)
            # transported vector
            new_vec1 = _push_forward_log(_pull_back_log(vec1, U, lmbd),
                                         new_U, new_lmbd)

            return new_vec1

        elif self.metric == 'log_cholesky':
            v = self.retraction(u, vec2)

            L = tf.linalg.cholesky(u)
            inv_L = tf.linalg.inv(L)

            inv_diag_L = tf.linalg.diag(1 / tf.linalg.diag_part(L))

            X = _pull_back_chol(vec1, L, inv_L)

            K = tf.linalg.cholesky(v)

            L_transport = _lower(X) + tf.linalg.band_part(K, 0, 0) *\
                inv_diag_L * tf.linalg.band_part(X, 0, 0)

            return K @ adj(L_transport) + L_transport @ adj(K)

    def retraction_transport(self, u, vec1, vec2):
        """Performs a retraction and a vector transport simultaneously.

        Args:
            u: complex valued tensor of shape (..., n, n),
                a set of points from the manifold, starting points.
            vec1: complex valued tensor of shape (..., n, n),
                a set of vectors to be transported.
            vec2: complex valued tensor of shape (..., n, n),
                a set of direction vectors.

        Returns:
            two complex valued tensors of shape (..., n, n),
            a set of transported points and vectors."""

        if self.metric == 'log_euclidean':
            lmbd, U = tf.linalg.eigh(u)
            # geoidesic in S
            Su = U @ tf.linalg.diag(tf.math.log(lmbd)) @ adj(U)
            Svec2 = _pull_back_log(vec2, U, lmbd)
            Sresult = Su + Svec2
            # eig decomposition of new point from S
            log_new_lmbd, new_U = tf.linalg.eigh(Sresult)
            # new point from S++
            new_point = new_U @ tf.linalg.diag(tf.exp(log_new_lmbd)) @\
                adj(new_U)
            # new lmbd
            new_lmbd = tf.exp(log_new_lmbd)
            # transported vector
            new_vec1 = _push_forward_log(_pull_back_log(vec1, U, lmbd),
                                         new_U, new_lmbd)

            return new_point, new_vec1

        elif self.metric == 'log_cholesky':
            v = self.retraction(u, vec2)

            L = tf.linalg.cholesky(u)
            inv_L = tf.linalg.inv(L)

            inv_diag_L = tf.linalg.diag(1 / tf.linalg.diag_part(L))

            X = _pull_back_chol(vec1, L, inv_L)

            K = tf.linalg.cholesky(v)

            L_transport = _lower(X) + tf.linalg.band_part(K, 0, 0) *\
                inv_diag_L * tf.linalg.band_part(X, 0, 0)

            return v, K @ adj(L_transport) + L_transport @ adj(K)

    def random(self, shape, dtype=tf.complex64):
        """Returns a set of points from the manifold generated
        randomly.

        Args:
            shape: tuple of integer numbers (..., n, n),
                shape of a generated matrix.
            dtype: type of an output tensor, can be
                either tf.complex64 or tf.complex128.

        Returns:
            complex valued tensor of shape (..., n, n),
            a generated matrix."""

        list_of_dtypes = [tf.complex64, tf.complex128]

        if dtype not in list_of_dtypes:
            raise ValueError("Incorrect dtype")
        real_dtype = tf.float64 if dtype == tf.complex128 else tf.float32

        u = tf.complex(tf.random.normal(shape, dtype=real_dtype),
                       tf.random.normal(shape, dtype=real_dtype))
        u = tf.linalg.adjoint(u) @ u
        return u
