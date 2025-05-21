
from sqlalchemy import create_engine, text

# Set the database URL
db_url = 'postgresql://stevenlong:yourpassword@localhost:5433/RecordManager_Postgre_DB'

# Create an SQLAlchemy engine
engine = create_engine(db_url)

# Example function to test the connection
def test_connection(engine):
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            for row in result:
                print(row)
    except Exception as e:
        print(f"Error connecting to the database: {e}")

# Test the connection
test_connection(engine)
