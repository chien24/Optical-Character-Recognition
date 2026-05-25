from pathlib import Path
import cv2
import numpy as np
from PIL import Image

# Simple rotated-crop utility (same logic as paddle adapter)

def _order_points_clockwise(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _get_rotate_crop_image(img: np.ndarray, points: np.ndarray) -> np.ndarray:
    pts = points.astype(np.float32)
    if pts.shape[0] != 4:
        pts = pts.reshape(-1, 2)

    rect = _order_points_clockwise(pts)
    (tl, tr, br, bl) = rect
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = max(int(heightA), int(heightB))

    if maxWidth <= 0 or maxHeight <= 0:
        x_min = int(np.min(pts[:, 0]))
        x_max = int(np.max(pts[:, 0]))
        y_min = int(np.min(pts[:, 1]))
        y_max = int(np.max(pts[:, 1]))
        return img[y_min:y_max, x_min:x_max]

    dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    return warped


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    sample = root / 'paddle' / 'vietnamese-ocr' / 'samples' / 'doanvan1.png'
    if not sample.exists():
        print('Sample image not found:', sample)
        raise SystemExit(1)

    img_bgr = cv2.imread(str(sample))
    h, w = img_bgr.shape[:2]

    # Make a slightly rotated rectangle near the top-third of the image
    pts = np.array([
        [int(0.05 * w), int(0.15 * h)],
        [int(0.95 * w), int(0.10 * h)],
        [int(0.95 * w), int(0.25 * h)],
        [int(0.05 * w), int(0.30 * h)],
    ], dtype=np.float32)

    crop = _get_rotate_crop_image(img_bgr, pts)
    out = Path(__file__).resolve().parent / 'out_crop.png'
    crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    Image.fromarray(crop_rgb).save(str(out))
    print('Saved rotated crop to', out)
