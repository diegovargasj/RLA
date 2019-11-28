class DHondt:
    def __init__(self, alpha, M, P, t, sw, sl, W):
        self.alpha = alpha
        self.M = M
        self.m = 0
        self.P = P
        self.T = [[1 for i in P] for j in P]
        self.t = t
        self.sw = sw
        self.sl = sl
        self.W = W

    def gamma_pos(self, p, q):
        return self.t[p] / (self.t[p] + self.t[q]) * (self.sw[p] + self.sl[q]) / self.sw[p]

    def gamma_neg(self, p, q):
        return (1 - self.t[p] / (self.t[p] + self.t[q])) * (1 - (self.sw[p] + self.sl[q]) / self.sw[p])

    def audit(self, c):
        self.m += 1
        if c in self.W:
            p = c
            for q in self.P:
                if q != p and self.T[p][q] >= 1.0 / self.alpha:
                    self.T[p][q] *= self.gamma_pos(p, q)
        else:
            q = c
            for p in self.P:
                if p != q and self.T[p][q] >= 1.0 / self.alpha:
                    self.T[p][q] *= self.gamma_neg(p, q)

    def verified(self):
        for p in self.P:
            for q in self.P:
                if p != q and self.T[p][q] < 1.0 / self.alpha:
                    return False

        return True



