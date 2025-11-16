import numpy as np
try:
    import cv2
except Exception:
    cv2 = None

def find_vertical_overlap(img1: np.ndarray, img2: np.ndarray, max_overlap: int = 300) -> int:
    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]
    w = min(w1, w2)
    a = img1[:, :w]
    b = img2[:, :w]
    a_gray = np.mean(a, axis=2)
    b_gray = np.mean(b, axis=2)
    best_off = 0
    best_err = float('inf')
    max_overlap = min(max_overlap, h1, h2)
    for off in range(0, max_overlap):
        a_strip = a_gray[h1 - off : h1, :]
        b_strip = b_gray[0 : off, :]
        if a_strip.shape != b_strip.shape:
            continue
        err = np.mean(np.abs(a_strip - b_strip))
        if err < best_err:
            best_err = err
            best_off = off
    return best_off

def jam_overlap(img1: np.ndarray, img2: np.ndarray):
    if cv2 is None:
        return 0, 0, 0, 0
    try:
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]
        w = min(w1, w2)
        a = img1[:, :w]
        b = img2[:, :w]
        ga = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
        gb = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
        try:
            sift = cv2.SIFT_create()
        except Exception:
            return 0, 0, 0, 0
        kps1, des1 = sift.detectAndCompute(ga, None)
        kps2, des2 = sift.detectAndCompute(gb, None)
        if des1 is None or des2 is None or len(kps1) < 4 or len(kps2) < 4:
            return 0, 0, 0, 0
        index_params = dict(algorithm=1, trees=5)
        search_params = dict(checks=64)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(des1, des2, k=2)
        goods = []
        for m in matches:
            if len(m) == 2 and m[0].distance < 0.6 * m[1].distance:
                q = kps1[m[0].queryIdx].pt
                t = kps2[m[0].trainIdx].pt
                ig_top = int(min(h1, h2) * 0.05)
                ig_bot = int(min(h1, h2) * 0.05)
                if (ig_top <= q[1] <= h1 - ig_bot) and (ig_top <= t[1] <= h2 - ig_bot):
                    goods.append(m[0])
        if len(goods) < 4:
            return 0, 0, 0, len(goods)
        freq = {}
        for g in goods:
            dy = int(round(kps1[g.queryIdx].pt[1] - kps2[g.trainIdx].pt[1]))
            if abs(dy) > max(h1, h2):
                continue
            freq[dy] = freq.get(dy, 0) + 1
        if not freq:
            return 0, 0, 0, len(goods)
        distancesmode = max(freq.items(), key=lambda kv: kv[1])[0]
        max1y = 0.0
        max2y = 0.0
        for g in goods:
            pos0 = kps1[g.queryIdx].pt
            pos1 = kps2[g.trainIdx].pt
            if int(pos0[1] - pos1[1]) == distancesmode:
                if pos0[1] > max1y:
                    max1y = pos0[1]
                if pos1[1] > max2y:
                    max2y = pos1[1]
        off = int(max(0, distancesmode))
        c1 = int(min(h1, max1y))
        c2 = int(min(h2, max2y))
        return off, c1, c2, len(goods)
    except Exception:
        return 0, 0, 0, 0

def overlap_error(a: np.ndarray, b: np.ndarray, off: int) -> float:
    h1, w1 = a.shape[:2]
    h2, w2 = b.shape[:2]
    w = min(w1, w2)
    off = max(1, min(min(h1, h2) - 1, int(off)))
    x1 = a[h1 - off : h1, :w].astype(np.float32)
    x2 = b[0 : off, :w].astype(np.float32)
    if x1.shape != x2.shape or x1.size == 0:
        return 1e9
    return float(np.mean(np.abs(x1 - x2)))

def refine_overlap(a: np.ndarray, b: np.ndarray, init_off: int) -> int:
    h1 = a.shape[0]
    h2 = b.shape[0]
    base = max(1, min(min(h1, h2) - 1, int(init_off)))
    win = int(max(8, min(48, base // 2)))
    best_off = base
    best_err = overlap_error(a, b, base)
    for d in range(-win, win + 1):
        o = base + d
        err = overlap_error(a, b, o)
        if err < best_err:
            best_err = err
            best_off = o
    return int(best_off)

def sticky_top(a: np.ndarray, b: np.ndarray, limit: int = 140, th: float = 2.0) -> int:
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    top = 0
    step = 8
    lim = min(limit, h)
    af = a.astype(np.float32)
    bf = b.astype(np.float32)
    for k in range(step, lim + 1, step):
        x1 = af[0:k, :w]
        x2 = bf[0:k, :w]
        err = np.mean(np.abs(x1 - x2))
        if err <= th:
            top = k
        else:
            break
    return int(top)

def blend_vertical(base: np.ndarray, cur: np.ndarray, off: int, blend: int = 12) -> np.ndarray:
    h1 = base.shape[0]
    h2 = cur.shape[0]
    w = min(base.shape[1], cur.shape[1])
    off = max(1, min(min(h1, h2) - 1, int(off)))
    b = base[:, :w].astype(np.float32)
    c = cur[:, :w].astype(np.float32)
    cut_a = max(0, h1 - off)
    cut_b = max(0, off)
    bo = b[cut_a:h1]
    co = c[0:off]
    H = bo.shape[0]
    W = bo.shape[1]
    if H == 0 or W == 0:
        return np.vstack([b, c]).astype(np.uint8)
    diff = np.mean(np.abs(bo - co), axis=2)
    dp = np.zeros_like(diff)
    ptr = np.zeros((H, W), dtype=np.int16)
    dp[:, 0] = diff[:, 0]
    for j in range(1, W):
        prev = dp[:, j - 1]
        m0 = prev
        m1 = np.concatenate((np.array([1e9], dtype=prev.dtype), prev[:-1]))
        m2 = np.concatenate((prev[1:], np.array([1e9], dtype=prev.dtype)))
        stack = np.stack([m0, m1, m2], axis=0)
        idx = np.argmin(stack, axis=0)
        dp[:, j] = diff[:, j] + np.min(stack, axis=0)
        ptr[:, j] = idx.astype(np.int16) - 1
    path = np.zeros(W, dtype=np.int32)
    i = int(np.argmin(dp[:, W - 1]))
    path[W - 1] = i
    for j in range(W - 1, 0, -1):
        i = i + int(ptr[i, j])
        if i < 0:
            i = 0
        elif i >= H:
            i = H - 1
        path[j - 1] = i
    ov = np.empty((H, W, 3), dtype=np.float32)
    for j in range(W):
        s = int(path[j])
        if s > 0:
            ov[:s, j, :] = bo[:s, j, :]
        if s < H:
            ov[s:, j, :] = co[s:, j, :]
    head = b[:cut_a, :W]
    tail = c[cut_b:, :W]
    out = np.vstack([head, ov, tail]).astype(np.uint8)
    return out