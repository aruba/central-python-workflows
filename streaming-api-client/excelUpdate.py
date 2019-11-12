import json
import re
import time
import os
import csv


class exportToFile:

    def __init__(self, topic, fileName, filePath=None,
                 fileType="csv", rowLimit="65000"):
        self.fullName = ""
        self.topic = topic
        self.dataSheets = {}
        self.fileName = fileName
        self.filePath = filePath
        self.fileType = fileType
        self.rowLimit = int(rowLimit)

    @staticmethod
    def camel_to_underscore(name):
        camel_pat = re.compile(r'([A-Z])')
        return camel_pat.sub(lambda x: '_' + x.group(1).lower(), name)

    @staticmethod
    def underscore_to_camel(name):
        under_pat = re.compile(r'_([a-z])')
        return under_pat.sub(lambda x: x.group(1).upper(), name)

    def createFileDir(self, dateTime=False):
        fileName = ""
        if not self.fileType or self.fileType is None:
            self.fileType = "csv"
        if not dateTime:
            fileName = "_".join([self.fileName, self.topic]) \
                       + "." + self.fileType
        else:
            dateTime = time.strftime("%Y%m%d-%H%M%S")
            print([self.fileName, self.topic, dateTime])
            fileName = "_".join([self.fileName, self.topic, dateTime]) \
                       + "." + self.fileType

        if self.filePath is None:
            self.filePath = os.path.join(os.getcwd(), "logs")

        self.fullName = os.path.join(self.filePath, fileName)
        # Creating Directory
        if not os.path.exists(os.path.dirname(self.fullName)):
            try:
                os.makedirs(os.path.dirname(self.fullName))
            except OSError as exc:  # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise

    def countLines(self, fileName=""):
        if not fileName or fileName == "":
            fileName = self.fullName

        if self.fileType == "csv":
            linesCount = 0
            try:
                with open(fileName) as f:
                    linesCount = sum(1 for line in f)
            except Exception as err:
                print("Error in counting lines: %s" % linesCount)
            return linesCount

    def readFromFile(self, fileName=""):
        if not fileName or fileName == "":
            fileName = self.fullName

        try:
            if self.fileType == "xls":
                pass
            elif self.fileType == "csv":
                with open(fileName, mode="r") as f:
                    csv_dict_reader = csv.DictReader(f)
                    dataList = list(csv_dict_reader)
                    fieldNames = csv_dict_reader.fieldnames
                return fieldNames, dataList
        except Exception as err:
            print(err)
