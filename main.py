from http.server import BaseHTTPRequestHandler, HTTPServer
from PyQt6.QtWidgets import QMainWindow, QApplication, QFileDialog, QLabel, QCheckBox
from PyQt6.QtCore import QThread, QObject
from PyQt6 import QtCore
from PyQt6.QtGui import QFont
from interface import Ui_MainWindow
import sqlite3
import os
import subprocess
import sys
import csv
import pandas as pd

clms = []
class CSVReader(QMainWindow):
    def __init__(self):
        super(CSVReader, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.temp = os.environ['TEMP']
        self.ui.start_server_button.clicked.connect(self.start_server)
        self.ui.start_server_button.clicked.connect(self.report_started_server)
        self.ui.open_csv_button.clicked.connect(self.csv_choice_menu)
        self.ui.checkBox.stateChanged.connect(self.write_column_names)

    def report_started_server(self): 
        self.ui.start_server_button.setText("Server started!")
        self.ui.start_server_button.setEnabled(False)

    def write_column_names(self):
        self.ui.data_field.setText(self.columns)
 
    def give_columns_info(self, columns):
        self.columns = columns
        print(self.columns)
        self.ui.checkBox.setChecked(True)
        # self.ui.data_field.setText(1234)

    def csv_choice_menu(self):
        file_dialog = QFileDialog()
        filter = "*.csv"
        csv_path = QFileDialog.getOpenFileName(file_dialog, filter=filter)[0]
        if not csv_path:
            return
        
        if ' ' in csv_path:
            warning = QLabel("PATH TO CSV MUST NOT CONTAIN SPACE SYMBOL.")
            warning.setStyleSheet("QLabel {color: red;}")
            warning.setFont(QFont('Times', 20))
            self.ui.verticalLayout.addWidget(warning)
            warning.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        with open(csv_path, 'r') as file:
            csv_lines = list(csv.reader(file, delimiter=","))
        filename = os.path.basename(csv_path)
        temp_file = os.path.join(self.temp, filename)
        
        with open(temp_file, 'w') as file:
            file.write(str(csv_lines))
        subprocess.run(f'curl -d @{temp_file} http://127.0.0.1:8000')

    def start_server(self):
        self.thread = QThread()
        self.worker = StartServer()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.start_server)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()
        

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/html')
        self.end_headers()
        message = "HTTP Server for reading csv files."
        self.wfile.write(bytes(message, "utf8"))
    
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type','text/csv')
        self.end_headers()
        content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
        post_data = self.rfile.read(content_length) # <--- Gets the data itself
        message_string = post_data.decode()
        self.message_list = eval(message_string)
        self.column_names = []
        for item in self.message_list[0]:
            self.column_names.append(item)
        self.data = pd.DataFrame(self.message_list, columns = self.column_names)
        self.write_to_sqlite()
    
    def write_to_sqlite(self):
        connection = self.connect_to_sqlite()
        create_query = self.create_table_query()
        self.execute_query(connection, create_query)
        insert_query = self.insert_data_query()
        self.execute_query(connection, insert_query)
    
    def create_table_query(self):
        self.columns = ','.join(self.column_names)
        create_table = f"CREATE TABLE file ({self.columns});"
        return create_table
    
    def insert_data_query(self):
        new_list = self.message_list[1:]
        # workaround
        mylist = str(new_list).replace('[', '(').replace(']', ')').replace('((', '(').replace('))', ')').replace(', ()', '')
        insert_data = f"INSERT INTO file ({self.columns}) VALUES {mylist};"
        return insert_data

    def execute_query(self, connection, query):
        cursor = connection.cursor()
        try:
            cursor.execute(query)
            connection.commit()
            print("Query executed successfully")
        except sqlite3.Error as e:
            print(f"The error '{e}' occurred")

    def connect_to_sqlite(self):
        connection = None
        try:
            db_name = 'db.sqlite3'
            current_folder = os.path.dirname(__file__)
            path = os.path.join(current_folder, db_name)
            print(path)
            connection = sqlite3.connect(path)
            print("Connection to SQLite DB successful")
        except sqlite3.Error as e:
            print(f"The error '{e}' occurred")
        return connection

class StartServer(QObject):
    def start_server(self):
        with HTTPServer(('', 8000), handler) as server:
            server.serve_forever()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = CSVReader()
    ui.show()
    app.exec()