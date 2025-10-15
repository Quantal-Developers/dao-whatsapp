import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL
import logging

# Disable logging for clean output
logging.disable(logging.CRITICAL)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.cursor = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self.connection = psycopg2.connect(DATABASE_URL)
            self.cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            logger.info("Database connection established")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Database connection closed")
    
    def execute_query(self, query, params=None):
        """Execute a SELECT query and return results"""
        try:
            if not self.connection or self.connection.closed:
                self.connect()
            
            self.cursor.execute(query, params)
            results = self.cursor.fetchall()
            return results
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return None
    
    def execute_update(self, query, params=None):
        """Execute an INSERT/UPDATE/DELETE query"""
        try:
            if not self.connection or self.connection.closed:
                self.connect()
            
            self.cursor.execute(query, params)
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Update execution failed: {e}")
            self.connection.rollback()
            return False
    
    def get_table_schema(self, table_name):
        """Get schema information for a table"""
        query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position;
        """
        return self.execute_query(query, (table_name,))
    
    def get_all_tables(self):
        """Get list of all tables in the database"""
        query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
        """
        return self.execute_query(query)

# Global database manager instance
db_manager = DatabaseManager()
