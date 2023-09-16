# CsvServerReader
HTTP service with interface for reading csv files

# Installing&Launching
Install the app by cloning the repository with git clone command. Open the command line in 
project folder. Run the app with `python main.py`. Start a local server by clicking the corresponding button.
You can now choose a .csv file to make a post request with.

# Databases
The app uses Sqlite3 and QSql as a method for working with databases.
After you make a post request with curl, it will create `db.sqlite3` in the project folder
with sent data in it. There are some .csv files in the project repository, that was used 
for testing the app. You can find more .csv examples at https://people.sc.fsu.edu/~jburkardt/data/csv/csv.html
For the demostrarion purposes, there is a "Sort" and "Hide/Show column" options, that are available
for usage.