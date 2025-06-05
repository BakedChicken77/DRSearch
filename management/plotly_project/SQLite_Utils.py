import sqlite3
from typing import List, Tuple, Any

class SQLiteDBHandler:
    def __init__(self, db_file: str):
        """Initialize the database connection."""
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()

    def create_table(self, table_name: str, columns: List[Tuple[str, str]]):
        """Create a new table in the database."""
        columns_with_types = ", ".join([f"{name} {data_type}" for name, data_type in columns])
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_with_types})"
        self.cursor.execute(query)
        self.conn.commit()

    def add_data(self, table_name: str, data: Tuple[Any, ...]):
        """Insert data into the specified table."""
        placeholders = ", ".join(["?"] * len(data))
        query = f"INSERT INTO {table_name} VALUES ({placeholders})"
        self.cursor.execute(query, data)
        self.conn.commit()

    def get_data(self, table_name: str, columns: List[str], where_clause: str = "", params: Tuple = ()):
        """Retrieve data from the specified table."""
        columns_str = ", ".join(columns)
        query = f"SELECT {columns_str} FROM {table_name} {where_clause}"
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def update_data(self, table_name: str, set_clause: str, where_clause: str = "", params: Tuple = ()):
        """Update data in the specified table."""
        query = f"UPDATE {table_name} SET {set_clause} {where_clause}"
        self.cursor.execute(query, params)
        self.conn.commit()

    def delete_data(self, table_name: str, where_clause: str = "", params: Tuple = ()):
        """Delete data from the specified table."""
        query = f"DELETE FROM {table_name} {where_clause}"
        self.cursor.execute(query, params)
        self.conn.commit()

    def add_field(self, table_name: str, fields: List[Tuple[str, str]]):
        """Add a single field or list of fields to a specified table."""
        for field_name, field_type in fields:
            query = f"ALTER TABLE {table_name} ADD COLUMN {field_name} {field_type}"
            self.cursor.execute(query)
        self.conn.commit()

    def remove_field(self, table_name: str, fields: List[str]):
        """Remove a single field or list of fields from a specified table."""
        # SQLite does not support dropping columns directly. We need to create a new table without the specified fields,
        # copy data from the old table, and then replace the old table with the new one.
        existing_columns_query = f"PRAGMA table_info({table_name})"
        self.cursor.execute(existing_columns_query)
        columns_info = self.cursor.fetchall()
        existing_columns = [info[1] for info in columns_info if info[1] not in fields]
        existing_columns_str = ", ".join(existing_columns)

        temp_table_name = f"{table_name}_temp"
        create_temp_table_query = f"CREATE TABLE {temp_table_name} AS SELECT {existing_columns_str} FROM {table_name}"
        self.cursor.execute(create_temp_table_query)
        
        drop_table_query = f"DROP TABLE {table_name}"
        self.cursor.execute(drop_table_query)
        
        rename_temp_table_query = f"ALTER TABLE {temp_table_name} RENAME TO {table_name}"
        self.cursor.execute(rename_temp_table_query)
        
        self.conn.commit()

    def __del__(self):
        """Close the database connection when the object is deleted."""
        self.conn.close()

def test_sqlite_db_handler():
    db = SQLiteDBHandler('test_example.db')
    
    # Define table schema
    columns = [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("text", "TEXT"),
        ("metadata", "TEXT"),
        ("parameters", "TEXT")
    ]
    
    # Create a new table
    db.create_table("elements", columns)
    
    # Add data to the table without setting the id
    db.add_data("elements", (None, 'Some large text', '{"key": "value"}', '{"param": "value"}'))
    db.add_data("elements", (None, 'Another text', '{"another_key": "another_value"}', '{"another_param": "another_value"}'))
    
    # Retrieve data from the table
    data = db.get_data("elements", ["id", "text", "metadata", "parameters"])
    print("Retrieved Data:", data)
    
    # Update data in the table
    db.update_data("elements", "text = 'Updated text'", "WHERE id = ?", (1,))
    
    # Retrieve data again to check update
    updated_data = db.get_data("elements", ["id", "text", "metadata", "parameters"], "WHERE id = ?", (1,))
    print("Updated Data:", updated_data)
    
    # Add new fields to the table
    db.add_field("elements", [("new_field1", "TEXT"), ("new_field2", "INTEGER")])
    
    # Insert data with new fields
    db.add_data("elements", (None, 'New text', '{"new_key": "new_value"}', '{"new_param": "new_value"}', 'extra_text', 123))
    
    # Retrieve data to check new fields
    new_data = db.get_data("elements", ["id", "text", "metadata", "parameters", "new_field1", "new_field2"])
    print("Data with New Fields:", new_data)
    
    # Remove fields from the table
    db.remove_field("elements", ["new_field1", "new_field2"])
    
    # Retrieve data to check removal of fields
    final_data = db.get_data("elements", ["id", "text", "metadata", "parameters"])
    print("Final Data after Removing Fields:", final_data)
    
    # Delete data from the table
    db.delete_data("elements", "WHERE id = ?", (1,))
    
    # Retrieve data again to check deletion
    final_data_after_deletion = db.get_data("elements", ["id", "text", "metadata", "parameters"])
    print("Final Data after Deletion:", final_data_after_deletion)

if __name__ == "__main__":
    test_sqlite_db_handler()
