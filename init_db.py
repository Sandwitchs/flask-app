import pymysql

# Update this if your MySQL has a password
MYSQL_USER = 'root'
MYSQL_PASSWORD = ''
MYSQL_HOST = 'localhost'
DB_NAME = 'sim_pesantren'

def init_database():
    try:
        # Connect without specifying database
        conn = pymysql.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD
        )
        cursor = conn.cursor()
        
        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Database '{DB_NAME}' checked/created successfully.")
    except Exception as e:
        print(f"Failed to connect to MySQL or create database. Error: {e}")
        print("Please ensure MySQL is running locally on port 3306 with user 'root' and no password.")

if __name__ == '__main__':
    init_database()
