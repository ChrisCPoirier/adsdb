#!/usr/bin/env python
#######################################################################
# Copyright 1994-2010 iAnywhere Solutions, Inc.  All rights reserved.
# This sample code is provided AS IS, without warranty or liability
# of any kind.
# 
# You may use, reproduce, modify and distribute this sample code
# without limitation, on the condition that you retain the foregoing
# copyright notice and disclaimer as to the original iAnywhere code.
# 
#######################################################################
import sys
import adsdb
import dbapi20
import unittest
import os

class test_adsdb(dbapi20.DatabaseAPI20Test):

    # Delete the test.add from a previous run if it is leftover
    if os.access( 'c:\\test.add', os.F_OK ):
        os.remove( 'c:\\test.add' )
        os.remove( 'c:\\test.ai' )
        os.remove( 'c:\\test.am' )

    # Create a database for testing
    conn = adsdb.connect( DataSource='c:\\', ServerType='local or remote' )
    cur = conn.cursor()
    cur.execute( "CREATE DATABASE [test.add]" )
    conn.close()

    # These variables setup the python unit tests to use our driver (adsdb) and our connection string
    driver = adsdb
    connect_args = ()
    connect_kw_args = dict()
    connect_kw_args = dict(DataSource='C:\\test.add', ServerType='local or remote', UserID='ADSSYS' )

    def test_setoutputsize(self): pass
    def test_setoutputsize_basic(self): pass

if __name__ == '__main__':

    # Now run the tests
    unittest.main()
    print '''Done'''
