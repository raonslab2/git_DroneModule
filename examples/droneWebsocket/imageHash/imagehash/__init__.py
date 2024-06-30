"""
Image hashing library
======================

Example:

>>> from PIL import Image
>>> import imagehash
>>> hash = imagehash.average_hash(Image.open('test.png'))
>>> print(hash)
d879f8f89b1bbf
>>> otherhash = imagehash.average_hash(Image.open('other.bmp'))
>>> print(otherhash)
ffff3720200ffff
>>> print(hash == otherhash)
False
>>> print(hash - otherhash)
36
>>> for r in range(1, 30, 5):
...     rothash = imagehash.average_hash(Image.open('test.png').rotate(r))
...     print('Rotation by %d: %d Hamming difference' % (r, hash - rothash))
...
Rotation by 1: 2 Hamming difference
Rotation by 6: 11 Hamming difference
Rotation by 11: 13 Hamming difference
Rotation by 16: 17 Hamming difference
Rotation by 21: 19 Hamming difference
Rotation by 26: 21 Hamming difference
>>>

"""

from PIL import Image
import numpy
#import scipy.fftpack
#import pywt

def _binary_array_to_hex(arr):
	"""
	internal function to make a hex string out of a binary array
	"""
	h = 0
	s = []
	for i, v in enumerate(arr.flatten()):
		if v: 
			h += 2**(i % 8)
		if (i % 8) == 7:
			s.append(hex(h)[2:].rjust(2, '0'))
			h = 0
	return "".join(s)

class ImageHash(object):
	"""
	Hash encapsulation. Can be used for dictionary keys and comparisons.
	"""
	def __init__(self, binary_array):
		self.hash = binary_array

	def __str__(self):
		return _binary_array_to_hex(self.hash.flatten())

	def __repr__(self):
		return repr(self.hash)

	def __sub__(self, other):
		if other is None:
			raise TypeError('Other hash must not be None.')
		if self.hash.size != other.hash.size:
			raise TypeError('ImageHashes must be of the same shape.', self.hash.shape, other.hash.shape)
		return (self.hash.flatten() != other.hash.flatten()).sum()

	def __eq__(self, other):
		if other is None:
			return False
		return numpy.array_equal(self.hash.flatten(), other.hash.flatten())

	def __ne__(self, other):
		if other is None:
			return False
		return not numpy.array_equal(self.hash.flatten(), other.hash.flatten())

	def __hash__(self):
		# this returns a 8 bit integer, intentionally shortening the information
		return sum([2**(i % 8) for i, v in enumerate(self.hash.flatten()) if v])

def hex_to_hash(hexstr):
	"""
	Convert a stored hash (hex, as retrieved from str(Imagehash))
	back to a Imagehash object.
	"""
	l = []
	if len(hexstr) != 16:
		raise ValueError('The hex string has the wrong length')
	for i in range(8):
		h = hexstr[i*2:i*2+2]
		v = int("0x" + h, 16)
		l.append([v & 2**i > 0 for i in range(8)])
	return ImageHash(numpy.array(l))


def average_hash(image, hash_size=8):
	"""
	Average Hash computation

	Implementation follows http://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html

	@image must be a PIL instance.
	"""
	image = image.convert("L").resize((hash_size, hash_size), Image.ANTIALIAS)
	pixels = numpy.array(image.getdata()).reshape((hash_size, hash_size))
	avg = pixels.mean()
	diff = pixels > avg
	# make a hash
	return ImageHash(diff)

def phash(image, hash_size=8, highfreq_factor=4):
	"""
	Perceptual Hash computation.

	Implementation follows http://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html

	@image must be a PIL instance.
	"""
	import scipy.fftpack
	img_size = hash_size * highfreq_factor
	image = image.convert("L").resize((img_size, img_size), Image.ANTIALIAS)
	pixels = numpy.array(image.getdata(), dtype=numpy.float).reshape((img_size, img_size))
	dct = scipy.fftpack.dct(scipy.fftpack.dct(pixels, axis=0), axis=1)
	dctlowfreq = dct[:hash_size, :hash_size]
	med = numpy.median(dctlowfreq)
	diff = dctlowfreq > med
	return ImageHash(diff)

def phash_simple(image, hash_size=8, highfreq_factor=4):
	"""
	Perceptual Hash computation.

	Implementation follows http://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html

	@image must be a PIL instance.
	"""
	import scipy.fftpack
	img_size = hash_size * highfreq_factor
	image = image.convert("L").resize((img_size, img_size), Image.ANTIALIAS)
	pixels = numpy.array(image.getdata(), dtype=numpy.float).reshape((img_size, img_size))
	dct = scipy.fftpack.dct(pixels)
	dctlowfreq = dct[:hash_size, 1:hash_size+1]
	avg = dctlowfreq.mean()
	diff = dctlowfreq > avg
	return ImageHash(diff)

def dhash(image, hash_size=8):
	"""
	Difference Hash computation.

	following http://www.hackerfactor.com/blog/index.php?/archives/529-Kind-of-Like-That.html

	@image must be a PIL instance.
	"""
	image = image.convert("L").resize((hash_size + 1, hash_size), Image.ANTIALIAS)
	pixels = numpy.array(image.getdata(), dtype=numpy.float).reshape((hash_size + 1, hash_size))
	# compute differences
	diff = pixels[1:, :] > pixels[:-1, :]
	return ImageHash(diff)


def whash(image, hash_size = 8, image_scale = None, mode = 'haar', remove_max_haar_ll = True):
	"""
	Wavelet Hash computation.
	
	based on https://www.kaggle.com/c/avito-duplicate-ads-detection/

	@image must be a PIL instance.
	@hash_size must be a power of 2 and less than @image_scale.
	@image_scale must be power of 2 and less than image size. By default is equal to max
		power of 2 for an input image.
	@mode (see modes in pywt library):
		'haar' - Haar wavelets, by default
		'db4' - Daubechies wavelets
	@remove_max_haar_ll - remove the lowest low level (LL) frequency using Haar wavelet.
	"""
	import pywt
	if image_scale is not None:
		assert image_scale & (image_scale - 1) == 0, "image_scale is not power of 2"
	else:
		image_scale = 2**int(numpy.log2(min(image.size)))
	ll_max_level = int(numpy.log2(image_scale))

	level = int(numpy.log2(hash_size))
	assert hash_size & (hash_size-1) == 0, "hash_size is not power of 2"
	assert level <= ll_max_level, "hash_size in a wrong range"
	dwt_level = ll_max_level - level

	image = image.convert("L").resize((image_scale, image_scale), Image.ANTIALIAS)
	pixels = numpy.array(image.getdata(), dtype=numpy.float).reshape((image_scale, image_scale))
	pixels /= 255

	# Remove low level frequency LL(max_ll) if @remove_max_haar_ll using haar filter
	if remove_max_haar_ll:
		coeffs = pywt.wavedec2(pixels, 'haar', level = ll_max_level)
		coeffs = list(coeffs)
		coeffs[0] *= 0
		pixels = pywt.waverec2(coeffs, 'haar')

	# Use LL(K) as freq, where K is log2(@hash_size)
	coeffs = pywt.wavedec2(pixels, mode, level = dwt_level)
	dwt_low = coeffs[0]

	# Substract median and compute hash
	med = numpy.median(dwt_low)
	diff = dwt_low > med
	return ImageHash(diff)

