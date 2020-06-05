import tensorflow as tf


def adj(A):
    """Correct hermitian adjoint
    Args:
        A: tf tensor of shape (..., n, m)
    Returns:
        tf tensor of shape (..., m, n), hermitian adjoint matrix"""

    return tf.math.conj(tf.linalg.matrix_transpose(A))


def _lower(X):
    """Returns the lower triangular part of a matrix without diagonal part.
    Args:
        X: tf tensor of shape (..., m, m)
    Returns:
        tf tensor of shape (..., m, m), a matrix without diagonal and upper
        triangular parts"""

    dim = X.shape[-1]
    dtype = X.dtype
    lower = tf.ones((dim, dim), dtype=dtype) - tf.linalg.diag(tf.ones((dim,),
                                                              dtype))
    lower = tf.linalg.band_part(lower, -1, 0)

    return lower * X


def _half(X):
    """Returns the lower triangular part of
    a matrix with half of diagonal part.
    Args:
        X: tf tensor of shape (..., m, m)
    Returns:
        tf tensor of shape (..., m, m), a matrix with half of diagonal and
        without upper triangular parts"""

    dim = X.shape[-1]
    dtype = X.dtype
    half = tf.ones((dim, dim),
                   dtype=dtype) - 0.5 * tf.linalg.diag(tf.ones((dim,), dtype))
    half = tf.linalg.band_part(half, -1, 0)

    return half * X


def _pull_back_chol(W, L, inv_L):
    """Takes a tangent vector to a point from S++ and
    computes the corresponding tangent vector to the
    corresponding point from L+
    Args:
        W: tf tensor of shape (..., m, m), tangent vector
        L: tf tensor of shape (..., m, m), triangular matrix from L+
        inv_L: tf tensor of shape (..., m, m), inverse L
    Returns:
        tf tensor of shape (..., m, m), tangent vector to corresponding
        point in L+"""

    X = inv_L @ W @ adj(inv_L)
    X = L @ (_half(X))

    return X


def _push_forward_chol(X, L):
    """Takes a tangent vector to a point from L+ and
    computes the corresponding tangent vector to the
    corresponding point from S++
    Args:
        X: tf tensor of shape (..., m, m), tangent vector
        L: tf tensor of shape (..., m, m), triangular matrix from L+
    Returns:
        tf tensor of shape (..., m, m), tangent vector to corresponding
        point in S++"""

    return L @ adj(X) + X @ adj(L)


def _f_matrix(lmbd):
    """Returns f matrix (part of pull back and push forward)
    Args:
        lmbd: tf tensor of shape (..., m), eigenvalues of matrix
        from S
    Returns:
        tf tensor of shape (..., m, m), f matrix"""

    n = lmbd.shape[-1]
    l_i = lmbd[..., tf.newaxis]
    l_j = lmbd[..., tf.newaxis, :]
    denom = tf.math.log(l_i / l_j) + tf.eye(n, dtype=lmbd.dtype)
    return (l_i - l_j) / denom + tf.linalg.diag(lmbd)


def _pull_back_log(W, U, lmbd):
    """Takes a tangent vector to a point from S++ and
    computes the corresponding tangent vector to the
    corresponding point from S
    Args:
        W: tf tensor of shape (..., m, m), tangent vector
        U: tf tensor of shape (..., m, m), unitary matrix
        from eigen decomposition of a point from S++
        lmbd: tf tensor of shape (..., m), eigenvalues of
        a point from S++
    Returns:
        tf tensor of shape (..., m, m), tangent vector to corresponding
        point in S"""

    f = _f_matrix(lmbd)
    return U @ ((1 / f) * (adj(U) @ W @ U)) @ adj(U)


def _push_forward_log(W, U, lmbd):
    """Takes a tangent vector to a point from S and
    computes the corresponding tangent vector to the
    corresponding point from S++
    Args:
        W: tf tensor of shape (..., m, m), tangent vector
        U: tf tensor of shape (..., m, m), unitary matrix
        from eigen decomposition of a point from S
        lmbd: tf tensor of shape (..., m), eigenvalues of
        a point from S
    Returns:
        tf tensor of shape (..., m, m), tangent vector to corresponding
        point in S++"""

    f = _f_matrix(lmbd)
    return U @ (f * (adj(U) @ W @ U)) @ adj(U)
