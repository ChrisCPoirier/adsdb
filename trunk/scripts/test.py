#######################################################################
# Copyright 1994-2011 iAnywhere Solutions, Inc.  All rights reserved.
# This sample code is provided AS IS, without warranty or liability
# of any kind.
# 
# You may use, reproduce, modify and distribute this sample code
# without limitation, on the condition that you retain the foregoing
# copyright notice and disclaimer as to the original iAnywhere code.
# 
#######################################################################

import adsdb

# Adjust the connection path (C:\) and server type as necessary
conn = adsdb.connect(DataSource='c:\\', ServerType='local or remote')
cur = conn.cursor()

cur.execute("select 'Hello World' from system.iota")
assert cur.fetchone()[0] > 0

conn.close()
print 'adsdb successfully installed.'

