import logging
import os
import uuid
import struct
import tempfile
import subprocess
import StringIO
import EfiDecompressor

logger = logging.getLogger(__name__)

class EFIGUIDS:
	FIRMWARE_VOLUME1 = uuid.UUID('{7a9354d9-0468-444a-81ce-0bf617d890df}')
	FIRMWARE_VOLUME2 = uuid.UUID('{8c8ce578-8a3d-4f1c-9935-896185c32dd3}')
	FIRMWARE_FILE_SECTION_GUID_DEFINED_LZMA_COMPRESSED = uuid.UUID('{ee4e5898-3914-4259-9d6e-dc7bd79403cf}')

class EfiElement(object):
	def __init__(self):
		pass

class EfiFirmwareImage(EfiElement):
	def __init__(self, stream, length):
		self.stream = stream
		self.length = length
		self.firmwareVolumes = []

		self._parse()

	def _parse(self):
		logger.debug("Parsing EfiFirmwareImage with length %u", self.length)

		base = self.stream.tell()
		while base < self.length:
			#Align to 8 bytes
			if self.stream.tell() % 8:
				tmp = 8 - (self.stream.tell() % 8)
				self.stream.seek(tmp, os.SEEK_CUR)
				base += tmp

			#search for firmware volume GUID
			guidBytes = self.stream.read(16)
			while base < self.length and uuid.UUID(bytes_le=guidBytes) != EFIGUIDS.FIRMWARE_VOLUME1 and uuid.UUID(bytes_le=guidBytes) != EFIGUIDS.FIRMWARE_VOLUME2:
				guidBytes = self.stream.read(16)
				if len(guidBytes) < 16:
					return
				base += 16

			#seems a firmware volume was found
			#rewind the stream back to the beginning
			base -=16
			self.stream.seek(-32, os.SEEK_CUR)
			logger.debug("Found firmware volume at 0x%X", self.stream.tell())

			(zero, guid, length, sig, attrib, headerlength, checksum, reserved, revision) = struct.unpack("<16s16sQ4sIHH3sB", self.stream.read(16 + 16 + 8 + 4 + 4 + 2 + 2 + 3 + 1))
			guid = uuid.UUID(bytes_le=guid)
			self.firmwareVolumes.append(EfiFirmwareVolume(base, headerlength, length - headerlength, sig, attrib, self.stream))

			#skip blockmap
			while True:
				(numBlocks, blockLength) = struct.unpack("<II", self.stream.read(8))
				if numBlocks == 0 and blockLength == 0:
 					break;

			self.stream.seek(length - headerlength, os.SEEK_CUR)
			base += length

class EfiFirmwareVolume(EfiElement):
	def __init__(self, base, headerLength, dataLength, signature, attributes, stream):
		self.Base = base
		self.HeaderLength = headerLength
		self.DataLength = dataLength
		self.Signature = signature
		self.Attributes = attributes
		self.stream = stream
		self.files = []
		self._parse()

	def _parse(self):
		streamPos = self.stream.tell()

		self.stream.seek(self.Base + self.HeaderLength, os.SEEK_SET)
		base = 0
		while base < self.DataLength:
			#Align to 8 byte
			if self.stream.tell() % 8:
				tmp = 8 - (self.stream.tell() % 8)
				self.stream.seek(tmp, os.SEEK_CUR)
				base += tmp

			if base >= self.DataLength:
				break

			logger.debug("Parsing firmware file at 0x%X", self.stream.tell())
			(guid, checksum, type, attrib, length, state) = struct.unpack("<16sHBB3sB", self.stream.read(16 + 2 + 1 + 1 + 3 + 1))
			guid = uuid.UUID(bytes_le=guid)
			length = struct.unpack("<I", length + '\0')[0]
			self.stream.seek(self.Base + self.HeaderLength + base + 24)
			filedata = self.stream.read(length - 24)
			if type != 0xFF:
				self.files.append(EfiFile(base, length - 24, guid, type, attrib, state, filedata))

			base += length

		self.stream.seek(streamPos, os.SEEK_SET)

	def __str__(self):
		result = "EFI_FIRMWARE_VOLUME:\n"
		result += "\tBase Offset: 0x%08x\n" % self.Base
		result += "\tHeader Length: 0x%x\n" % self.HeaderLength
		result += "\tData Length: 0x%08x\n" % self.DataLength
		result += "\tTotal Length: 0x%08x\n" % (self.HeaderLength + self.DataLength)
		result += "\tSignature: %s\n" % self.Signature
		result += "\tAttributes: 0x%04x\n" % self.Attributes
		return result

class EfiFile(EfiElement):
	class EFI_FILETYPES:
		EFI_FV_FILETYPE_RAW						= 0x01
		EFI_FV_FILETYPE_FREEFORM				= 0x02
		EFI_FV_FILETYPE_SECURITY_CORE			= 0x03
		EFI_FV_FILETYPE_PEI_CORE				= 0x04
		EFI_FV_FILETYPE_PXE_CORE				= 0x05
		EFI_FV_FILETYPE_PEIM					= 0x06
		EFI_FV_FILETYPE_DRIVER					= 0x07
		EFI_FV_FILETYPE_COMBINED_PEIM_DRIVER	= 0x08
		EFI_FV_FILETYPE_APPLICATION				= 0x09
		EFI_FV_FILETYPE_FIRMWARE_VOLUME_IMAGE	= 0x0b
		EFI_FV_FILETYPE_FFS_PAD					= 0xf0

	def __init__(self, base, length, guid, type, attributes, state, filedata):
		self.Base = base
		self.Length = length
		self.Guid = guid
		self.Type = type
		self.Attributes = attributes
		self.State = state
		self.Data = filedata
		self.subsections = []
		self._parse()

	def _parse(self):
		if (self.Type == EfiFile.EFI_FILETYPES.EFI_FV_FILETYPE_FREEFORM or
		self.Type == EfiFile.EFI_FILETYPES.EFI_FV_FILETYPE_PEI_CORE or
		self.Type == EfiFile.EFI_FILETYPES.EFI_FV_FILETYPE_PXE_CORE or
		self.Type == EfiFile.EFI_FILETYPES.EFI_FV_FILETYPE_PEIM or
		self.Type == EfiFile.EFI_FILETYPES.EFI_FV_FILETYPE_DRIVER or
		self.Type == EfiFile.EFI_FILETYPES.EFI_FV_FILETYPE_COMBINED_PEIM_DRIVER or
		self.Type == EfiFile.EFI_FILETYPES.EFI_FV_FILETYPE_APPLICATION or
		self.Type == EfiFile.EFI_FILETYPES.EFI_FV_FILETYPE_SECURITY_CORE or
		self.Type == EfiFile.EFI_FILETYPES.EFI_FV_FILETYPE_FIRMWARE_VOLUME_IMAGE):
			base = 0
			while base < len(self.Data):
				if base % 4:
					base += 4 - (base % 4)

				if base >= len(self.Data):
					break

				logger.debug("Parsing firmware file section at file-relative-offset 0x%X", base)
				(length, efitype) = struct.unpack("<3sB", self.Data[base:base+4])
				length = struct.unpack("<I", length + '\0')[0]

				sectionData = self.Data[base:base+length]
				self.subsections.append(InstantiateSectionFromType(efitype, sectionData))

				base += length

	def _strfiletype(self):
		if self.Type == self.EFI_FILETYPES.EFI_FV_FILETYPE_RAW:
			return "RAW"
		elif self.Type == self.EFI_FILETYPES.EFI_FV_FILETYPE_FREEFORM:
			return "FREEFORM"
		elif self.Type == self.EFI_FILETYPES.EFI_FV_FILETYPE_SECURITY_CORE:
			return "SECURITY_CORE"
		elif self.Type == self.EFI_FILETYPES.EFI_FV_FILETYPE_PEI_CORE:
			return "PEI_CORE"
		elif self.Type == self.EFI_FILETYPES.EFI_FV_FILETYPE_PXE_CORE:
			return "PXE_CORE"
		elif self.Type == self.EFI_FILETYPES.EFI_FV_FILETYPE_PEIM:
			return "PEIM"
		elif self.Type == self.EFI_FILETYPES.EFI_FV_FILETYPE_DRIVER:
			return "DRIVER"
		elif self.Type == self.EFI_FILETYPES.EFI_FV_FILETYPE_COMBINED_PEIM_DRIVER:
			return "COMBINED_PEIM_DRIVER"
		elif self.Type == self.EFI_FILETYPES.EFI_FV_FILETYPE_APPLICATION:
			return "APPLICATION"
		elif self.Type == self.EFI_FILETYPES.EFI_FV_FILETYPE_FIRMWARE_VOLUME_IMAGE:
			return "FIRMWARE_VOLUME_IMAGE"
		elif self.Type == self.EFI_FILETYPES.EFI_FV_FILETYPE_FFS_PAD:
			return "PAD"
		return "UNKNOWN"

	def __str__(self):
		result = "EFI_FIRMWARE_FILE:\n"
		result += "\tBase Offset: 0x%08x\n" % self.Base
		result += "\tLength: 0x%08x\n" % self.Length
		result += "\tGUID: 0x%s\n" % self.Guid
		result += "\tType: %s (0x%02x)\n" % (self._strfiletype(), self.Type)
		result += "\tAttributes: 0x%02x\n" % self.Attributes
		result += "\tState: 0x%x\n" % self.State
		return result

def InstantiateSectionFromType(type, data):
	if type == EfiSection.EFI_SECTIONTYPES.EFI_SECTION_COMPRESSION:
		return EfiCompressedSection(type, data)
	if type == EfiSection.EFI_SECTIONTYPES.EFI_SECTION_GUID_DEFINED:
		return EfiGuidDefinedSection(type, data)
	elif type == EfiSection.EFI_SECTIONTYPES.EFI_SECTION_VERSION:
		return EfiVersionSection(type, data)
	elif type == EfiSection.EFI_SECTIONTYPES.EFI_SECTION_USER_INTERFACE:
		return EfiUserInterfaceSection(type, data)
	elif type == EfiSection.EFI_SECTIONTYPES.EFI_SECTION_FREEFORM_SUBTYPE_GUID:
		return EfiFreeformSubtypeGuidSection(type, data)
	elif type == EfiSection.EFI_SECTIONTYPES.EFI_SECTION_FIRMWARE_VOLUME_IMAGE:
		return EfiFirmwareVolumeSection(type, data)
	else:
		return EfiGenericSection(type, data)

class EfiSection(EfiElement):
	class EFI_SECTIONTYPES:
		EFI_SECTION_COMPRESSION					= 0x01
		EFI_SECTION_GUID_DEFINED				= 0x02
		EFI_SECTION_PE32						= 0x10
		EFI_SECTION_PIC							= 0x11
		EFI_SECTION_TE							= 0x12
		EFI_SECTION_DXE_DEPEX					= 0x13
		EFI_SECTION_VERSION						= 0x14
		EFI_SECTION_USER_INTERFACE				= 0x15
		EFI_SECTION_COMPATABILITY16				= 0x16
		EFI_SECTION_FIRMWARE_VOLUME_IMAGE		= 0x17
		EFI_SECTION_FREEFORM_SUBTYPE_GUID		= 0x18
		EFI_SECTION_RAW							= 0x19
		EFI_SECTION_PEI_DEPEX					= 0x1b

	def __init__(self, sectionType, data):
		self.SectionType = sectionType
		self.Data = data
		self.RawContent = data[4:]
		self.Subsections = []

	def _parseSubsections(self, data):
		base = 0
		while base < len(data):
			if base % 4:
				base += 4 - (base % 4)

			if base >= len(data):
				break

			logger.debug("Parsing subsection section at section-relative-offset 0x%X", base)
			(length, efitype) = struct.unpack("<3sB", data[base:base+4])
			length = struct.unpack("<I", length + '\0')[0]

			sectionData = data[base:base+length]
			self.Subsections.append(InstantiateSectionFromType(efitype, sectionData))

			base += length

	def _strsectiontype(self):
		if self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_COMPRESSION:
			return "COMPRESSION"
		elif self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_GUID_DEFINED:
			return "GUID_DEFINED"
		elif self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_PE32:
			return "PE32"
		elif self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_PIC:
			return "PIC"
		elif self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_TE:
			return "TE"
		elif self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_DXE_DEPEX:
			return "DEPEX"
		elif self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_VERSION:
			return "VERSION"
		elif self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_USER_INTERFACE:
			return "USER_INTERFACE"
		elif self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_COMPATABILITY16:
			return "COMPATABILITY16"
		elif self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_FIRMWARE_VOLUME_IMAGE:
			return "FIRMWARE_VOLUME_IMAGE"
		elif self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_FREEFORM_SUBTYPE_GUID:
			return "FREEFORM_SUBTYPE_GUID"
		elif self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_RAW:
			return "RAW"
		elif self.SectionType == self.EFI_SECTIONTYPES.EFI_SECTION_PEI_DEPEX:
			return "PEI_DEPEX"
		return "UNKNOWN"

	def __str__(self):
		result = "EFI_FIRMWARE_SECTION:\n"
		result += "\tType: %s (0x%02x)\n" % (self._strsectiontype(), self.SectionType)
		result += "\tLength: 0x%08x\n" % len(self.Data)
		return result

class EfiGenericSection(EfiSection):
	def __init__(self, sectionType, data):
		super(EfiGenericSection, self).__init__(sectionType, data)
		#self._parseSubsections(self.RawContent)

class EfiCompressedSection(EfiSection):
	def __init__(self, sectionType, data):
		super(EfiCompressedSection, self).__init__(sectionType, data)
		(self.UncompressedDataLength, self.CompressionType) = struct.unpack("<IB", self.Data[4:4+4+1])
		uncomp_data = self.Data[4+4+1:]
		
		if self.CompressionType == 0:
			self.UncompressedData = uncomp_data
		elif self.CompressionType == 1:
			self.UncompressedData = EfiDecompressor.Decompress(uncomp_data)
		else:
			logger.warning("Found unsupported CompressionType %u", self.CompressionType)
			self.UncompressedData = ""

		self._parseSubsections(self.UncompressedData)

	def __str__(self):
		result = super(EfiCompressedSection, self).__str__()
		result += "\tCompressionType: %u\n" % self.CompressionType
		result += "\tUncompressedDataLength: %08x\n" % self.UncompressedDataLength
		return result

class EfiFirmwareVolumeSection(EfiSection):
	def __init__(self, sectionType, data):
		super(EfiFirmwareVolumeSection, self).__init__(sectionType, data)
		stringStream = StringIO.StringIO(self.RawContent)
		stringStream.seek(0, os.SEEK_END)
		streamLen = stringStream.tell()
		stringStream.seek(0, os.SEEK_SET)
		self.SubFirmware = EfiFirmwareImage(stringStream, streamLen)

class EfiVersionSection(EfiSection):
	def __init__(self, sectionType, data):
		super(EfiVersionSection, self).__init__(sectionType, data)
		(self.BuildNumber,) = struct.unpack("<H", self.Data[4:6])

	def __str__(self):
		result = super(EfiVersionSection, self).__str__()
		result += "\tBuild Number: %i\n" % self.BuildNumber
		return result

class EfiUserInterfaceSection(EfiSection):
	def __init__(self, sectionType, data):
		super(EfiUserInterfaceSection, self).__init__(sectionType, data)
		self.String = unicode(self.Data[4:len(data)-4], "utf-16")

	def __str__(self):
		result = super(EfiUserInterfaceSection, self).__str__()
		result += "\tString: %s\n" % self.String
		return result

class EfiFreeformSubtypeGuidSection(EfiSection):
	def __init__(self, sectionType, data):
		super(EfiFreeformSubtypeGuidSection, self).__init__(sectionType, data)
		(self.Guid,) = struct.unpack("<16s", self.Data[4:4+16])
		self.Guid = uuid.UUID(bytes_le=self.Guid)
		self.ContentData = data[4+16:]
		self.DataLength = len(self.ContentData)

	def __str__(self):
		result = super(EfiFreeformSubtypeGuidSection, self).__str__()
		result += "\tGUID: %s\n" % self.Guid
		result += "\tDataLength: 0x%08x\n" % self.DataLength
		return result

class EfiGuidDefinedSection(EfiSection):
	def __init__(self, sectionType, data):
		super(EfiGuidDefinedSection, self).__init__(sectionType, data)
		(self.Guid, self.DataOffset, self.Attributes) = struct.unpack("<16sHH", self.Data[4:4+16+2+2])
		self.Guid = uuid.UUID(bytes_le=self.Guid)
		self.ContentData = data[24:]
		self.DataLength = len(self.ContentData)

		if self.Guid == EFIGUIDS.FIRMWARE_FILE_SECTION_GUID_DEFINED_LZMA_COMPRESSED:
			logger.debug("Decompressing EFI GUID defined section containing LZMA")
			#FIXME: use pylzma...
			tmpfileIn = open("extractIn", "w+b")
			tmpfileIn.write(self.ContentData)
			tmpfileIn.close()

			#tmpfileOut = open("extractOut", "w+b")
			#tmpfileOut.close()

			#os.system("/Users/andy/Desktop/efi/edk/svntrunk/edk2/BaseTools/BinWrappers/Darwin-x86_64/LzmaCompress -d extractIn -o extractOut")
			fnull = open(os.devnull, 'w')
			subprocess.check_call(["/Users/andy/Desktop/efi/edk/svntrunk/edk2/BaseTools/BinWrappers/Darwin-x86_64/LzmaCompress", "-d", "extractIn", "-o", "extractOut"], stdout = fnull, stderr = fnull)
			fnull.close()

			tmpfileOut = open("extractOut", "rb")
			self.UncompressedData = tmpfileOut.read()
			tmpfileOut.close()

			os.unlink("extractIn")
			os.unlink("extractOut")

			self._parseSubsections(self.UncompressedData)

	def __str__(self):
		result = super(EfiGuidDefinedSection, self).__str__()
		result += "\tGUID: %s\n" % self.Guid
		result += "\tDataLength: 0x%08x\n" % self.DataLength
		result += "\tDataOffset: 0x%04x\n" % self.DataOffset
		result += "\tAttributes: 0x%04x\n" % self.Attributes
		return result
