from mako.template import Template
import ast, logging, os
import EFI

logger = logging.getLogger(__name__)

TEMPLATEDIR = "templates"

class FDFGenerator(ast.NodeVisitor):
	def __init__(self, directoryPrefix):
		self.fvCount = 0
		self.directoryPrefix = directoryPrefix
		self.nestedFirmwareVolumes = []
		self.curDir = os.path.normpath(directoryPrefix)
		self.fdTemplate = open(TEMPLATEDIR + "/fd.tmpl").read()
		self.fvTemplate = open(TEMPLATEDIR + "/fv.tmpl").read()
		self.ffTemplate = open(TEMPLATEDIR + "/ff.tmpl").read()
		self.fsTemplate = open(TEMPLATEDIR + "/fs.tmpl").read()

	def generic_visit(self, node):
		logger.error("Unrecognized node: %s " % (type(node).__name__))
		raise Exception("Unrecognized node: %s " % (type(node).__name__))

	def visit_EfiFirmwareImage(self, node):
		firmwareVolumes = ""
		tmpl = Template(text=self.fdTemplate)
		
		for v in node.firmwareVolumes:
			firmwareVolumes += self.visit(v)

		nestedVolumes = ""
		for v in self.nestedFirmwareVolumes:
			nestedVolumes += v
		return tmpl.render(firmwareImage=node, firmwareVolumes=(firmwareVolumes + nestedVolumes))

	def visit_EfiFirmwareVolume(self, node):
		volume = ""
		files = ""
		thisFirmwareVolumeIndex = self.fvCount
		node.volumeIndex = thisFirmwareVolumeIndex
		self.fvCount += 1
		self.curDir = os.path.join(self.curDir, "firmwareVolume" + str(thisFirmwareVolumeIndex))
		
		tmpl = Template(text=self.fvTemplate)
		
		for f in node.files:
			files += self.visit(f)

		volume = tmpl.render(firmwareVolume=node, fvNum=thisFirmwareVolumeIndex, files=files)

		self.curDir = os.path.normpath(os.path.join(self.curDir, ".."))

		return volume

	def visit_EfiFile(self, node):
		self.curDir = os.path.join(self.curDir, str(node.Guid))

		sectionsForFile = ""
		for s in node.subsections:
			sectionsForFile += self.visit(s)

		tmpl = Template(text=self.ffTemplate)
		curFile = tmpl.render(firmwareFile=node, sections=sectionsForFile, curDir=self.curDir)

		self.curDir = os.path.normpath(os.path.join(self.curDir, ".."))
		return curFile

	def visit_EfiGuidDefinedSection(self, node):
		subsections = ""
		if node.Guid == EFI.EFIGUIDS.FIRMWARE_FILE_SECTION_GUID_DEFINED_LZMA_COMPRESSED:
			lzmaContents = ""
			self.curDir = os.path.join(self.curDir, "LZMA_uncompressed")

			for s in node.Subsections:
				subsections += self.visit(s)

			tmpl = Template(text=self.fsTemplate)
			lzmaContents = tmpl.render(section=node, curDir=self.curDir, subsections=subsections)

			self.curDir = os.path.normpath(os.path.join(self.curDir, ".."))
			return lzmaContents
		else:
			for s in node.Subsections:
				subsections += self.visit(s)

			tmpl = Template(text=self.fsTemplate)
			return tmpl.render(section=node, curDir=self.curDir, subsections=subsections)
		

	def visit_EfiGenericSection(self, node):
		tmpl = Template(text=self.fsTemplate)
		return tmpl.render(section=node, curDir=self.curDir)

	def visit_EfiUserInterfaceSection(self, node):
		tmpl = Template(text=self.fsTemplate)
		return tmpl.render(section=node, curDir=self.curDir)

	def visit_EfiVersionSection(self, node):
		tmpl = Template(text=self.fsTemplate)
		return tmpl.render(section=node, curDir=self.curDir)

	def visit_EfiCompressedSection(self, node):
		subsections = ""
		self.curDir = os.path.join(self.curDir, "compressedSectionContents")

		for s in node.Subsections:
			subsections += self.visit(s)

		tmpl = Template(text=self.fsTemplate)
		compressionType = "PI_NONE"
		if node.CompressionType == 1:
			compressionType = "PI_STD"
		self.curDir = os.path.normpath(os.path.join(self.curDir, ".."))
		return tmpl.render(section=node, curDir=self.curDir, subsections=subsections, compressionType=compressionType)

	def visit_EfiFreeformSubtypeGuidSection(self, node):
		tmpl = Template(text=self.fsTemplate)
		return tmpl.render(section=node, curDir=self.curDir)

	def visit_EfiFirmwareVolumeSection(self, node):
		self.curDir = os.path.join(self.curDir, "firmwareVolumeSectionContents")

		volume = node.SubFirmware.firmwareVolumes[0]
		self.nestedFirmwareVolumes.append(self.visit(volume))

		tmpl = Template(text=self.fsTemplate)
		section = tmpl.render(section=node, curDir=self.curDir, fvname="FV_" + str(volume.volumeIndex))

		self.curDir = os.path.normpath(os.path.join(self.curDir, ".."))

		return section
