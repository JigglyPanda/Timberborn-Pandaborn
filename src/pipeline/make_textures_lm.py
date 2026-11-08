import numpy as np
def front_point(d, x, y, tol):
    P = d['P']
    s = (np.abs(P[:, 0] - x) < tol) & (np.abs(P[:, 1] - y) < tol) & (d['head'] > 0.5) & (d['teeth'] < 0.5)
    return P[np.argmax(np.where(s, P[:, 2], -9))]
