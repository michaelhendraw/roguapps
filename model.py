import os
import psycopg2
import psycopg2.extras

import constant

class Conn(object):
    def __init__(self):
        DATABASE_URL = constant.DATABASE_URL
        self.connection = psycopg2.connect(DATABASE_URL, sslmode='require')
        self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    def query(self, query, params):
        if params == '':
            return self.cursor.execute(query)    
        else:
            return self.cursor.execute(query, params)
    
    def commit(self):
        return self.connection.commit()

    def __del__(self):
        self.connection.close()