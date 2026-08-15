import warnings

import cv2
import numpy as np

warnings.filterwarnings("ignore", category=UserWarning)


class Image:

    def __init__(self, img):
        self.img = img

    def __getattr__(self, attr):
        return getattr(self.img, attr)

    def copy(self):
        return self.__class__(self.img.copy())

    def crop(self, top_left, bottom_right, resize=None):
        self.img = self.img[top_left[0]:bottom_right[0], top_left[1]:bottom_right[1]]
        if resize is not None:
            self.resize(resize)

    def normalise(self):
        self.img = self.img.astype(np.float32) / 255.0
        self.img -= self.img.mean()

    def resize(self, shape):
        if self.img.shape == shape:
            return
        self.img = cv2.resize(self.img, (shape[1], shape[0])).astype(self.img.dtype)


class DepthImage(Image):
    def __init__(self, img):
        super().__init__(img)

    def normalise(self):
        self.img = np.clip((self.img - self.img.mean()), -1, 1)
