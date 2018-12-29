import os
import psycopg2
import psycopg2.extras

class Conn(object):

    def __init__(self):
        DATABASE_URL = os.getenv('DATABASE_URL', None)
        self.connection = psycopg2.connect(DATABASE_URL, sslmode='require')
        self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    def query(self, query, params):
        if params == '':
            return self.cursor.execute(query)    
        else:
            return self.cursor.execute(query, params)

    def __del__(self):
        self.connection.close()