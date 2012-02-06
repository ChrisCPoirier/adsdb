#    Copyright 2010-2011 iAnywhere Solutions, Inc.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
# http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# 
# See the License for the specific language governing permissions and
# limitations under the License.
# 
# While not a requirement of the license, if you do modify this file, we
# would appreciate hearing about it.   Please email advantage@sybase.com


"""adsdb - A DB API v2.0 compatible interface to Advantage Database Server.

This package provides a DB API v2.0 interface
    http://www.python.org/dev/peps/pep-0249
to the ADS dbcapi library.

"""

import os
import sys
import time
import datetime
import exceptions
import codecs
import platform
from ctypes import *
from struct import pack, unpack, calcsize
from decimal import *

API_VERSION = 1
API_VERSION_EX = 2

# NB: The following must match those in sacapi.h for the specified API_VERSION!

A_INVALID_TYPE  = 0
A_BINARY        = 1
A_STRING        = 2
A_DOUBLE        = 3
A_VAL64         = 4
A_UVAL64        = 5
A_VAL32         = 6
A_UVAL32        = 7
A_VAL16         = 8
A_UVAL16        = 9
A_VAL8          = 10
A_UVAL8         = 11
A_NCHAR         = 12
A_DECIMAL       = 13
A_DATE          = 14
A_TIME          = 15
A_TIMESTAMP     = 16

DT_NOTYPE       = 0
DT_DATE         = 384
DT_TIME         = 388
DT_TIMESTAMP    = 392
DT_VARCHAR      = 448
DT_FIXCHAR      = 452
DT_LONGVARCHAR  = 456
DT_STRING       = 460
DT_DOUBLE       = 480
DT_FLOAT        = 482
DT_DECIMAL      = 484
DT_INT          = 496
DT_SMALLINT     = 500
DT_BINARY       = 524
DT_LONGBINARY   = 528
DT_TINYINT      = 604
DT_BIGINT       = 608
DT_UNSINT       = 612
DT_UNSSMALLINT  = 616
DT_UNSBIGINT    = 620
DT_BIT          = 624
DT_NSTRING      = 628
DT_NFIXCHAR     = 632
DT_NVARCHAR     = 636
DT_LONGNVARCHAR = 640

DD_INVALID      = 0x0
DD_INPUT        = 0x1
DD_OUTPUT       = 0x2
DD_INPUT_OUTPUT = 0x3

class DataValue(Structure):
    """Must match a_ads_data_value."""

    _fields_ = [("buffer",      POINTER(c_char)),
                ("buffer_size", c_size_t),
                ("length",      POINTER(c_size_t)),
                ("type",        c_int),
                ("is_null",     POINTER(c_int))]


class BindParam(Structure):
    """Must match a_ads_bind_param."""

    _fields_ = [("direction",   c_int),
                ("value",       DataValue),
                ("name",        c_char_p)]


class ColumnInfo(Structure):
    """Must match a_ads_column_info."""

    _fields_ = [("name",        c_char_p),
                ("type",        c_int),
                ("native_type", c_int),
                ("precision",   c_short),
                ("scale",       c_short),
                ("max_size",    c_int),
                ("nullable",    c_int)]


class DataInfo(Structure):
    """Must match a_ads_data_info."""

    _fields_ = [("index",       c_int),
                ("type",        c_int),
                ("is_null",     c_int),
                ("data_size",   c_size_t)]

# NB: The preceding must match those in sacapi.h for the specified API_VERSION!


class DBAPISet(frozenset):

    """A special type of set for which A == x is true if A is a
    DBAPISet and x is a member of that set."""

    def __eq__(self, other):
        if isinstance(other, DBAPISet):
            return frozenset.__eq__(self, other)
        else:
            return other in self

    def __ne__(self, other):
        return not self == other


STRING    = DBAPISet([A_STRING,A_NCHAR])
BINARY    = DBAPISet([A_BINARY])
NUMBER    = DBAPISet([A_DOUBLE,
                      A_VAL64,
                      A_UVAL64,
                      A_VAL32,
                      A_UVAL32,
                      A_VAL16,
                      A_UVAL16,
                      A_VAL8,
                      A_UVAL8,
                      A_DECIMAL])
DATE      = DBAPISet([A_DATE])
TIME      = DBAPISet([A_TIME])
TIMESTAMP = DBAPISet([A_TIMESTAMP])
DATETIME  = TIMESTAMP
ROWID     = DBAPISet()

ToPyType = {DT_DATE         : DATE,
            DT_TIME         : TIME,
            DT_TIMESTAMP    : TIMESTAMP,
            DT_VARCHAR      : STRING,
            DT_FIXCHAR      : STRING,
            DT_LONGVARCHAR  : STRING,
            DT_STRING       : STRING,
            DT_DOUBLE       : NUMBER,
            DT_FLOAT        : NUMBER,
            DT_DECIMAL      : NUMBER,
            DT_INT          : NUMBER,
            DT_SMALLINT     : NUMBER,
            DT_BINARY       : BINARY,
            DT_LONGBINARY   : BINARY,
            DT_TINYINT      : NUMBER,
            DT_BIGINT       : NUMBER,
            DT_UNSINT       : NUMBER,
            DT_UNSSMALLINT  : NUMBER,
            DT_UNSBIGINT    : NUMBER,
            DT_BIT          : NUMBER,
            DT_LONGNVARCHAR : STRING,
            DT_NSTRING      : STRING,
            DT_NFIXCHAR     : STRING,
            DT_NVARCHAR     : STRING}


class Error(exceptions.StandardError):
    pass

class Warning(exceptions.StandardError):
    """Raise for important warnings like data truncation while inserting."""
    pass

class InterfaceError(Error):
    """Raise for interface, not database, related errors."""
    pass

class DatabaseError(Error):
    pass

class InternalError(DatabaseError):
    """Raise for internal errors: cursor not valid, etc."""
    pass

class OperationalError(DatabaseError):
    """Raise for database related errors, not under programmer's control:
    unexpected disconnect, memory allocation error, etc."""
    pass

class ProgrammingError(DatabaseError):
    """Raise for programming errors: table not found, incorrect syntax, etc."""
    pass

class IntegrityError(DatabaseError):
    """Raise for database constraint failures:  missing primary key, etc."""
    pass

class DataError(DatabaseError):
    pass

class NotSupportedError(DatabaseError):
    """Raise for methods or APIs not supported by database."""
    pass


format = 'xxxdqQiIhHbBxxxx'

def mk_valueof(raw, char_set):
    def valueof(data):
        if data.is_null.contents:
            return None
        elif data.type in raw:
            return data.buffer[:data.length.contents.value]
        elif data.type in (A_STRING,):
            return data.buffer[:data.length.contents.value].decode(char_set)
        elif data.type in (A_NCHAR,):
            if isinstance(data, unicode):
                return data.buffer[:data.length.contents.value]
            else:
                return unicode( data.buffer[:data.length.contents.value], char_set )
        elif data.type in (A_DECIMAL,):
            # Numeric fields come out as strings, convert them to decimal.Decimal objects
            return Decimal( data.buffer[:data.length.contents.value])
        elif data.type in (A_DATE,):
            # Date fields come out as string, convert them to datetime.date objects
            return ads_typecast_date( data.buffer[:data.length.contents.value] )
        elif data.type in (A_TIME,):
            # Time fields come out as string, convert them to datetime.time objects
            return ads_typecast_time( data.buffer[:data.length.contents.value] )
        elif data.type in (A_TIMESTAMP,):
            # Timestamp fields come out as string, convert them to datetime.time objects
            return ads_typecast_timestamp( data.buffer[:data.length.contents.value] )
        else:
            fmt = format[data.type]
            return unpack(fmt, data.buffer[:calcsize(fmt)])[0]
    return valueof


def mk_assign(char_set):
    def assign(param, value):
        is_null = value is None
        param.value.is_null = pointer(c_int(is_null))
        if is_null and param.direction == DD_INPUT:
            value = 0
        if param.value.type == A_INVALID_TYPE:
            if isinstance(value, int):
                param.value.type = A_VAL32
            elif isinstance(value, float):
                param.value.type = A_DOUBLE
            elif isinstance(value, Binary):
                param.value.type = A_BINARY
            else:
                param.value.type = A_STRING
        fmt = format[param.value.type]
        if fmt == 'x':
            if isinstance(value, str):
                size = length = len(value)
            elif isinstance(value, unicode):
                param.value.type = A_NCHAR
                value = value.encode('utf-16')
                size = length = len(value) + 2  # +2 for the BOM chars
            else:
                value = str(value)
                size = length = len(value)
            if param.direction != DD_INPUT:
                if size < param.value.buffer_size:
                    size = param.value.buffer_size
            buffer = create_string_buffer(value)
        else:
            buffer = create_string_buffer(pack(fmt, value))
            size = length = calcsize(fmt)
        param.value.buffer = cast(buffer, POINTER(c_char))
        param.value.buffer_size = c_size_t(size)
        param.value.length = pointer(c_size_t(length))
    return assign


threadsafety = 1
apilevel     = '2.0'
paramstyle   = 'qmark'

__all__ = [ 'threadsafety', 'apilevel', 'paramstyle', 'connect'] 

if platform.system() == 'Windows':
    bIsWindows = True
elif platform.system() == 'Linux':
    bIsWindows = False
else:
    raise InterfaceError( "Could not determine operating system type (Windows or Linux)." )

if calcsize("P") * 8 == 64:
    bIs64Bit = True
elif calcsize("P") * 8 == 32:
    bIs64Bit = False
else:
    raise InterfaceError( "Could not determine Python architecture type (64 or 32 bit)." )

if bIsWindows == False:
    strACELibrary = 'libace.so'
elif bIs64Bit == True:
    strACELibrary = 'ace64.dll'
else:
    strACELibrary = 'ace32.dll'

def load_library(*names):
    for name in names:
        try:
            if bIsWindows == True:
                return windll.LoadLibrary(name)
            else:
                return cdll.LoadLibrary(name)
        except OSError:
            continue
    raise InterfaceError("Could not load dbcapi.  Tried: " + ','.join(names))


class Root(object):
    def __init__(self, name):
        self.api = load_library(strACELibrary)
        ver = c_uint(0)
        try:
            self.api.ads_init_ex.restype = POINTER(c_int)
            context = self.api.ads_init_ex(name, API_VERSION_EX, byref(ver))
            if not context or ver.value != API_VERSION_EX:
                raise InterfaceError("dbcapi version %d required." %
                        API_VERSION_EX)
            def new_connection():
                return self.api.ads_new_connection_ex(context)
            self.api.ads_new_connection = new_connection
            def fini():
                self.api.ads_fini_ex(context)
            self.api.ads_fini = fini
        except:
            if (not self.api.ads_init(name, API_VERSION, byref(ver)) or
                ver.value != API_VERSION):
                raise InterfaceError("dbcapi version %d required." %
                        API_VERSION)
            self.api.ads_new_connection.restype = POINTER(c_int)
        # Need to set return type to some pointer type other than void
        # to avoid automatic conversion to a (32 bit) int.
        self.api.ads_prepare.restype = POINTER(c_int)

    def __del__(self):
        if self.api:
            self.api.ads_fini()


def connect(*args, **kwargs):
    """Constructor for creating a connection to a database."""
    return Connection(args, kwargs)


class Connection(object):

    def __init__(self, args, kwargs, parent = Root("PYTHON")):

        self.Error = Error
        self.Warning = Warning
        self.InterfaceError = InterfaceError
        self.DatabaseError = DatabaseError
        self.InternalError = InternalError
        self.OperationalError = OperationalError
        self.ProgrammingError = ProgrammingError
        self.IntegrityError = IntegrityError
        self.DataError = DataError
        self.NotSupportedError = NotSupportedError
        self.cursors = set()

        self.parent, self.api = parent, parent.api
        char_set = 'utf-16'
        params = ';'.join( kw + '=' + arg for kw, arg in kwargs.items())
        if isinstance(params, unicode):
            params = args.encode('utf-16')

        self.valueof = mk_valueof((A_BINARY, A_STRING), char_set)
        self.assign = mk_assign(char_set)
        self.char_set = char_set
        self.c = self.api.ads_new_connection()
        if not self.c:
            error = self.error()
            raise error

        if not self.api.ads_connect(self.c, params):
            error = self.error()
            self.api.ads_free_connection(self.c)
            self.c = None
            raise error

    def __del__(self):
        if self.c:
            self.close()

    def con(self):
        if not self.c:
            raise self.InterfaceError("not connected")
        return self.c

    def begin_transaction (self):
        return self.api.AdsBeginTransaction(self.con())

    def commit(self):
        return self.api.ads_commit(self.con())

    def rollback(self):
        return self.api.ads_rollback(self.con())

    def cancel(self):
        try:
            return self.api.ads_cancel(self.con())
        except AttributeError:
            raise InterfaceError("cancel not supported")

    def error(self):
        buf = create_string_buffer(512)
        rc = self.api.ads_error(self.con(), buf, sizeof(buf))
        if rc in (-193,-194,-195,-196):
            return IntegrityError(buf.value)
        else:
            return OperationalError(buf.value)

    def clear_error(self):
        return self.api.ads_clear_error(self.con())

    def close(self):
        c = self.con()
        self.c = None
        for x in self.cursors:
            x.close(remove=False)
        self.cursors = None
        self.api.ads_disconnect(c)
        self.api.ads_free_connection(c)

    def cursor(self):
        x = Cursor(self)
        self.cursors.add(x)
        return x

    def __enter__(self): return self.cursor()

    def __exit__(self, exc, value, tb):
        if exc:
            self.rollback()
        else:
            self.commit()

class Cursor(object):
    class TypeConverter(object):
        def __init__(self,types):
            def find_converter(t):
                return CONVERSION_CALLBACKS.get(t, lambda x: x)
            self.converters = map(find_converter, types)

        def gen(self,values):
            for converter, value in zip(self.converters, values):
                yield converter(value)

    def __init__(self, parent):
        self.parent, self.api = parent, parent.api
        self.valueof = self.parent.valueof
        self.assign = self.parent.assign
        self.char_set = self.parent.char_set
        self.arraysize = 1
        self.converter = None
        self.rowcount = -1
        self.__stmt = None
        self.description = None

    def __stmt_get(self):
        if self.__stmt is None:
            raise InterfaceError("no statement")
        elif not self.__stmt:
            raise self.parent.error()
        return self.__stmt

    def __stmt_set(self, value):
        self.__stmt = value

    stmt = property(__stmt_get, __stmt_set)

    def __del__(self):
        self.close()

    def con(self):
        if not self.parent:
            raise InterfaceError("not connected")
        return self.parent.con()

    def get_stmt(self):
        return self.stmt

    def new_statement(self, operation):
        self.free_statement()
        if isinstance( operation, unicode ):
            operation = operation.encode( "utf-16" ) + chr(0)  # +chr(0) since ACE needs 2 NULL chars for utf-16
            self.stmt = self.api.ads_prepare(self.con(), operation, True ) # True unicode utf-16
        else:
            self.stmt = self.api.ads_prepare(self.con(), operation, False ) # False, not unicode

    def free_statement(self):
        if self.__stmt:
            self.api.ads_free_stmt(self.stmt)
            self.stmt = None
            self.description = None
            self.converter = None
            self.rowcount = -1

    def close(self, remove=True):
        p = self.parent
        if p:
            self.parent = None
            if remove:
                p.cursors.remove(self)
            self.free_statement()

    def columns(self):
        info = ColumnInfo()
        for i in xrange(self.api.ads_num_cols(self.get_stmt())):
            self.api.ads_get_column_info(self.get_stmt(), i, byref(info))
            if info.native_type in [DT_NSTRING,DT_NFIXCHAR,DT_NVARCHAR,DT_LONGNVARCHAR]:
                # Precision and size here are in bytes, so convert it to chars
                # for unicode fields
                info.precision = info.precision / 2
                info.max_size = info.max_size / 2
            yield ((info.name,
                   ToPyType[info.native_type],
                   None,
                   info.max_size,
                   info.precision,
                   info.scale,
                   info.nullable,
                   info.native_type),
                   info.native_type)

    def executemany(self, operation, seq_of_parameters):

        def bind(k, col):
            param = BindParam()
            self.api.ads_describe_bind_param(self.stmt, k, byref(param))
            (self.assign)(param, col)
            self.api.ads_bind_param(self.stmt, k, byref(param))
            return param

        try:
            self.new_statement(operation)
            bind_count = self.api.ads_num_params(self.stmt)
            self.rowcount = 0
            for parameters in seq_of_parameters:
                parms = [bind(k, col)
                         for k, col in enumerate(parameters[:bind_count])]
                if not self.api.ads_execute(self.stmt):
                    raise self.parent.error()

                try:
                    self.description, types = zip(*self.columns())
                    rowcount = self.api.ads_num_rows(self.stmt)
                    self.converter = self.TypeConverter(types)
                except ValueError:
                    rowcount = self.api.ads_affected_rows(self.stmt)
                    self.description = None
                    self.converter = None
    
                if rowcount < 0:
                    # Can happen if number of rows is only an estimate
                    self.rowcount = -1
                elif self.rowcount >= 0:
                    self.rowcount += rowcount
        except:
            self.rowcount = -1
            raise

        return [(self.valueof)(param.value) for param in parms]

    def execute(self, operation, parameters = ()):
        self.executemany(operation, [parameters])

    def callproc(self, procname, parameters = ()):
        stmt = 'EXECUTE PROCEDURE '+procname+'('+','.join(len(parameters)*('?',))+')'
        return self.executemany(stmt, [parameters])

    def values(self):
        value = DataValue()
        for i in xrange(self.api.ads_num_cols(self.get_stmt())):
            rc = self.api.ads_get_column(self.get_stmt(), i, byref(value))
            # if rc < 0:
            #     print "truncation of column %d"%i
            yield (self.valueof)(value)

    def rows(self):
        if not self.description:
            raise InterfaceError("no result set")

        while self.api.ads_fetch_next(self.get_stmt()):
            yield tuple(self.converter.gen(self.values()))

    def fetchmany(self, size=None):
        if size is None:
            size = self.arraysize
        return [row for i,row in zip(xrange(size), self.rows())]

    def fetchone(self):
        rows = self.fetchmany(size=1)
        if rows:
            return rows[0]
        return None

    def fetchall(self):
        return list(self.rows())

    def setinputsizes(self, sizes):
        pass

    def setoutputsize(self, sizes, column):
        pass


def Date(*ymd):
    return "%04d/%02d/%02d"%ymd

def Time(*hms):
    return "%02d:%02d:%02d"%hms

def Timestamp(*ymdhms):
    return "%04d/%02d/%02d %02d:%02d:%02d"%ymdhms

def DateFromTicks(ticks):
    return Date(*time.localtime(ticks)[:3])

def TimeFromTicks(ticks):
    return Time(*time.localtime(ticks)[3:6])

def TimestampFromTicks(ticks):
    return Timestamp(*time.localtime(ticks)[:6])

class Binary( str ):
    pass

def ads_typecast_timestamp (s):
    "Custom timestamp converter for ADS since it uses a different string format"
    if not s: return None
    if not ' ' in s: return typecast_date(s)

    d, t, ampm = s.split()
    dates = d.split('/')
    times = t.split(':')
    seconds = times[2]
    hour = int(times[0])

    # Convert to 24 hour time
    if hour == 12:
        hour = 0
    if ampm == 'PM':
        hour += 12

    if '.' in seconds: # check whether seconds have a fractional part
        seconds, microseconds = seconds.split('.')
    else:
        microseconds = '0'

    return datetime.datetime(int(dates[2]), int(dates[0]), int(dates[1]),
        hour, int(times[1]), int(seconds), int((microseconds + '000000')[:6]))

def ads_typecast_date(s):
    "Custom date converter for ADS since it uses a different string format"
    m, d, y = s.split('/')
    return s and datetime.date(int(y), int(m), int(d)) or None # returns None if s is null

def ads_typecast_time(s): # does NOT store time zone information
    "Custom time converter for ADS since it uses a different string format"
    if not s: return None

    t, ampm = s.split()
    hour, minutes, seconds = t.split(':')

    # Convert to 24 hour time
    iHour = int(hour)
    if iHour == 12:
        iHour = 0
    if ampm == 'PM':
        iHour += 12

    if '.' in seconds: # check whether seconds have a fractional part
        seconds, microseconds = seconds.split('.')
    else:
        microseconds = '0'

    return datetime.time(iHour, int(minutes), int(seconds), int(float('.'+microseconds) * 1000000))

CONVERSION_CALLBACKS = {}
def register_converter(datatype, callback):
    CONVERSION_CALLBACKS[datatype] = callback
