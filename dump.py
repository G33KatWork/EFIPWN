#!/usr/bin/env python

import sys
import os
import logging
import argparse

from EFI import EfiFirmwareImage
from TreePrinter import EfiTreePrintVisitor
from EfiTreeFileDumpVisitor import EfiTreeFileDumpVisitor
from FDFGenerator import FDFGenerator

def main(argv):
	parser = argparse.ArgumentParser(description='EFI Firmware exploration tool')
	parser.add_argument('-d', '--debug', action='store_true', dest='debug', help='Display debug information (DEBUG)')
	parser.add_argument('file', nargs=1, type=argparse.FileType('rb'), help='The firmware file')

	subparsers = parser.add_subparsers(title='Operations', dest='action')

	parser_print = subparsers.add_parser('print', help='Print a tree of the structure of the EFI firmware image')

	parser_dump = subparsers.add_parser('dump', help='Dump all files in an EFI firmware image into a directory structure')
	parser_dump.add_argument('destination', nargs=1, type=str, help='The location of the dump')

	parser_genfdf = subparsers.add_parser('genfdf', help='Try to create a EDK2 FDF file for generating a firmware image out of a dump')
	parser_genfdf.add_argument('dirPrefix', nargs=1, type=str, help='The location of the dump files')

	arguments = parser.parse_args(argv[1:])

	if arguments.debug:
		logging.basicConfig(level=logging.DEBUG)
	else:
		logging.basicConfig(level=logging.INFO)

	arguments.file[0].seek(0, os.SEEK_END)
	flen = arguments.file[0].tell()
	arguments.file[0].seek(0, os.SEEK_SET)

	fw = EfiFirmwareImage(arguments.file[0], flen)

	if arguments.action == 'print':
		v = EfiTreePrintVisitor()
		v.visit(fw)

	if arguments.action == 'dump':
		d = EfiTreeFileDumpVisitor(arguments.destination[0])
		d.visit(fw)

	if arguments.action == 'genfdf':
		f = FDFGenerator(arguments.dirPrefix[0])
		print f.visit(fw)

if __name__ == '__main__':
	main(sys.argv)
