import ast, os, logging
import EFI

logger = logging.getLogger(__name__)

class EfiTreeFileDumpVisitor(ast.NodeVisitor):
  def __init__(self, destinationDirectory):
    logger.debug("Dumping EFI Tree into %s: " % destinationDirectory)
    self.curDir = os.path.abspath(destinationDirectory)
    self.fvCount = 0
    self.uniquenessSuffix = 0

  def generic_visit(self, node):
    logger.error("Unrecognized node: %s " % (type(node).__name__))
    raise Exception("Unrecognized node: %s " % (type(node).__name__))

  def visit_EfiFirmwareImage(self, node):
    if not os.path.isdir(self.curDir):
      os.makedirs(self.curDir)

    for v in node.firmwareVolumes:
      self.visit(v)

  def visit_EfiFirmwareVolume(self, node):
    self.curDir = os.path.join(self.curDir, "firmwareVolume" + str(self.fvCount))
    logger.debug("Dumping Firmware Volume %i into directory %s: " % (self.fvCount, self.curDir))
    self.fvCount += 1
    os.makedirs(self.curDir)
    
    for f in node.files:
      self.visit(f)

    self.curDir = os.path.abspath(os.path.join(self.curDir, ".."))

  def visit_EfiFile(self, node):
    dirname = str(node.Guid)
    if dirname == 'ffffffff-ffff-ffff-ffff-ffffffffffff':
      dirname = dirname + "_" + str(self.uniquenessSuffix)
      self.uniquenessSuffix += 1

    self.curDir = os.path.join(self.curDir, dirname)
    logger.debug("Dumping Firmware File %s into directory %s: " % (str(node.Guid), self.curDir))
    os.makedirs(self.curDir)
    
    if node.Type == EFI.EfiFile.EFI_FILETYPES.EFI_FV_FILETYPE_RAW:
      f = open(os.path.join(self.curDir, "raw_filecontent"), "w+b")
      f.write(node.Data)
      f.close()

    if node.Type == EFI.EfiFile.EFI_FILETYPES.EFI_FV_FILETYPE_FFS_PAD:
      f = open(os.path.join(self.curDir, "pad_filecontent"), "w+b")
      f.write(node.Data)
      f.close()

    for s in node.subsections:
      self.visit(s)

    self.curDir = os.path.abspath(os.path.join(self.curDir, ".."))

  def visit_EfiGenericSection(self, node):
    logger.debug("Dumping version generic section content into directory %s: " % (self.curDir))
    f = open(os.path.join(self.curDir, node._strsectiontype()), "w+b")
    f.write(node.RawContent)
    f.close()

    for s in node.Subsections:
      self.visit(s)

  def visit_EfiVersionSection(self, node):
    logger.debug("Dumping version section content into directory %s: " % (self.curDir))
    f = open(os.path.join(self.curDir, "version.txt"), "w+b")
    f.write(node.VersionString)
    #f.write("\n")
    #f.write(str(node.BuildNumber))
    f.close()

  def visit_EfiGuidDefinedSection(self, node):
    if node.Guid == EFI.EFIGUIDS.FIRMWARE_FILE_SECTION_GUID_DEFINED_LZMA_COMPRESSED:
      self.curDir = os.path.join(self.curDir, "LZMA_uncompressed")
      os.makedirs(self.curDir)

      logger.debug("Dumping LZMA compressed GUID defined section content into directory %s: " % (self.curDir))
      for s in node.Subsections:
        self.visit(s)

      self.curDir = os.path.abspath(os.path.join(self.curDir, ".."))
    else:
      logger.debug("Dumping GUID defined section content into directory %s: " % (self.curDir))
      f = open(os.path.join(self.curDir, "GUID_DEFINED_" + str(node.Guid)), "w+b")
      f.write(str(node.ContentData))
      f.close()

  def visit_EfiUserInterfaceSection(self, node):
    logger.debug("Dumping UI section content into directory %s: " % (self.curDir))
    f = open(os.path.join(self.curDir, "uistring.txt"), "w+b")
    f.write(str(node.String))
    f.close()

  def visit_EfiFreeformSubtypeGuidSection(self, node):
    logger.debug("Dumping freeform guid defined section content into directory %s: " % (self.curDir))
    f = open(os.path.join(self.curDir, "freeform_guid_defined_" + str(node.Guid)), "w+b")
    f.write(str(node.ContentData))
    f.close()

  def visit_EfiCompressedSection(self, node):
    self.curDir = os.path.join(self.curDir, "compressedSectionContents")
    logger.debug("Dumping compressed sections in EFI Compressed Section into %s: " % (self.curDir))
    os.makedirs(self.curDir)
    
    for s in node.Subsections:
        self.visit(s)

    self.curDir = os.path.abspath(os.path.join(self.curDir, ".."))

  def visit_EfiFirmwareVolumeSection(self, node):
    self.curDir = os.path.join(self.curDir, "firmwareVolumeSectionContents")
    logger.debug("Dumping Firmware Volume in Firmware Volume Section into directory %s: " % (self.curDir))
    os.makedirs(self.curDir)
    
    self.visit(node.SubFirmware)

    self.curDir = os.path.abspath(os.path.join(self.curDir, ".."))

