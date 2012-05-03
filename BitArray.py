# -*- coding: utf-8 -*-

class BitArray:

	def __init__(self, data):
		self._Data = data
		
		self._DataBitsLeft = len(data) * 8

		self._ByteIdx = 0
		self._BitIdx = 0
	
	def mask(self, bitcount):
		return (1 << bitcount) - 1

	def read(self, bitsleftcount):

		result = 0
		bitsdonecount = 0
		while bitsleftcount:
			curbitsleftcount = 8 - self._BitIdx
			curdata = ord(self._Data[self._ByteIdx]) & self.mask(curbitsleftcount)
			
			if curbitsleftcount >= bitsleftcount:
				result <<= bitsleftcount				
				result |= curdata >> (curbitsleftcount - bitsleftcount)
				self._BitIdx += bitsleftcount
				bitsleftcount = 0
			else:
				result <<= curbitsleftcount
				result |= curdata
				bitsleftcount -= curbitsleftcount
				self._BitIdx += curbitsleftcount
			
			if self._BitIdx >= 8:
				self._BitIdx = 0
				self._ByteIdx += 1
				
		return result

