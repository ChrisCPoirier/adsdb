This package provides a python interface to the Advantage database
server. This interface conforms to PEP 249.

Requirements
------------
Before installing the adsdb interface please make sure the
following components are installed on your system.

- Python 2.4 or greater
- Python ctypes module if missing
- Advantage Database Server 10.1 or newer (Advantage Local Server works too)

Installing the adsdb module
------------------------------
Run the following command as an administrative user to install
adsdb:

python setup.py install

Testing the adsdb module
---------------------------
To test that the Python interface to Advantage is working correctly
run the test.py script in the scripts subdirectory.  If the path "C:\"
is not valid on your system, change it to a valid path.  You should
see this expected output:

adsdb successfully installed.

