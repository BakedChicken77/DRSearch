```python
# sqlite_manager\manager.py


import sqlite3
import json
from datetime import datetime
import logging
from typing import List, Optional, Dict, Any  # Import Any and other useful types

class SQLite_Manager:
    def __init__(self, docs_index_name, schema_file=None):
        self._docs_index_name = docs_index_name
        self._schema = self._load_schema(schema_file)
        self._valid_fields = list(self._schema.keys())
        self._connection = self._connect()
        self._cursor = self._connection.cursor()
        self._last_update_time = None
        self._create_table_if_not_exists()

    def _load_schema(self, schema_file):
        if schema_file:
            with open(schema_file, 'r') as file:
                return json.load(file)
        else:
            return {
                "uuid": "TEXT PRIMARY KEY",
                "plot_code": "INTEGER",
                "use4RAG": "BOOLEAN",
                "field1": "TEXT",
                "field2": "REAL"
            }

    def _connect(self):
        return sqlite3.connect(f'{self._docs_index_name}.db')
    
    def _create_table_if_not_exists(self):
        fields_definitions = ", ".join([f"{field} {ftype}" for field, ftype in self._schema.items()])
        query = f"CREATE TABLE IF NOT EXISTS {self._docs_index_name} ({fields_definitions})"
        self._execute_query(query)
    def _connect(self):
        # Establish connection
        return sqlite3.connect(f'{self._docs_index_name}.db')
        
    def _execute_query(self, query, params=None):
        try:
            self._cursor.execute(query, params or [])
            self._connection.commit()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
    
    def _check_valid_fields(self, fields):
        for field in fields:
            if field not in self._valid_fields:
                raise ValueError(f"Invalid field: {field}")
    
    def _update_last_modified(self):
        self._last_update_time = datetime.now()

    def set_field_values_for_all_ids(self, field_name, value):
        self._check_valid_fields([field_name])
        query = f"UPDATE {self._docs_index_name} SET {field_name} = ?"
        self._execute_query(query, [value])
        self._update_last_modified()
    
    def set_field_values_by_ids(self, ids, field_name, value):
        self._check_valid_fields([field_name])
        query = f"UPDATE {self._docs_index_name} SET {field_name} = ? WHERE uuid IN ({','.join('?' for _ in ids)})"
        self._execute_query(query, [value] + ids)
        self._update_last_modified()
    
    def get_filtered_data(self, field_name, value, fields):
        self._check_valid_fields([field_name] + fields)
        query = f"SELECT {', '.join(fields)} FROM {self._docs_index_name} WHERE {field_name} = ?"
        self._execute_query(query, [value])
        return self._cursor.fetchall()
    
    def get_property_keys(self, field_name):
        self._check_valid_fields([field_name])
        query = f"SELECT DISTINCT {field_name} FROM {self._docs_index_name}"
        self._execute_query(query)
        return [row[0] for row in self._cursor.fetchall()]
    
    def add_new_field(self, field: str, field_type: str, default_value: Any):
        if field in self._valid_fields:
            logging.warning(f"Field '{field}' already exists in the schema.")
            return
        self._schema[field] = field_type
        self._valid_fields.append(field)
        
        # Format the default value correctly for inclusion in the SQL statement
        if isinstance(default_value, str):
            default_value_formatted = f"'{default_value}'"
        elif default_value is None:
            default_value_formatted = "NULL"
        else:
            default_value_formatted = str(default_value)

        query = f"ALTER TABLE {self._docs_index_name} ADD COLUMN {field} {field_type} DEFAULT {default_value_formatted}"
        try:
            self._cursor.execute(query)
            self._connection.commit()
        except sqlite3.Error as e:
            logging.error(f"An error occurred while adding the field: {e}")
            raise
        self._update_last_modified()


    
    def get_field_values(self, fields):
        self._check_valid_fields(fields)
        query = f"SELECT {', '.join(fields)} FROM {self._docs_index_name}"
        self._execute_query(query)
        return self._cursor.fetchall()
    
    def close_weaviate_client(self):
        self._connection.close()
    
    def get_last_update_to_collection(self):
        return self._last_update_time

```

```DockerFile
# sqlite_manager\test_manager

import sqlite3
import os
import logging
from manager import SQLite_Manager  # Importing your SQLite_Manager class

# Setup logging
logging.basicConfig(level=logging.INFO)

# Test Report
failed_tests = []
passed_tests = []

def log_test_result(test_name, result, error=None):
    if result:
        passed_tests.append(test_name)
        logging.info(f"{test_name}: PASS")
    else:
        failed_tests.append((test_name, error))
        logging.error(f"{test_name}: FAIL - {error}")


def test_set_field_values_for_all_ids(SM):
    test_name = "set_field_values_for_all_ids"
    try:
        
        SM.set_field_values_for_all_ids('plot_code', 1)
        log_test_result(test_name, True)
    except Exception as e:
        log_test_result(test_name, False, str(e))

def test_set_field_values_by_ids(SM):
    test_name = "set_field_values_by_ids"
    try:
        
        ids = ['id1', 'id2']
        SM.set_field_values_by_ids(ids, 'plot_code', 1)
        log_test_result(test_name, True)
    except Exception as e:
        log_test_result(test_name, False, str(e))

def test_get_filtered_data(SM):
    test_name = "get_filtered_data"
    try:
        
        SM.get_filtered_data('plot_code', 1, ['uuid', 'plot_code'])
        log_test_result(test_name, True)
    except Exception as e:
        log_test_result(test_name, False, str(e))

def test_get_property_keys(SM):
    test_name = "get_property_keys"
    try:
        
        SM.get_property_keys('plot_code')
        log_test_result(test_name, True)
    except Exception as e:
        log_test_result(test_name, False, str(e))

def test_add_new_field(SM):
    test_name = "add_new_field"
    try:
        
        SM.add_new_field('new_field', 'TEXT', 'default_value')
        log_test_result(test_name, True)
    except Exception as e:
        log_test_result(test_name, False, str(e))

def test_get_field_values(SM):
    test_name = "get_field_values"
    try:
        
        SM.get_field_values(['uuid', 'plot_code'])
        log_test_result(test_name, True)
    except Exception as e:
        log_test_result(test_name, False, str(e))

def test_close_weaviate_client(SM):
    test_name = "close_weaviate_client"
    try:
        
        SM.close_weaviate_client()
        log_test_result(test_name, True)
    except Exception as e:
        log_test_result(test_name, False, str(e))

def test_get_last_update_to_collection(SM):
    test_name = "get_last_update_to_collection"
    try:
        
        SM.get_last_update_to_collection()
        log_test_result(test_name, True)
    except Exception as e:
        log_test_result(test_name, False, str(e))


SM = SQLite_Manager(docs_index_name='test_db')
# Run Tests

test_set_field_values_for_all_ids(SM)
test_set_field_values_by_ids(SM)
test_get_filtered_data(SM)
test_get_property_keys(SM)
test_add_new_field(SM)
test_get_field_values(SM)
test_close_weaviate_client(SM)
test_get_last_update_to_collection(SM)

# Cleanup
try:
    if os.path.exists('test_db.db'):
        SM.close_weaviate_client()  # Ensure the connection is closed
        os.remove('test_db.db')
        logging.info("Test database removed.")
except PermissionError as e:
    logging.error(f"Failed to remove test database: {e}")


# Report Results
print("\n--- Test Report ---")
if passed_tests:
    print("Passed Tests:")
    for test in passed_tests:
        print(f" - {test}")

if failed_tests:
    print("\nFailed Tests:")
    for method, error in failed_tests:
        print(f" - {method}: {error}")

if not failed_tests:
    print("\nAll tests passed successfully!")

```

