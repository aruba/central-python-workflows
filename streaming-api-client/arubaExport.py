import re
import json
import csv
from excelUpdate import exportToFile
# from proto import presence_pb2
import threading

threadLock = threading.Lock()


class presenceExport(exportToFile):

    def __init__(self, topic, fileName, filePath=None,
                 fileType="csv", rowLimit="65000"):
        exportToFile.__init__(self, topic, fileName,
                              filePath, fileType, rowLimit)
        self.createFileDir(dateTime=True)
        # self.dataHeaders = {}

    @staticmethod
    def extractProximityData(decode_data):
        from proto import presence_pb2
        # Extract fields from proto file
        main_headers = ["timestamp", "customer_id", "event"]
        p_headers = presence_pb2.proximity.DESCRIPTOR.fields_by_name.keys()
        headers = main_headers + p_headers
        data_dict = {}
        data_list = []
        for ele in headers:
            data_dict.update({ele: ""})

        # Data
        timestamp = decode_data.timestamp
        customerId = decode_data.customer_id
        event = decode_data.event

        proximity_list = decode_data.pa_proximity_event.proximity
        for ele in proximity_list:
            try:
                data_dict = {}
                data_dict["timestamp"] = timestamp
                data_dict["customer_id"] = customerId
                data_dict["event"] = event
                for key in p_headers:
                    if hasattr(ele, key):
                        data = getattr(ele, key)
                        # If it is mac address, it will be a dictionary
                        mac_type = presence_pb2.mac_address
                        if isinstance(data, mac_type):
                            data = data.addr
                            data = data.decode("utf8")
                        data_dict[key] = data
                    else:
                        data_dict[key] = "NULL"
            except Exception as err:
                print(err)
            data_list.append(data_dict)
        return data_list

    def createProximityCol(self):
        from proto import presence_pb2
        # self.createFileDir(dateTime=True)
        if self.topic == "presence":
            main_headers = ['timestamp', 'customer_id', 'event']
            proximity_msg = presence_pb2.proximity
            proximity_headers = proximity_msg.DESCRIPTOR.fields_by_name.keys()
            proximity_headers = main_headers + proximity_headers
            # proximity_headers = list(map(exportToFile.underscore_to_camel,
            #                              main_headers + proximity_headers))
            try:
                with open(self.fullName, "w") as f:
                    field_writer = csv.writer(f, delimiter=',', quotechar='"',
                                              quoting=csv.QUOTE_MINIMAL)
                    field_writer.writerow(proximity_headers)
                return True
            except Exception as err:
                raise

    def writeData(self, data, fileName=""):
        # if number of rows are greater than rowLimit create a new file
        if self.topic == "presence":
            if not fileName or fileName == "":
                fileName = self.fullName
            fieldNames, readData = self.readFromFile(fileName)
            try:
                with open(fileName, mode="a") as f:
                    csv_writer = csv.DictWriter(f, fieldnames=fieldNames)
                    if data:
                        csv_writer.writerows(data)
            except Exception as err:
                raise


class writeThread (threading.Thread):

    def __init__(self, dataClass, data):
        threading.Thread.__init__(self)
        self.dataClass = dataClass
        self.data = data

    def run(self):
        # Get lock to synchronize threads
        threadLock.acquire()
        self.dataClass.writeData(self.data)
        # Free lock to release next thread
        threadLock.release()
