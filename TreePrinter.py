import ast
#import EFI

class EfiTreePrintVisitor(ast.NodeVisitor):
  def __init__(self):
    self.indentation = 0

  def generic_visit(self, node):
    print "Unrecognized node: ", type(node).__name__
    print node
    #ast.NodeVisitor.generic_visit(self, node)

  def visit_EfiFirmwareImage(self, node):
    for v in node.firmwareVolumes:
      self.visit(v)

  def visit_EfiFirmwareVolume(self, node):
    print indent(str(node), self.indentation)
    self.indentation += 10
    for f in node.files:
      self.visit(f)
    self.indentation -= 10

  def visit_EfiFile(self, node):
    print indent(str(node), self.indentation)
    self.indentation += 10
    for s in node.subsections:
      self.visit(s)
    self.indentation -= 10

  def visit_EfiGenericSection(self, node):
    print indent(str(node), self.indentation)
    self.indentation += 10
#    for n in node.subsubsections:
#      self.visit(n)
    self.indentation -= 10

  def visit_EfiVersionSection(self, node):
    print indent(str(node), self.indentation)
    self.indentation += 10
#    for n in node.subsubsections:
#      self.visit(n)
    self.indentation -= 10

  def visit_EfiGuidDefinedSection(self, node):
    print indent(str(node), self.indentation)
    self.indentation += 10
    for n in node.Subsections:
      self.visit(n)
    self.indentation -= 10

  def visit_EfiUserInterfaceSection(self, node):
    print indent(str(node), self.indentation)
    self.indentation += 10
#    for n in node.subsubsections:
#      self.visit(n)
    self.indentation -= 10

  def visit_EfiFreeformSubtypeGuidSection(self, node):
    print indent(str(node), self.indentation)
    self.indentation += 10
    for n in node.Subsections:
      self.visit(n)
    self.indentation -= 10

  def visit_EfiCompressedSection(self, node):
    print indent(str(node), self.indentation)
    self.indentation += 10
    for n in node.Subsections:
      self.visit(n)
    self.indentation -= 10

  def visit_EfiFirmwareVolumeSection(self, node):
    print indent(str(node), self.indentation)
    self.indentation += 10
    for s in node.SubFirmware.firmwareVolumes:
      self.visit(s)
    self.indentation -= 10
    

def indent(s, i):
  a = s.split("\n")
  res = ""
  for b in a:
    res += " "*i + b + "\n"
  return res
