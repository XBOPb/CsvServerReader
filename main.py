from http.server import BaseHTTPRequestHandler, HTTPServer
from PyQt6.QtWidgets import (QMainWindow, QApplication, QPushButton, QCheckBox, 
                             QFileDialog, QLabel, QTableWidget, 
                             QTableWidgetItem, QWidget, QVBoxLayout, QHBoxLayout)
from PyQt6.QtCore import QThread, QObject
from PyQt6 import QtCore
from PyQt6.QtGui import QFont
from PyQt6.QtSql import QSqlDatabase, QSqlQuery
from interface import Ui_MainWindow
import sqlite3
import os
import subprocess
import sys
import csv

class CSVReader(QMainWindow):
    def __init__(self):
        super(CSVReader, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.temp = os.environ['TEMP']
        self.ui.start_server_button.clicked.connect(self.start_server)
        self.ui.start_server_button.clicked.connect(self.report_started_server)
        self.ui.open_csv_button.clicked.connect(self.csv_choice_menu)

    def report_started_server(self): 
        self.ui.start_server_button.setText("Server started at 127.0.0.1:8000")
        self.ui.start_server_button.setEnabled(False)

    def csv_choice_menu(self):
        file_dialog = QFileDialog()
        filter = "*.csv"
        csv_path = QFileDialog.getOpenFileName(file_dialog, filter=filter)[0]
        if not csv_path:
            return
        
        if ' ' in csv_path:
            # command line does not like spaces
            warning = QLabel("PATH TO CSV MUST NOT CONTAIN SPACE SYMBOL.")
            warning.setStyleSheet("QLabel {color: red;}")
            warning.setFont(QFont('Times', 20))
            self.ui.verticalLayout.addWidget(warning)
            warning.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        with open(csv_path, 'r') as file:
            csv_lines = list(csv.reader(file, delimiter=","))
        filename = os.path.basename(csv_path)
        temp_file = os.path.join(self.temp, filename)
        global main_name
        # save globally for table creation
        main_name = filename.split('.')[0]
        
        with open(temp_file, 'w') as file:
            file.write(str(csv_lines))
        # send post request
        subprocess.check_output(f'curl -d @{temp_file} http://127.0.0.1:8000')
        self.close()
        # show db in GUI
        self.connect_sql_qt()

    def connect_sql_qt(self):
        con = QSqlDatabase.addDatabase("QSQLITE")
        con.setDatabaseName('db.sqlite3')
        if not con.open():
            print('Unable to connect')
        win = Database(self)
        win.show()

    def start_server(self):
        # start server in thread so GUI doesn't freeze
        self.thread = QThread()
        self.worker = StartServer()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.start_server)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()
    

class Database(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Table overview")
        self.resize(450, 250)
        # get all items query
        query = QSqlQuery(f"SELECT * FROM {main_name}")
        self.build_table(query)
        
    def build_table(self, query):
        # set up table
        self.central_widget = QWidget(self)
        self.vertical_layout = QVBoxLayout(self.central_widget)
        self.columns_layout = QHBoxLayout()
        self.view = QTableWidget()
        self.vertical_layout.addLayout(self.columns_layout)
        self.vertical_layout.addWidget(self.view)
        headers = self.get_headers()
        column_number = len(headers)
        self.view.setColumnCount(column_number)
        for header in headers:
            self.column_order = QPushButton(f'Sort')
            self.column_order.setFixedSize(30, 20)
            self.column_order.setObjectName(f'sort_{header}')
            self.columns_layout.addWidget(self.column_order)
            self.column_order.clicked.connect(self.sort_database)

            self.column_box = QCheckBox(header)
            self.column_box.setChecked(True)
            self.column_box.stateChanged.connect(self.filter_database)
            self.columns_layout.addWidget(self.column_box)

        self.view.setHorizontalHeaderLabels(headers)
        while query.next():
            rows = self.view.rowCount()
            self.view.setRowCount(rows + 1)
            for i in range(column_number):
                self.view.setItem(rows, i, QTableWidgetItem(str(query.value(i))))
        self.view.resizeColumnsToContents()
        self.setCentralWidget(self.central_widget)

    def get_headers(self):
        connection = sqlite3.connect('db.sqlite3')
        cursor = connection.execute(f'SELECT * FROM {main_name}')
        names = [description[0] for description in cursor.description]
        connection.close()
        return names
    
    def filter_database(self):
        # hide/show column depending on checkbox
        all_boxes = self.findChildren(QCheckBox)
        for i, box in enumerate(all_boxes):
            if box.checkState() == QtCore.Qt.CheckState.Unchecked:
                self.view.setColumnHidden(i, True)
            else:
                self.view.setColumnHidden(i, False)

    def sort_database(self):
        self.view.clear()
        sort_button = str(self.sender().objectName()).replace('sort_', '')
        query = QSqlQuery(f'SELECT * FROM {main_name} ORDER BY {sort_button}')
        self.build_table(query)

        
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # in case you want to check if server's up
        self.send_response(200)
        self.send_header('Content-type','text/html')
        self.end_headers()
        message = "HTTP Service for reading csv files."
        self.wfile.write(bytes(message, "utf8"))
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        message_string = post_data.decode()
        self.message_list = eval(message_string)
        self.column_names = []
        for item in self.message_list[0]:
            self.column_names.append(item)
        self.write_to_sqlite()
        self.send_response(200)
        self.send_header('Content-type','text/csv')
        self.end_headers()
    
    def write_to_sqlite(self):
        # write post data to sqlite database
        connection = self.connect_to_sqlite()
        clear_query = self.delete_table_query()
        self.execute_query(connection, clear_query)
        create_query = self.create_table_query()
        self.execute_query(connection, create_query)
        insert_query = self.insert_data_query()
        self.execute_query(connection, insert_query)
    
    def create_table_query(self):
        self.columns = ','.join(self.column_names)
        create_table = f"CREATE TABLE IF NOT EXISTS {main_name} ({self.columns});"
        return create_table
    
    def delete_table_query(self):
        drop_table = f"DROP TABLE IF EXISTS {main_name}"
        return drop_table
    
    def insert_data_query(self):
        new_list = self.message_list[1:]
        new_list.pop()
        mylist = str(new_list).replace('[', '(').replace(']', ')').replace('((', '(').replace('))', ')')
        insert_data = f"INSERT INTO {main_name} ({self.columns}) VALUES {mylist};"
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
        # inital connection to sqlite
        connection = None
        try:
            db_name = 'db.sqlite3'
            current_folder = os.path.dirname(__file__)
            path = os.path.join(current_folder, db_name)
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