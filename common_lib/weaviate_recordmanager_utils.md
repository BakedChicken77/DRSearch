```python
# weaviate_recordmanager_utils\Delete_All_Data_In_Weaviate.py

import os
import json
import pandas as pd
from weaviate import Client, AuthClientPassword
import weaviate
from dotenv import load_dotenv


load_dotenv()  # This loads the variables from .env into the environment

# Define the connection parameters for Weaviate database
WEAVIATE_URL = os.getenv('WEAVIATE_URL')
WEAVIATE_API_KEY = os.getenv('WEAVIATE_API_KEY')
WEAVIATE_DOCS_INDEX_NAME = os.getenv('WEAVIATE_DOCS_INDEX_NAME')

# Create a Weaviate client instance
# client = Client(
#     url=WEAVIATE_URL,
#     auth_client_secret=AuthClientPassword(api_key=WEAVIATE_API_KEY),
# )
client = weaviate.Client(
    url=WEAVIATE_URL, 
    auth_client_secret=weaviate.AuthApiKey(api_key=WEAVIATE_API_KEY),
)

# Perform the batch delete operation
result = client.batch.delete_objects(
    class_name=WEAVIATE_DOCS_INDEX_NAME,
    where={
        "operator": "Equal",
        "path": ["text_as_html"],
        "valueText": ""
    },
    output="verbose",
    dry_run=False
)

# Print the result of the delete operation
print(result)
```

```python
# weaviate_recordmanager_utils\Delete_Index_In_Weaviate.py

import os
# import sys 
# Add the parent directory to the sys.path
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import weaviate
from dotenv import load_dotenv
from langchain.indexes import SQLRecordManager
# from constants import WEAVIATE_DOCS_INDEX_NAME_SEPS
# Load environment variables
load_dotenv()

def delete_seps_docs():
    WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
    WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")
    RECORD_MANAGER_DB_URL = os.environ.get('RECORD_MANAGER_DB_URL')
    WEAVIATE_DOCS_INDEX_NAME = 'JACSKE_PRODUCTION_20241204' # Replace with index name


    if not all([WEAVIATE_URL, WEAVIATE_API_KEY, RECORD_MANAGER_DB_URL, WEAVIATE_DOCS_INDEX_NAME]):
        print("One or more environment variables are missing.")
        return

    # Initialize the SQLRecordManager
    record_manager = SQLRecordManager(
        namespace=f"weaviate/{WEAVIATE_DOCS_INDEX_NAME}",
        db_url=RECORD_MANAGER_DB_URL
    )

    # List all keys in the namespace
    keys = record_manager.list_keys()

    if not keys:
        print(f"No keys found in the namespace {WEAVIATE_DOCS_INDEX_NAME}.")
    else:
        # Delete keys using the record manager
        record_manager.delete_keys(keys)
        print(f"All keys in the namespace '{WEAVIATE_DOCS_INDEX_NAME}' have been deleted from the record manager.")

    # Initialize Weaviate client to delete data from Weaviate
    client = weaviate.Client(
        url=WEAVIATE_URL,
        auth_client_secret=weaviate.AuthApiKey(api_key=WEAVIATE_API_KEY),
    )

    # Define a batch size for deletion to avoid issues with large datasets
    batch_size = 100

    # Retrieve and delete all object IDs in the index in batches
    while True:
        response = client.query.get(WEAVIATE_DOCS_INDEX_NAME).with_additional("id").do()
        if 'data' in response and WEAVIATE_DOCS_INDEX_NAME in response['data']:
            objects = response['data'][WEAVIATE_DOCS_INDEX_NAME]
            if not objects:
                break

            for obj in objects:
                object_id = obj['id']
                client.data_object.delete(object_id)

            print(f"Batch of {len(objects)} objects deleted from Weaviate index '{WEAVIATE_DOCS_INDEX_NAME}'.")
        else:
            print(f"No more data found in Weaviate index '{WEAVIATE_DOCS_INDEX_NAME}'.")
            break

    print(f"All data in Weaviate index '{WEAVIATE_DOCS_INDEX_NAME}' has been deleted.")

if __name__ == "__main__":
    delete_seps_docs()

```

```python
# weaviate_recordmanager_utils\Delete_Index_In_Weaviate_extended.py

import os
import weaviate
from dotenv import load_dotenv
from ExtendedSQLRecordManager import ExtendedSQLRecordManager  # Import the ExtendedSQLRecordManager

# Load environment variables
load_dotenv()

def delete_seps_docs():
    WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
    WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")
    RECORD_MANAGER_DB_URL = os.getenv('RECORD_MANAGER_DB_URL')
    WEAVIATE_DOCS_INDEX_NAME = 'JACSKE_PRODUCTION_20241204' # Replace with index name

    if not all([WEAVIATE_URL, WEAVIATE_API_KEY, RECORD_MANAGER_DB_URL, WEAVIATE_DOCS_INDEX_NAME]):
        print("One or more environment variables are missing.")
        return

    # Initialize the ExtendedSQLRecordManager
    record_manager = ExtendedSQLRecordManager(
        namespace=f"weaviate/{WEAVIATE_DOCS_INDEX_NAME}",
        db_url=RECORD_MANAGER_DB_URL
    )

    # List all keys in the namespace
    keys = record_manager.list_keys()

    if not keys:
        print(f"No keys found in the namespace {WEAVIATE_DOCS_INDEX_NAME}.")
    else:
        # Delete keys using the record manager
        record_manager.delete_keys(keys)
        print(f"All keys in the namespace '{WEAVIATE_DOCS_INDEX_NAME}' have been deleted from the record manager.")

    # Initialize Weaviate client to delete data from Weaviate
    client = weaviate.Client(
        url=WEAVIATE_URL,
        auth_client_secret=weaviate.AuthApiKey(api_key=WEAVIATE_API_KEY),
    )

    # Define a batch size for deletion to avoid issues with large datasets
    batch_size = 100

    # Retrieve and delete all object IDs in the index in batches
    while True:
        response = client.query.get(WEAVIATE_DOCS_INDEX_NAME).with_additional("id").do()
        if 'data' in response and WEAVIATE_DOCS_INDEX_NAME in response['data']:
            objects = response['data'][WEAVIATE_DOCS_INDEX_NAME]
            if not objects:
                break

            for obj in objects:
                object_id = obj['id']
                client.data_object.delete(object_id)

            print(f"Batch of {len(objects)} objects deleted from Weaviate index '{WEAVIATE_DOCS_INDEX_NAME}'.")
        else:
            print(f"No more data found in Weaviate index '{WEAVIATE_DOCS_INDEX_NAME}'.")
            break

    print(f"All data in Weaviate index '{WEAVIATE_DOCS_INDEX_NAME}' has been deleted.")

if __name__ == "__main__":
    delete_seps_docs()

```

```python
# weaviate_recordmanager_utils\delete_sql_Tables.py

import psycopg2, os
from dotenv import load_dotenv
load_dotenv()  # This loads the variables from .env into the environment
RECORD_MANAGER_DB_URL= os.getenv('RECORD_MANAGER_DB_URL')

def get_db_connection():
    # This should match your database connection setup
    return psycopg2.connect(RECORD_MANAGER_DB_URL)

def drop_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Drop the document_elements table first due to foreign key constraint
        cursor.execute("DROP TABLE IF EXISTS document_elements;")
        # Then drop the documents table
        cursor.execute("DROP TABLE IF EXISTS documents;")
        conn.commit()
        print("Tables dropped successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    drop_tables()

```

```python
# weaviate_recordmanager_utils\ExtendedSQLRecordManager.py


import hashlib
import os
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, create_engine, inspect, UniqueConstraint, Index
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, declarative_base
import logging

from langchain.indexes import SQLRecordManager, index
from langchain.indexes._sql_record_manager import UpsertionRecord  # Importing the UpsertionRecord class
import uuid  # Importing uuid module for UUID generation

Base = declarative_base()

class DocRecord(Base):
    """A SQLAlchemy model for storing document records."""
    __tablename__ = 'doc_records'
    uuid = Column(
        String,
        index=True,
        default=lambda: str(uuid.uuid4()),  # Ensuring UUID is generated as a string
        primary_key=True,
        nullable=False,
    )
    group_id = Column(String, index=True, nullable=False)
    namespace = Column(String, index=True, nullable=False)
    hash = Column(String)
    last_modified = Column(DateTime)
    ingestion_date = Column(DateTime)
    updated_at = Column(Float, index=True)
    text_key = Column(String, default='0')
    embedder_model = Column(String, default='0')
    html_summary_model = Column(String, default='0')
    html_summary_prompt = Column(String, default='0')
    max_chunk_size = Column(Integer, default=0)
    html_summaries = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("group_id", "namespace", name="uix_group_id_namespace"),
        Index("ix_group_id_namespace", "group_id", "namespace"),
    )

class ExtendedSQLRecordManager(SQLRecordManager):
    """A class that extends SQLRecordManager to manage document-level records."""

    def __init__(self, namespace, db_url=None, engine=None, engine_kwargs=None, async_mode=False, logger=None):
        """Initializes the ExtendedSQLRecordManager with a namespace and database URL.

        Args:
            namespace: The namespace for the vector store.
            db_url: The database URL for connecting to the SQL database.
            engine: An already existing SQL Alchemy engine.
            engine_kwargs: Additional keyword arguments for the engine.
            async_mode: Whether to create an async engine.
            logger: A logger object for logging messages.
        """
        super().__init__(namespace=namespace, db_url=db_url, engine=engine, engine_kwargs=engine_kwargs, async_mode=async_mode)
        if db_url:
            self.engine = create_engine(db_url, **(engine_kwargs or {}))
        elif engine:
            self.engine = engine
        else:
            raise ValueError("Must specify either db_url or engine")

        self.Session = sessionmaker(bind=self.engine)
        self.logger = logger if logger else logging.getLogger(__name__)
        self.record_manager = SQLRecordManager(namespace=namespace, db_url=db_url, engine=engine, engine_kwargs=engine_kwargs, async_mode=async_mode)
        self.namespace = namespace
        # self.record_manager.create_schema()
        self.ensure_schema_exists()
        # self.identify_and_add_missing_columns()  # Ensure all columns are present
   
    def create_schema(self):
        """Creates the necessary database schema if it doesn't exist."""
        # super().create_schema()
        if not inspect(self.engine).has_table('doc_records'):
            self._prompt_user_and_create_tables()

    def ensure_schema_exists(self):
        """Ensures the necessary database schema exists and matches the defined schema."""
        inspector = inspect(self.engine)
        # self.record_manager.create_schema()
        if not inspector.has_table("upsertion_record") or not inspector.has_table("doc_records") or not self._schema_matches():
            self._prompt_user_and_create_tables()
            self.logger.info("Schema created.")
        else:
            self.logger.info("Schema already exists and matches the defined schema.")
    
    def _prompt_user_and_create_tables(self):
        prompt_message = """\
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

The tables 'doc_records' and 'upsertion_record' do not exist or do not match the defined schema.
User must first run:
'Delete_doc_records_table_and_create_a_new_table.sql'
to create tables before documents can be ingested via the ExtendedSQLRecordManager.py

INGESTION ABORTED!
"""
        print(prompt_message)
        self.logger.info(prompt_message)
        exit()
    
        
    def _schema_matches(self):
        """Checks if the existing schema matches the defined schema for DocRecord and UpsertionRecord."""
        inspector = inspect(self.engine)

        # Check DocRecord table
        doc_record_columns = inspector.get_columns('doc_records')
        doc_record_expected_columns = {col.name: col.type for col in DocRecord.__table__.columns}
        for col in doc_record_columns:
            if col['name'] not in doc_record_expected_columns or not isinstance(col['type'], type(doc_record_expected_columns[col['name']])):
                return False

        # Check UpsertionRecord table
        upsertion_record_columns = inspector.get_columns('upsertion_record')
        upsertion_record_expected_columns = {col.name: col.type for col in UpsertionRecord.__table__.columns}
        for col in upsertion_record_columns:
            if col['name'] not in upsertion_record_expected_columns or not isinstance(col['type'], type(upsertion_record_expected_columns[col['name']])):
                return False

        return True

    def get_document_hash(self, file_path):
        """Generates an MD5 hash for the specified document.

        Args:
            file_path: The path to the document file.

        Returns:
            The MD5 hash of the document.
        """
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        return file_hash

    def get_document_status(self, group_id):
        """Checks the status of a document (new, modified, or current).

        Args:
            group_id: The group ID of the document.

        Returns:
            The status of the document ('new', 'modified', or 'current').
        """

        group_id= str(group_id)
        session = self.Session()
        try:
            doc_record = session.query(DocRecord).filter_by(group_id=group_id, namespace=self.namespace).first()
            if doc_record:
                file_hash = self.get_document_hash(group_id)
                #last_modified = datetime.fromtimestamp(os.path.getmtime(group_id))
                if doc_record.hash == file_hash:# and doc_record.last_modified == last_modified:
                    return 'current'
                else:
                    return 'modified'
            else:
                return 'new'
        finally:
            session.close()

    def delete_document(
        self,
        vectorstore,
        namespace,
        group_ids
    ):
        """
        Delete documents from the vector store and the record manager based on the provided namespace and list of group_ids.

        Args:
            vectorstore: The vector store object.
            namespace: The namespace for the vector store.
            group_ids: A list of group IDs to be deleted.
        """

        # List all keys in the namespace that are also in the provided list of group_ids
        keys = self.record_manager.list_keys(group_ids=group_ids)

        if not keys:
             self.logger.info(f"No keys found in the namespace {namespace} for the provided group IDs.")
        else:
            # Delete keys using the record manager
            self.record_manager.delete_keys(keys)
            self.logger.info(f"All keys in the namespace '{namespace}' for the provided group IDs have been deleted from the record manager.")

        # Initialize Weaviate client to delete data from Weaviate
        client = vectorstore._client

        try:
            # Retrieve and delete all object IDs in the index in batches
            while True:
                response = client.query.get(namespace).with_additional("id").do()
                if 'data' in response and namespace in response['data']:
                    objects = response['data'][namespace]
                    if not objects:
                        break

                    for obj in objects:
                        object_id = obj['id']
                        client.data_object.delete(object_id)

                    self.logger.info(f"Batch of {len(objects)} objects deleted from Weaviate index '{namespace}'.")

                else:
                    self.logger.info(f"No more data found in Weaviate index '{namespace}'.")
                    break

        except Exception as e:
            self.logger.error(f"Error deleting objects from Weaviate index '{namespace}': {e}")


    def update_document_record(self, session, group_id, file_hash, last_modified, ingestion_date, **kwargs):
        """Updates or inserts a document record in the database.

        Args:
            session: The SQLAlchemy session.
            group_id: The group ID of the document.
            file_hash: The MD5 hash of the document.
            last_modified: The last modified timestamp of the document.
            ingestion_date: The ingestion date of the document.
            **kwargs: Additional columns for document processing information.
        """
        existing_doc = session.query(DocRecord).filter_by(group_id=group_id, namespace=self.namespace).first()
        if existing_doc:
            # Update the existing record
            existing_doc.hash = file_hash
            existing_doc.last_modified = last_modified
            existing_doc.ingestion_date = ingestion_date
            for key, value in kwargs.items():
                if hasattr(existing_doc, key):
                    setattr(existing_doc, key, value)
            self.logger.info(f"Updated existing document record for {group_id}")
        else:
            # Insert a new record
            new_doc_record = DocRecord(
                group_id=group_id,
                hash=file_hash,
                last_modified=last_modified,
                namespace=self.namespace,
                ingestion_date=ingestion_date,
                **{k: v for k, v in kwargs.items() if hasattr(DocRecord, k)}
            )
            session.add(new_doc_record)
            self.logger.info(f"Added new document record for {group_id}")

    def remove_document(self, vectorstore, namespace, file_paths, batch_size=10):
        """
        Removes document records from the database and deletes them from the vector store.

        Args:
            vectorstore: The vector store object.
            namespace: The namespace for the vector store.
            file_paths: A list of file paths to be removed.
            batch_size: The number of documents to process in each batch.
        """
        # Initialize a database session
        session = self.Session()
        
        try:
            # Lists to hold group IDs
            list_of_group_ids = file_paths

            self.logger.info(f"Total group IDs to remove: {len(list_of_group_ids)}")

            # Process documents in batches
            for i in range(0, len(list_of_group_ids), batch_size):
                self.logger.info(f"Processing batch starting at index {i}")
                batch_group_ids = list_of_group_ids[i:i + batch_size]
                self.logger.info(f"Batch group IDs: {batch_group_ids}")

                # Begin a nested transaction for batch processing
                with session.begin_nested():
                    try:
                        # Delete existing documents from upsertion_record
                        self.delete_document(
                            vectorstore=vectorstore,
                            namespace=namespace,
                            group_ids=batch_group_ids
                        )

                        # Delete existing documents from doc_records
                        session.query(DocRecord).filter(
                            DocRecord.group_id.in_(batch_group_ids),
                            DocRecord.namespace == namespace
                        ).delete(synchronize_session=False)

                        # Commit the nested transaction
                        session.commit()

                    except Exception as e:
                        # Rollback the nested transaction in case of an error
                        session.rollback()
                        self.logger.error(f"Error removing documents batch: {e}")
                        raise

        except Exception as e:
            # Rollback the outer transaction in case of an error
            session.rollback()
            self.logger.error(f"Error removing documents: {e}")
        finally:
            # Close the database session
            session.close()
        
        self.logger.info("Document removal process completed.")




    def add_document(self, elements, vectorstore, cleanup='incremental', force_update=False, batch_size=10, **kwargs):
        """
        Adds new document records to the database and indexes them in the vector store.

        Args:
            elements: List of elements to be indexed.
            vectorstore: The vector store object.
            cleanup: The cleanup mode for the indexing.
            force_update: Force update documents even if they are present in the record manager.
            batch_size: The number of documents to process in each batch.
            **kwargs: Additional columns for document processing information.
        """
        # Initialize a database session
        session = self.Session()
        
        # Dictionary to hold indexing statistics
        total_indexing_stats = {
            'num_added': 0,
            'num_updated': 0,
            'num_skipped': 0,
            'num_deleted': 0
        }
        
        try:
            # Lists to hold group IDs
            list_of_group_ids = []
            up_to_date_group_ids = []

            # Populate list_of_group_ids with unique file paths from elements
            for element in elements:
                group_id = element.metadata['file_path']
                if group_id and group_id not in list_of_group_ids:
                    list_of_group_ids.append(group_id)

            # Check the status of each document and add up-to-date ones to up_to_date_group_ids
            for group_id in list_of_group_ids:
                file_hash = self.get_document_hash(group_id)
                last_modified = datetime.fromtimestamp(os.path.getmtime(group_id))
                existing_doc_status = self.get_document_status(group_id)
                
                if existing_doc_status == 'current':
                    self.logger.info(f"Document {group_id} is already up-to-date.")
                    up_to_date_group_ids.append(group_id)

            # Remove up-to-date group IDs from list_of_group_ids
            list_of_group_ids = [group_id for group_id in list_of_group_ids if group_id not in up_to_date_group_ids]

            self.logger.info(f"Total group IDs to process: {len(list_of_group_ids)}")

            # Process documents in batches
            for i in range(0, len(list_of_group_ids), batch_size):
                self.logger.info(f"Processing batch starting at index {i}")
                batch_group_ids = list_of_group_ids[i:i + batch_size]
                self.logger.info(f"Batch group IDs: {batch_group_ids}")
                batch_elements = [element for element in elements if element.metadata['file_path'] in batch_group_ids]

                # Begin a nested transaction for batch processing
                with session.begin_nested():
                    try:
                        # Delete existing documents before adding new ones
                        self.delete_document(
                            vectorstore=vectorstore,
                            namespace=self.namespace,
                            group_ids=batch_group_ids
                        )

                        # Index the entire batch of elements once
                        indexing_stats = index(
                            batch_elements,
                            self.record_manager,
                            vectorstore,
                            cleanup=cleanup,
                            source_id_key="file_path",
                            force_update=force_update,
                        )

                        # Accumulate indexing stats
                        for key in total_indexing_stats:
                            total_indexing_stats[key] += indexing_stats.get(key, 0)

                        # Update document records after successful indexing
                        for group_id in batch_group_ids:
                            file_hash = self.get_document_hash(group_id)
                            last_modified = datetime.fromtimestamp(os.path.getmtime(group_id))
                            ingestion_date = datetime.now()

                            # Ensure html_summaries is stored as 1 or 0
                            if 'html_summaries' in kwargs:
                                kwargs['html_summaries'] = 1 if kwargs['html_summaries'] in [True, 1] else 0

                            # Update the document record in the database
                            self.update_document_record(session, group_id, file_hash, last_modified, ingestion_date, **kwargs)

                        # Commit the nested transaction
                        session.commit()

                    except Exception as e:
                        # Rollback the nested transaction in case of an error
                        session.rollback()
                        self.logger.error(f"Error adding documents batch: {e}")
                        raise

        except Exception as e:
            # Rollback the outer transaction in case of an error
            session.rollback()
            self.logger.error(f"Error adding documents: {e}")
        finally:
            # Close the database session
            session.close()
        
        # Return the accumulated indexing statistics
        return total_indexing_stats







    def get_documents_by_namespace(self):
        """Retrieves all documents stored in the specified namespace.

        Returns:
            A list of tuples containing file paths, last modified dates, hashes, 
            and additional columns that contain the parameters used during processing 
            such as max_chunk_size, embedder_model, etc...
        """
        session = self.Session()
        try:
            docs = session.query(DocRecord).filter_by(namespace=self.namespace).all()
            return [(doc.group_id, doc.last_modified, doc.hash, doc.text_key, doc.embedder_model, 
                     doc.html_summary_model, doc.html_summary_prompt, doc.max_chunk_size, doc.html_summaries, doc.ingestion_date) for doc in docs]
        finally:
            session.close()

    def get_default_columns_from_docrecord(self):
        """Retrieve columns with default values from the DocRecord class."""
        default_columns = {}
        for column in DocRecord.__table__.columns:
            if column.default is not None:
                default_columns[column.name] = column
        return default_columns

    def identify_and_add_missing_columns(self):
        """Identifies and adds missing columns with default values in the doc_records table."""
        session = self.Session()
        try:
            inspector = inspect(self.engine)
            # Inspect current columns in doc_records table
            current_doc_columns = {col['name'] for col in inspector.get_columns('doc_records')}

            # Get expected columns from DocRecord
            expected_doc_columns = self.get_default_columns_from_docrecord()

            # Find discrepancies
            missing_in_doc_records = {col_name: col_type for col_name, col_type in expected_doc_columns.items() if col_name not in current_doc_columns}

            # Log discrepancies
            if missing_in_doc_records:
                self.logger.warning(f"Missing columns in doc_records table: {list(missing_in_doc_records.keys())}")

                with self.engine.connect() as connection:
                    for column_name, column in missing_in_doc_records.items():
                        # SQL command to add a column to the table
                        col_type = str(column.type.compile(self.engine.dialect))
                        default_value = column.default.arg if column.default is not None else None
                        alter_table_command = f'ALTER TABLE doc_records ADD COLUMN {column_name} {col_type} DEFAULT {default_value}'
                        connection.execute(alter_table_command)
                        self.logger.info(f"Added missing column {column_name} to doc_records table.")
     
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error identifying and adding missing columns: {e}")
        finally:
            session.close()

```

```python
# weaviate_recordmanager_utils\getSchema_weaviate.py

import weaviate
import json
import os
from dotenv import load_dotenv
load_dotenv()  # This loads the variables from .env into the environment

# Define the connection parameters for Weaviate database
WEAVIATE_URL=os.getenv('WEAVIATE_URL')
WEAVIATE_API_KEY=os.getenv('WEAVIATE_API_KEY')
RECORD_MANAGER_DB_URL= os.getenv('RECORD_MANAGER_DB_URL')
# WEAVIATE_URL = os.getenv('WEAVIATE_URL') or 'http://localhost:8080'
# WEAVIATE_API_KEY = os.getenv('WEAVIATE_API_KEY')  # API key if needed, else set it to None

# Create a client to interact with Weaviate
client = weaviate.Client(url=WEAVIATE_URL, auth_client_secret=weaviate.AuthApiKey(api_key=WEAVIATE_API_KEY))

def print_schema():
    # Fetch the schema from Weaviate
    schema = client.schema.get()
    
    # Serialize the schema dictionary to a JSON formatted string for pretty printing
    schema_str = json.dumps(schema, indent=2)
    
    # Print the schema to the console
    print(schema_str)

if __name__ == "__main__":
    # Print the schema when the script is executed
    print_schema()

```

```python
# weaviate_recordmanager_utils\Get_Weaviate_Field_Names.py

import os
import weaviate
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def list_field_names():
    WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
    WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")
    WEAVIATE_DOCS_INDEX_NAME = 'SEPs_F_T_C_W_A_V_Summaries_5000'  # Replace with your actual index name

    if not all([WEAVIATE_URL, WEAVIATE_API_KEY, WEAVIATE_DOCS_INDEX_NAME]):
        print("One or more environment variables are missing.")
        return

    # Initialize Weaviate client
    client = weaviate.Client(
        url=WEAVIATE_URL,
        auth_client_secret=weaviate.AuthApiKey(api_key=WEAVIATE_API_KEY),
    )

    # Retrieve the schema for the specified index
    schema = client.schema.get()
    
    # Find the class corresponding to the specified index
    class_schema = next((cls for cls in schema['classes'] if cls['class'] == WEAVIATE_DOCS_INDEX_NAME), None)
    
    if not class_schema:
        print(f"No schema found for index '{WEAVIATE_DOCS_INDEX_NAME}'.")
        return

    # List all field names in the class schema
    field_names = [prop['name'] for prop in class_schema['properties']]
    
    if not field_names:
        print(f"No fields found in the index '{WEAVIATE_DOCS_INDEX_NAME}'.")
    else:
        print(f"Fields in the index '{WEAVIATE_DOCS_INDEX_NAME}':")
        for field in field_names:
            print(field)

if __name__ == "__main__":
    list_field_names()

```

```python
# weaviate_recordmanager_utils\Get_Weaviate_Index_Names.py

import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from langchain.indexes._sql_record_manager import UpsertionRecord  # Adjust the import if the path is different

# Load environment variables
load_dotenv()

def print_current_indexes():
    RECORD_MANAGER_DB_URL = os.environ.get('RECORD_MANAGER_DB_URL')

    if not RECORD_MANAGER_DB_URL:
        print("The environment variable RECORD_MANAGER_DB_URL is missing.")
        return

    # Create an engine and session
    engine = create_engine(RECORD_MANAGER_DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Query to get all unique namespaces
        result = session.query(UpsertionRecord.namespace).distinct().all()
        namespaces = [row[0] for row in result]
        
        print("Current indexes managed by the record manager:")
        for namespace in namespaces:
            # Strip the "weaviate/" prefix if present
            index_name = namespace.split("/", 1)[-1]
            print(index_name)
    finally:
        session.close()

if __name__ == "__main__":
    print_current_indexes()

```

```python
# weaviate_recordmanager_utils\Get_Weaviate_Index_Names_extended.py

import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from ExtendedSQLRecordManager import ExtendedSQLRecordManager, UpsertionRecord  # Import the ExtendedSQLRecordManager and UpsertionRecord

# Load environment variables
load_dotenv()

def print_current_indexes():
    RECORD_MANAGER_DB_URL = os.getenv('RECORD_MANAGER_DB_URL')

    if not RECORD_MANAGER_DB_URL:
        print("The environment variable RECORD_MANAGER_DB_URL is missing.")
        return

    # Initialize the ExtendedSQLRecordManager
    record_manager = ExtendedSQLRecordManager(namespace="", db_url=RECORD_MANAGER_DB_URL)

    # Create a session
    session = record_manager.Session()

    try:
        # Query to get all unique namespaces
        result = session.query(UpsertionRecord.namespace).distinct().all()
        namespaces = [row[0] for row in result]
        
        print("Current indexes managed by the record manager:")
        for namespace in namespaces:
            # Strip the "weaviate/" prefix if present
            index_name = namespace.split("/", 1)[-1]
            print(index_name)
    finally:
        session.close()

if __name__ == "__main__":
    print_current_indexes()

```

```python
# weaviate_recordmanager_utils\Get_Weaviate_Info.py

import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import weaviate
from langchain.indexes._sql_record_manager import UpsertionRecord  # Adjust the import if the path is different

# Load environment variables
load_dotenv()

def print_current_indexes():
    RECORD_MANAGER_DB_URL =  os.getenv('RECORD_MANAGER_DB_URL')

    if not RECORD_MANAGER_DB_URL:
        print("The environment variable RECORD_MANAGER_DB_URL is missing.")
        return

    # Create an engine and session
    engine = create_engine(RECORD_MANAGER_DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Query to get all unique namespaces
        result = session.query(UpsertionRecord.namespace).distinct().all()
        namespaces = [row[0] for row in result]
        
        print("Current indexes managed by the record manager:")
        for namespace in namespaces:
            print(namespace)
            # Strip the "weaviate/" prefix if present
            index_name = namespace.split("/", 1)[-1]
            print_weaviate_index_details(index_name)
    finally:
        session.close()

def print_weaviate_index_details(index_name):
    WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
    WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")

    if not all([WEAVIATE_URL, WEAVIATE_API_KEY, index_name]):
        print("One or more environment variables are missing.")
        return

    # Initialize Weaviate client
    client = weaviate.Client(
        url=WEAVIATE_URL,
        auth_client_secret=weaviate.AuthApiKey(api_key=WEAVIATE_API_KEY),
    )

    # Retrieve the schema for the specified index
    schema = client.schema.get()
    
    # Find the class corresponding to the specified index
    class_schema = next((cls for cls in schema['classes'] if cls['class'] == index_name), None)
    
    if not class_schema:
        print(f"No schema found for index '{index_name}'.")
        return

    # List all field names in the class schema
    field_names = [prop['name'] for prop in class_schema['properties']]
    
    if not field_names:
        print(f"No fields found in the index '{index_name}'.")
    else:
        print(f"Fields in the index '{index_name}':")
        for field in field_names:
            print(field)
    
    # Debugging: Print the entire properties to understand their structure
    print(f"Properties in the index '{index_name}':")
    for prop in class_schema['properties']:
        print(prop)

    # List all field names that have embeddings
    embedding_fields = [prop['name'] for prop in class_schema['properties'] if prop.get('vectorize', False) or 'vectorize' in prop]
    
    if not embedding_fields:
        print(f"No fields with embeddings found in the index '{index_name}'.")
    else:
        print(f"Fields with embeddings in the index '{index_name}':")
        for field in embedding_fields:
            print(field)

if __name__ == "__main__":
    print_current_indexes()

```

```python
# weaviate_recordmanager_utils\List_RecordManager_Indexes.py

import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from langchain.indexes._sql_record_manager import UpsertionRecord  # Adjust the import if the path is different

# Load environment variables
load_dotenv()

def print_current_indexes():
    RECORD_MANAGER_DB_URL =  os.getenv('RECORD_MANAGER_DB_URL')

    if not RECORD_MANAGER_DB_URL:
        print("The environment variable RECORD_MANAGER_DB_URL is missing.")
        return

    # Create an engine and session
    engine = create_engine(RECORD_MANAGER_DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Query to get all unique namespaces
        result = session.query(UpsertionRecord.namespace).distinct().all()
        namespaces = [row[0] for row in result]
        
        print("Current indexes managed by the record manager:")
        for namespace in namespaces:
            print(namespace)
    finally:
        session.close()

if __name__ == "__main__":
    print_current_indexes()

```

```python
# weaviate_recordmanager_utils\List_RecordManager_Indexes_extended.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from ExtendedSQLRecordManager import ExtendedSQLRecordManager, UpsertionRecord  # Import the ExtendedSQLRecordManager and UpsertionRecord

# Load environment variables
load_dotenv()

def print_current_indexes():
    RECORD_MANAGER_DB_URL = os.getenv('RECORD_MANAGER_DB_URL')

    if not RECORD_MANAGER_DB_URL:
        print("The environment variable RECORD_MANAGER_DB_URL is missing.")
        return

    # Initialize the ExtendedSQLRecordManager
    record_manager = ExtendedSQLRecordManager(namespace="", db_url=RECORD_MANAGER_DB_URL)

    # Create a session
    session = record_manager.Session()

    try:
        # Query to get all unique namespaces
        result = session.query(UpsertionRecord.namespace).distinct().all()
        namespaces = [row[0] for row in result]
        
        print("Current indexes managed by the record manager:")
        for namespace in namespaces:
            print(namespace)
    finally:
        session.close()

if __name__ == "__main__":
    print_current_indexes()

```

```python
# weaviate_recordmanager_utils\List_RecordManager_PrimaryKey.py

import os
from sqlalchemy import create_engine, MetaData, Table

def print_upsertionrecord_primary_key():
    RECORD_MANAGER_DB_URL = os.getenv('RECORD_MANAGER_DB_URL')

    if not RECORD_MANAGER_DB_URL:
        print("The environment variable RECORD_MANAGER_DB_URL is missing.")
        return

    # Create an engine
    engine = create_engine(RECORD_MANAGER_DB_URL)
    metadata = MetaData()

    # Reflect the table from the database
    upsertionrecord_table = Table('upsertion_record', metadata, autoload_with=engine)

    # Get the primary key columns
    primary_keys = [key.name for key in upsertionrecord_table.primary_key]

    print(f"Primary key columns in 'upsertion_record': {primary_keys}")

if __name__ == "__main__":
    print_upsertionrecord_primary_key()
```

```python
# weaviate_recordmanager_utils\query_weaviate_test.py

import os
import json
import pandas as pd
from weaviate import Client, AuthClientPassword
import weaviate
from dotenv import load_dotenv

load_dotenv()  # This loads the variables from .env into the environment

# Define the connection parameters for Weaviate database
WEAVIATE_URL = os.getenv('WEAVIATE_URL')
WEAVIATE_API_KEY = os.getenv('WEAVIATE_API_KEY')

# Create a Weaviate client instance
# client = Client(
#     url=WEAVIATE_URL,
#     auth_client_secret=AuthClientPassword(api_key=WEAVIATE_API_KEY),
# )
client = weaviate.Client(
    url=WEAVIATE_URL, 
    auth_client_secret=weaviate.AuthApiKey(api_key=WEAVIATE_API_KEY),
)

def fetch_documents_graphql():
    # GraphQL query to get documents with detailed properties
    query = """
    {
        Get {
            JACSKE_HDD(limit: 2) {
                category
            }
        }
    }
    """

    # Fetch the data from Weaviate using the GraphQL query
    response = client.query.raw(query)

    return response

# Fetch documents
docs = fetch_documents_graphql()

# Check if data is retrieved successfully and store it in an Excel file
if 'data' in docs and 'Get' in docs['data'] and 'JACSKE_HDD' in docs['data']['Get']:
    # Convert the list of dictionaries into a DataFrame
    df = pd.DataFrame(docs['data']['Get']['JACSKE_HDD'])
    
    # Specify the filename for the Excel file
    excel_filename = 'documents_data.xlsx'
    
    # Write DataFrame to an Excel file
    df.to_excel(excel_filename, index=False)
    print(f"Data successfully written to {excel_filename}")
else:
    print("No data found or query failed.")

```

```python
# weaviate_recordmanager_utils\record_manager_util.py

import os
import json
import weaviate
from contextlib import contextmanager
from weaviate.auth import AuthApiKey
from dotenv import load_dotenv
from .ExtendedSQLRecordManager import ExtendedSQLRecordManager, UpsertionRecord
from sqlalchemy import create_engine, text
import pprint
import numpy as np
import numbers


ID_FIELD_NAME = "_additional { id }"
VECTOR_FIELD_NAME = "_additional { vector }"

def determine_data_type(value):
    if isinstance(value, list):
        return "text[]"
    elif isinstance(value, int):
        return "int"
    elif isinstance(value, float):
        return "number"
    elif value is None:
        return "text"
    else:
        return "text"


class RecordManager_Util:
    def __init__(self, weaviate_url=None, weaviate_api_key=None, docs_index_name=None, record_man_url=None, text_key='page_content'):
        """
        Initializes the RecordManager_Util class.

        Parameters:
        - weaviate_url: URL for Weaviate instance.
        - weaviate_api_key: API key for Weaviate.
        - client: An existing Weaviate client instance (optional).
        - docs_index_name: The index name for documents in Weaviate (optional).
        - record_man_url: URL for the record manager (optional).
        """
        load_dotenv()  # Load environment variables

        self.text_key=text_key

        self.docs_index_name = docs_index_name
        self.record_man_url = record_man_url or os.getenv('RECORD_MANAGER_DB_URL')

        self.record_manager = None

        if docs_index_name and record_man_url:
            self.record_manager = self.init_record_manager()

        self.weaviate_url = weaviate_url or os.getenv('WEAVIATE_URL')
        self.weaviate_api_key = weaviate_api_key or os.getenv('WEAVIATE_API_KEY')
        if not weaviate_url or not weaviate_api_key:
            # raise ValueError("Both weaviate_url and weaviate_api_key must be provided.")
            print()

    @contextmanager
    def get_weaviate_client(self, weaviate_url=None, weaviate_api_key=None ):
        if not self.weaviate_url or not self.weaviate_api_key:
            if not weaviate_url or not weaviate_api_key: 
                raise ValueError("Both weaviate_url and weaviate_api_key must be provided.")
            else:
                self.weaviate_url = weaviate_url
                self.weaviate_api_key = weaviate_api_key
        elif weaviate_url or weaviate_api_key:
            raise ValueError("weaviate_url and weaviate_api_key have already be set and can not be changed.")

        client = weaviate.Client(
            url=self.weaviate_url,
            auth_client_secret=AuthApiKey(api_key=self.weaviate_api_key),
        )
        try:
            yield client
        finally:
            client._connection.close()

    def init_record_manager(self, record_man_url=None, docs_index_name=None):
        """Initialize the SQLRecordManager"""
        docs_index_name = self.docs_index_name

        if not self.record_manager:
            record_man_url = self._check_record_man_url(record_man_url)
            docs_index_name = self._check_docs_index_name(docs_index_name)

            self.record_manager = ExtendedSQLRecordManager(
                namespace=f"weaviate/{docs_index_name}",
                db_url=record_man_url
            )
        else:
            print(f"""Record manager already initialized using:
record_man_url = {self.record_man_url}
docs_index_name = {self.docs_index_name}\
""")
        return self.record_manager

    def delete_all_data(self, client, docs_index_name=None):
        """
        Deletes all data in the specified Weaviate index.

        Parameters:
        - docs_index_name: The index name for documents in Weaviate (optional).
        """
        docs_index_name = self._check_docs_index_name(docs_index_name)

        # Ask the user for confirmation before proceeding with the delete operation
        confirmation = input("Are you sure you want to delete all data in Weaviate? This action cannot be undone. (yes/no): ")
        if confirmation.lower() != 'yes':
            print("Delete operation canceled.")
            return

        # Perform the batch delete operation
        result = client.batch.delete_objects(
            class_name=docs_index_name,
            where={
                "operator": "Equal",
                "path": ["text_as_html"],
                "valueText": ""
            },
            output="verbose",
            dry_run=False
        )

        # Print the result of the delete operation
        print(result)


    def get_filtered_data(self, client, field, value, field_names, vector=False):
        docs_index_name = self.docs_index_name
        if not isinstance(value, int) and not isinstance(value, list):
            value = json.dumps(value)[1:-1]

        #we want to keep 'id' as-is because _check_valid_fields
        # will replace 'id' with ID_FIELD_NAME which won't work as the filter field
        if 'id' in field:
            if isinstance(field,list):
                if len(field) != 1:
                    field.remove('id') 
                    field, field_type = self._check_valid_fields(client, field)
                    field.append('id')
                    field_type.append('string')
                else:
                    field = field[0]
                    field_type = 'string'
            else:
                field = 'id'
                field_type = 'string'

        else:
            field, field_type = self._check_valid_fields(client, field)

        if not field:
            raise ValueError(f"""Field {field} is not a valid field name for index {docs_index_name}""")
        #convert list of single string to a string
        # if isinstance(field, list):
        #     field = field[0]
        #     field_type = field_type[0]

        # Here we need to replace 'id' with ID_FIELD_NAME if 'id' is present
        field_names, _ = self._check_valid_fields(client, field_names)
        if not field_names:
            raise ValueError(f"""field_names {field_names} is not a valid field name for index {docs_index_name}""")
        # Ensure ID_FIELD_NAME is always included in the field names
        field_names.append(ID_FIELD_NAME)
        # Include vector if requested
        if vector:
            field_names.append(VECTOR_FIELD_NAME)


        # Construct the where clause for the query
        # where_clause = {
        #     "path": field,
        #     "operator": "Equal",
        #     type_parameter: value
        # }

        where_clause = self._create_where_clause(field, value, field_type)

        # Perform the query
        result = client.query.get(
            docs_index_name,
            field_names
        ).with_where(where_clause).do()

        if result.get('errors',None):
            print(f"Query returned the following error: {result['errors']}")

        data = result["data"]["Get"][docs_index_name]

        # Format the data to include 'id' and 'vector' fields appropriately
        return self._format_id_vector_data(data)

    def _create_where_clause(self, fields, values, field_types):
        if isinstance(fields, list) and isinstance(values, list) and isinstance(field_types, list):
            if len(fields) != len(values) or len(fields) != len(field_types):
                raise ValueError("The length of fields, values, and field_types must match.")

            operands = []
            for field, value, field_type in zip(fields, values, field_types):
                # Check if field_type is a list and extract the first element
                if isinstance(field_type, list):
                    field_type = field_type[0]

                type_parameter = self._get_type_parameter_from_type(field_type)
                operands.append({
                    "path": [field],
                    "operator": "Equal",
                    type_parameter: value
                })

            where_clause = {
                "operator": "And",  # Change to "Or" if any condition should be true
                "operands": operands
            }
        else:
            if isinstance(field_types, list):
                field_types = field_types[0]

# The following check to see if 'field_types' is list and if so, set to single type was added because 
# when a non-list value for 'field' is passed in to method 'get_filtered_data', the value for field_types 
# passed into this method is a list of lists. This also applies to This still needs to be troubleshot.
# for example:
# When x = get_filtered_data(client, field... , 
# where (not isinstance(field, list) and isinstance(field, (str, int, float, bool))) = True 
# then field_types at this point in the code will be a list, isinstance(field, list) = True 

                if isinstance(field_types, list):
                    field_types = field_types[0]  

            if isinstance(fields, list):
                fields = fields[0]    
                         
            type_parameter = self._get_type_parameter_from_type(field_types)
            where_clause = {
                "path": [fields],
                "operator": "Equal",
                type_parameter: values
            }

        return where_clause


    def _get_type_parameter_from_type(self,field_type):
        type_mapping = {
            "int": "valueInt",
            "number": "valueNumber",
            "boolean": "valueBoolean",
            "string": "valueString",
            "text": "valueText",
            "date": "valueDate", #formatted as RFC3339
            # Add other type mappings if needed
        }

        if field_type in type_mapping:
            return type_mapping[field_type]
        else:
            raise ValueError(f"Unsupported field type: {field_type}")


    def get_metadata_fields(self, client, property='name',docs_index_name=None):
        """
        Lists all field names in the specified Weaviate index.

        Parameters:
        - docs_index_name: The index name for documents in Weaviate (optional).
        
        Returns:
        - A list of field names.
        """
        docs_index_name = self._check_docs_index_name(docs_index_name)

        # Retrieve the schema for the specified index
        class_schema = client.schema.get(docs_index_name)
        
        if not class_schema:
            print(f"No schema found for index '{docs_index_name}'.")
            return None

        # Check if property is a list
        if isinstance(property, list):
            # If property is a list, extract the corresponding values for each property
            results = [{prop_name: prop.get(prop_name, None) for prop_name in property} for prop in class_schema['properties']]
        else:
            # If property is a single string, extract the corresponding values for that property
            results = [prop.get(property, None) for prop in class_schema['properties']]

        if not results:
            print(f"No fields found in the index '{docs_index_name}'.")
            return None
        else:
            return results
        
    def _check_valid_fields(self, client, field_names,docs_index_name=None):
        if docs_index_name is None:
            docs_index_name = self.docs_index_name

        if isinstance(field_names, str):
            field_names = [field_names]

        count = 0

        valid_field_names = []
        valid_field_types = []
        if 'id' in field_names:
            field_names.remove('id')
            valid_field_names.append(ID_FIELD_NAME)
            count += 1
        if 'vector' in field_names:
            field_names.remove('vector')
            valid_field_names.append(VECTOR_FIELD_NAME)
            count += 1

        # Get available field names from the vectorstore
        aval_field_info = self.get_metadata_fields(client, property=['name', 'dataType'])
        aval_field_names = [item['name'] for item in aval_field_info]
        aval_field_names_dataType = [item['dataType'] for item in aval_field_info]

        invalid_field_names = []
        # Ensure field_names is a list
        if isinstance(field_names, str):
            if field_names not in aval_field_names and count==0:
                raise ValueError(f"""Field {field_names} is not a valid field name for index {docs_index_name}""")
            else:
                valid_field_names = field_names
                valid_field_types = aval_field_names_dataType
        else:
            # Use a list comprehension to filter and extend both lists accordingly
            valid_fields = [(field, aval_field_names_dataType[aval_field_names.index(field)]) for field in field_names if field in aval_field_names]

            # Unpack the filtered fields into valid_field_names and valid_field_types
            valid_field_names.extend([field for field, _ in valid_fields])
            valid_field_types.extend([ftype for _, ftype in valid_fields])
            
            if len(field_names) != len(valid_field_names) - count:
                invalid_field_names = [field for field in field_names if field not in aval_field_names]

        if invalid_field_names:
            print(f"Invalid field names removed: {invalid_field_names}")

        return valid_field_names, valid_field_types

    def get_data(self, client, field_names=None, page_size=100, offset=0):
        docs_index_name = self.docs_index_name

        if field_names:
            field_names, _ = self._check_valid_fields(client, field_names, docs_index_name)
        else:  # get all fields when field_names is not provided
            field_names =  [ID_FIELD_NAME, VECTOR_FIELD_NAME]
            field_names.extend(self.get_metadata_fields(client))

        all_data = []
        # Loop to paginate through all results
        while True:
            result = client.query.get(
                docs_index_name,
                field_names
            ).with_limit(page_size).with_offset(offset).do()

            data = result["data"]["Get"][docs_index_name]

            if not data:
                break

            all_data.extend(data)
            offset += page_size

        return self._format_id_vector_data(all_data)

    def get_all_data(self, client, page_size=100, offset=0):
        return self.get_data(client, None, page_size, offset)
    
    def _format_id_vector_data(self, data, keys=['vector', 'id']):
        if data:
            if keys:
                for item in data:
                    for key in keys:
                        if "_additional" in item and key in item["_additional"]:
                            item[key] = item["_additional"][key]
                            del item["_additional"][key]  # Remove the old key
                            if not item["_additional"]:  # Remove empty _additional key if it's now empty
                                del item["_additional"]
        return data

    def get_indexes(self, record_man_url=None, docs_index_name=None):
        docs_index_name = self._check_docs_index_name(docs_index_name)
        if docs_index_name != self.docs_index_name:
            raise ValueError(f"""
record_manager has already been initialized using docs_index_name = {self.docs_index_name}. RecordManager_Util Object can only have one record manager.
If you would like to initialize record manager using docs_index_name = {docs_index_name}, you must instantiate a new RecordManager_Util class object with desired docs_index_name.\
""")
            
        record_man_url = self._check_record_man_url(record_man_url)
        if record_man_url != self.record_man_url:
            raise ValueError(f"""
record_manager has already been initialized using record_man_url = {self.record_man_url}. RecordManager_Util Object can only have one record manager.
If you would like to initialize record manager using record_man_url = {record_man_url}, you must instantiate a new RecordManager_Util class object with desired record_man_url.\
""")
        else:
            self.init_record_manager(record_man_url, docs_index_name)

        # Create a session
        session = self.record_manager.Session()

        try:
            # Query to get all unique namespaces
            result = session.query(UpsertionRecord.namespace).distinct().all()
            namespaces = [row[0] for row in result]
            
            print("Current indexes managed by the record manager:")
            namespace_list = []
            for namespace in namespaces:
                # Strip the "weaviate/" prefix if present
                index_name = namespace.split("/", 1)[-1]
                namespace_list.append(index_name)
                # print(index_name)
        except Exception as e:
            print("failed to get indexes from Weaviate")
        finally:
            session.close()
            return namespace_list

    def delete_docs(self, client, docs_index_name=None, record_man_url=None):
        docs_index_name = self._check_docs_index_name(docs_index_name)
        record_man_url = self._check_record_man_url(record_man_url)

        # Initialize the ExtendedSQLRecordManager
        record_manager = self.init_record_manager(record_man_url, docs_index_name)

        # List all keys in the namespace
        keys = record_manager.list_keys()

        if not keys:
            print(f"No keys found in the namespace {docs_index_name}.")
        else:
            # Delete keys using the record manager
            record_manager.delete_keys(keys)
            print(f"All keys in the namespace '{docs_index_name}' have been deleted from the record manager.")

        # Define a batch size for deletion to avoid issues with large datasets
        batch_size = 100

        # Retrieve and delete all object IDs in the index in batches
        while True:
            response = client.query.get(docs_index_name).with_additional("id").do()
            if 'data' in response and docs_index_name in response['data']:
                objects = response['data'][docs_index_name]
                if not objects:
                    break

                for obj in objects:
                    object_id = obj['id']
                    client.data_object.delete(object_id)

                print(f"Batch of {len(objects)} objects deleted from Weaviate index '{docs_index_name}'.")
            else:
                print(f"No more data found in Weaviate index '{docs_index_name}'.")
                break

        print(f"All data in Weaviate index '{docs_index_name}' has been deleted.")

    def test_postgresql_conn(self, record_man_url=None):
        record_man_url = self._check_record_man_url(record_man_url)
        load_dotenv()
        try:
            # Create an SQLAlchemy engine
            engine = create_engine(record_man_url)
            with engine.connect() as connection:
                return connection.execute(text("SELECT version();"))
                                
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            return None
        
    def set_field_values_by_id(self, client, ids, field, value):
        """
        Update the specified field with the given value(s) for the provided list of ids.
        
        Parameters:
        - client: The Weaviate client instance.
        - ids: The list of ids to update.
        - field: The field to update.
        - value: The value(s) to set. Can be a single value or a list of values.
        
        Returns:
        - list: The list of ids that were updated.
        """
        docs_index_name = self.docs_index_name
        try:
            if ids:
                if not isinstance(ids, list):
                    ids = [ids]

                if isinstance(value, list):
                    if len(value) != len(ids):
                        raise ValueError("The length of values must match the length of ids.")
                else:
                    value = [value] * len(ids)

                for id, val in zip(ids, value):
                    if not isinstance(val, numbers.Number):
                        val = json.dumps(val)[1:-1]
                    if isinstance(val, np.float32):
                        val = float(val)


                    client.data_object.update(
                        data_object={field: val},
                        class_name=docs_index_name,
                        uuid=id
                    )
                return ids
            else:
                print("No elements found that match the filtered criteria")
                return None
        except Exception as e:
            print(f"An error occurred while updating: {e}")

    def add_new_field(self, client, field_name, field_type, default_value, tokenization=None):
        """
        Adds a new field to an existing class in Weaviate and sets a default value for the field.

        Parameters:
        - field_name: Name of the new field to add.
        - field_type: Data type of the new field (e.g., "string", "int").
        - tokenization: Tokenization type for the new field (optional).
        - default_value: Default value to set for the new field (optional).
        """
        docs_index_name = self.docs_index_name

        # Get the current schema for the class
        schema = self.get_class_schema(client, docs_index_name)
        if not schema:
            raise ValueError(f"Class '{docs_index_name}' does not exist in the schema.")

        # Check if the field already exists
        if any(prop['name'] == field_name for prop in schema['properties']):
            raise ValueError(f"Field '{field_name}' already exists in class '{docs_index_name}'.")

        # Define the new property
        new_property = {
            "name": field_name,
            "dataType": [field_type]
        }
        if tokenization:
            new_property["tokenization"] = tokenization

        # Add the new property to the class schema
        client.schema.property.create(docs_index_name, new_property)
        print(f"Field '{field_name}' added to class '{docs_index_name}' successfully.")

        self._update_all_field_values(client, field_name, default_value)

    # Fetch all instances of the class to update them with the default value
    def _update_all_field_values(self, client, field_name, value):
        docs_index_name = self.docs_index_name
        query = f'{{ Get {{ {docs_index_name} {{ _additional {{ id }} }} }} }}'
        results = client.query.raw(query)['data']['Get'][docs_index_name]
        
        # Update each instance with the default value for the new field
        ids=[]
        for instance in results:
            ids.append(instance['_additional']['id'])

        self.set_field_values_by_id(client, ids, field_name, value)

    def get_class_schema(self, client, docs_index_name=None):
        docs_index_name = self._check_docs_index_name(docs_index_name)
        try:
            return client.schema.get(docs_index_name)
        except Exception as e:
            print(f"Class '{docs_index_name}' does not exist in the schema.")
            return None
        
    def get_class_names(self, client):
        """
        Returns a list of all class names in the Weaviate database.

        Returns:
        - A list of class names.
        """
        schema = client.schema.get()
        class_names = [cls['class'] for cls in schema['classes']]
        return class_names

    def check_weaviate_schema_exist(self, client, docs_index_name=None):
        docs_index_name = self._check_docs_index_name(docs_index_name)
        try:
            class_schema = self.get_class_schema(client,docs_index_name)
            print(f"Schema for class '{docs_index_name}' exists:")
            print(class_schema)
            return True
        except Exception as e:
            print(f"Class '{docs_index_name}' does not exist in the schema.")
            return False

    def print_all_weaviate_schemas(self, client):
        schema = client.schema.get()
        pprint.pprint(schema)

    def create_weaviate_schema(self, client, docs_index_name, key, elements, tokenization_overrides, logger=None):
        docs_index_name = self._check_docs_index_name(docs_index_name)
        try:
            schema = client.schema.get()
            existing_class = next((cls for cls in schema['classes'] if cls['class'] == docs_index_name), None)

            if existing_class:
                existing_properties = {prop['name']: prop for prop in existing_class['properties']}
            else:
                existing_properties = {}

            other_keys = {k: determine_data_type(v) for k, v in elements[0].metadata.items()}

            # Define properties based on the input keys and tokenization_overrides
            properties = []
            key_name_list = []
            for key, data_type in other_keys.items():
                if key in tokenization_overrides:
                    override = tokenization_overrides[key]
                    if isinstance(override, tuple):
                        data_type, tokenization = override
                        if data_type == None or tokenization == None:
                            continue
                    else:
                        tokenization = override
                        data_type = data_type
                else:
                    tokenization = "word" if data_type in ["text", "text[]"] else None

                properties.append({
                    "name": key,
                    "dataType": ["text"] if data_type is None else [data_type],
                    "description": f"This property was generated by Weaviate's auto-schema feature",
                    "indexFilterable": True,
                    "indexSearchable": data_type in ["text", "text[]"],
                    "tokenization": tokenization
                })
                key_name_list.append(key)

            if existing_class:
                # Remove properties not present in the new schema
                schema_keys = [prop for prop in properties if prop['name'] in other_keys]
                schema_key_name_list = []
                not_schema_key_name_list = []
                for schema_key in schema_keys:
                    if schema_key.get('name') in key_name_list:
                        schema_key_name_list.append(schema_key.get('name'))
                    else:
                        not_schema_key_name_list.append(schema_key.get('name'))
                
                if not_schema_key_name_list:
                    logger.error(f"in'create_weaviate_schema, the following keys found in elements' metadata are not found in the schema for class {docs_index_name}: {not_schema_key_name_list}")

                return schema_key_name_list
            else:
                # Define the schema with optimized settings for best search performance
                class_obj = {
                    "class": docs_index_name,
                    "description": "Documents for optimized search performance",
                    "properties": properties,
                    "invertedIndexConfig": {
                        "bm25": {"b": 0.75, "k1": 2.0},  # Adjusted for better term frequency impact
                        "cleanupIntervalSeconds": 60,
                        "stopwords": {"additions": None, "preset": "en", "removals": None}
                    },
                    "multiTenancyConfig": {"enabled": False},
                    "replicationConfig": {"factor": 1},
                    "shardingConfig": {
                        "actualCount": 1,
                        "actualVirtualCount": 128,
                        "desiredCount": 1,
                        "desiredVirtualCount": 128,
                        "function": "murmur3",
                        "key": "_id",
                        "strategy": "hash",
                        "virtualPerPhysical": 128
                    },
                    "vectorIndexConfig": {
                        "bq": {"enabled": False},
                        "cleanupIntervalSeconds": 300,
                        "distance": "cosine",
                        "dynamicEfFactor": 10,
                        "dynamicEfMax": 1000,
                        "dynamicEfMin": 500,
                        "ef": 1000,
                        "efConstruction": 200,
                        "flatSearchCutoff": 0,# Disable switching to flat search for exhaustive search
                        "maxConnections": 128,
                        "pq": {
                            "bitCompression": False,
                            "centroids": 256,
                            "enabled": False,
                            "encoder": {"distribution": "log-normal", "type": "kmeans"},
                            "segments": 0,
                            "trainingLimit": 100000
                        },
                        "skip": False,
                        "vectorCacheMaxObjects": 1000000000000
                    },
                    "vectorIndexType": "hnsw",
                    "vectorizer": "none"  # external vectorizer
                }

                # Create the class in Weaviate
                client.schema.create_class(class_obj)
                logger.info(f"Weaviate schema created for class name: {docs_index_name}.")
                return key_name_list
        except Exception as e:
            logger.error(f"An error occurred in create_weaviate_schema: {e}")

    def _print_weaviate_index_details(self, client, docs_index_name=None):
        docs_index_name = self._check_docs_index_name(docs_index_name)

        # Retrieve the schema for the specified index
        schema = client.schema.get()
        
        # Find the class corresponding to the specified index
        class_schema = next((cls for cls in schema['classes'] if cls['class'] == docs_index_name), None)
        
        if not class_schema:
            print(f"No schema found for index '{docs_index_name}'.")
            return

        # List all field names in the class schema
        field_names = [prop['name'] for prop in class_schema['properties']]
        
        if not field_names:
            print(f"No fields found in the index '{docs_index_name}'.")
        else:
            print(f"Fields in the index '{docs_index_name}':")
            for field in field_names:
                print(field)
        
        # Debugging: Print the entire properties to understand their structure
        print(f"Properties in the index '{docs_index_name}':")
        for prop in class_schema['properties']:
            print(prop)

        # List all field names that have embeddings
        embedding_fields = [prop['name'] for prop in class_schema['properties'] if prop.get('vectorize', False) or 'vectorize' in prop]
        
        if not embedding_fields:
            print(f"No fields with embeddings found in the index '{docs_index_name}'.")
        else:
            print(f"Fields with embeddings in the index '{docs_index_name}':")
            for field in embedding_fields:
                print(field)

    def _check_docs_index_name(self, docs_index_name):
        if not docs_index_name:
            docs_index_name = self.docs_index_name or os.getenv('WEAVIATE_DOCS_INDEX_NAME')
            if not docs_index_name:
                raise ValueError("docs_index_name must be provided or set in the environment variables.")
        return docs_index_name
    
    def _check_record_man_url(self, record_man_url):
        if not record_man_url:
            record_man_url = self.record_man_url or os.getenv('RECORD_MANAGER_DB_URL')
            if not record_man_url:
                raise ValueError("record_man_url must be provided or set in the environment variables.")
        return record_man_url

```

```python
# weaviate_recordmanager_utils\TestPOSTgreSQL.py

from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text

# Example function to test the connection
def test_postgresql_conn(db_url=None):# Load environment variables from .env file
    if not db_url:
        db_url = os.getenv('RECORD_MANAGER_DB_URL')
        if not db_url:
            raise ValueError("db_url must be provided or set in the environment variables.")
    load_dotenv()
    try:
        # Create an SQLAlchemy engine
        engine = create_engine(db_url)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            for row in result:
                print(row)
    except Exception as e:
        print(f"Error connecting to the database: {e}")



if __name__ == "__main__":
    test_postgresql_conn()
```

```python
# weaviate_recordmanager_utils\weaviate_client_singleton.py

import weaviate
from weaviate.auth import AuthApiKey
import os
from dotenv import load_dotenv
import threading

# Load environment variables from the .env file
load_dotenv()

# Retrieve the Weaviate URL and API key from environment variables
WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")

class WeaviateClientManager:
    """
    Singleton class to manage the Weaviate client instance.
    
    Ensures that only one instance of the Weaviate client is created and reused
    across the entire application. Uses double-checked locking to ensure thread safety.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """
        Control the creation of a single instance of the class.
        
        If an instance doesn't already exist, acquire a lock and check again to 
        ensure that no other thread has created an instance in the meantime.
        
        Returns:
            WeaviateClientManager: The singleton instance of the class.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # Double-checked locking
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, url: str, key: str):
        """
        Initialize the Weaviate client.
        
        This method initializes the Weaviate client only if it hasn't been
        initialized already. This ensures that the client is created only once.
        
        Args:
            url (str): The URL of the Weaviate server.
            key (str): The API key for authenticating with the Weaviate server.
        """
        if not hasattr(self, 'client'):
            self.client = weaviate.Client(
                url=url, 
                auth_client_secret=AuthApiKey(api_key=key)
            )

    def get_client(self):
        """
        Get the Weaviate client instance.
        
        Returns:
            weaviate.Client: The Weaviate client instance.
        """
        return self.client

# Instantiate the manager with the Weaviate server URL and API key
client_manager = WeaviateClientManager(WEAVIATE_URL, WEAVIATE_API_KEY)

def get_weaviate_client():
    """
    Get the Weaviate client instance from the client manager.
    
    This function acts as a dependency injection provider, making it easy to 
    use the Weaviate client in various parts of the application.
    
    Returns:
        weaviate.Client: The Weaviate client instance.
    """
    return client_manager.get_client()

```

```python
# weaviate_recordmanager_utils\weaviate_V4_client_singleton.py


## This work with Weaviate CLient V4


import weaviate
from weaviate.auth import AuthApiKey
from weaviate.classes.init import Auth
import os
from dotenv import load_dotenv
import threading

# Load environment variables from the .env file
load_dotenv()

# Retrieve the Weaviate URL and API key from environment variables
# WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")

class WeaviateClientManager:
    """
    Singleton class to manage the Weaviate client instance.
    
    Ensures that only one instance of the Weaviate client is created and reused
    across the entire application. Uses double-checked locking to ensure thread safety.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """
        Control the creation of a single instance of the class.
        
        If an instance doesn't already exist, acquire a lock and check again to 
        ensure that no other thread has created an instance in the meantime.
        
        Returns:
            WeaviateClientManager: The singleton instance of the class.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # Double-checked locking
                    cls._instance = super().__new__(cls)
        return cls._instance

    # def __init__(self, url: str, key: str):
    def __init__(self, key: str):
        """
        Initialize the Weaviate client.
        
        This method initializes the Weaviate client only if it hasn't been
        initialized already. This ensures that the client is created only once.
        
        Args:
            url (str): The URL of the Weaviate server.
            key (str): The API key for authenticating with the Weaviate server.
        """
        # if not hasattr(self, 'client'):
        #     self.client = weaviate.Client(
        #         url=url, 
        #         auth_client_secret=AuthApiKey(api_key=key)
        #     )

        if not hasattr(self, 'client'):
            self.client = weaviate.connect_to_local(
                host='localhost',
                port=8080,
                grpc_port=50051,
                auth_credentials=Auth.api_key(key)
            ) 

    def get_client(self):
        """
        Get the Weaviate client instance.
        
        Returns:
            weaviate.Client: The Weaviate client instance.
        """
        return self.client
    

    def close_client(self):
        """
        Close the Weaviate client connection.
        """
        if hasattr(self, 'client') and self.client is not None:
            self.client.close()
            self.client = None

# Instantiate the manager with the Weaviate server URL and API key
# client_manager = WeaviateClientManager(WEAVIATE_URL, WEAVIATE_API_KEY)
client_manager = WeaviateClientManager(WEAVIATE_API_KEY)

def get_weaviate_client():
    """
    Get the Weaviate client instance from the client manager.
    
    This function acts as a dependency injection provider, making it easy to 
    use the Weaviate client in various parts of the application.
    
    Returns:
        weaviate.Client: The Weaviate client instance.
    """
    return client_manager.get_client()

def close_weaviate_client():
    return client_manager.close_client()
```

```python
# weaviate_recordmanager_utils\weaviate_v4_recordmanager_utils.py

import os
import json
import weaviate
from contextlib import contextmanager
from weaviate.classes.init import Auth
from weaviate.classes.query import MetadataQuery, Filter, Sort
from dotenv import load_dotenv
# from .ExtendedSQLRecordManager import ExtendedSQLRecordManager, UpsertionRecord
from sqlalchemy import create_engine, text
import pprint
import numpy as np
import numbers
from weaviate_recordmanager_utils.weaviate_V4_client_singleton import get_weaviate_client as singleton_weaviate_client
from weaviate_recordmanager_utils.weaviate_V4_client_singleton import close_weaviate_client
from weaviate.classes.config import Property, DataType
import weaviate.classes as wvc
from weaviate.types import UUID
from weaviate.exceptions import UnexpectedStatusCodeError
from typing import Optional

import logging
logger = logging.getLogger(__name__)

ID_FIELD_NAME = "_additional { id }"
VECTOR_FIELD_NAME = "_additional { vector }"

def determine_data_type(value):
    if isinstance(value, list):
        return "text[]"
    elif isinstance(value, int):
        return "int"
    elif isinstance(value, float):
        return "number"
    elif value is None:
        return "text"
    else:
        return "text"
    

DATATYPES = {
    'text': DataType.TEXT,               # Text data type
    'text[]': DataType.TEXT_ARRAY,       # Text array data type
    'int': DataType.INT,                 # Integer data type
    'int[]': DataType.INT_ARRAY,         # Integer array data type
    'boolean': DataType.BOOL,            # Boolean data type
    'boolean[]': DataType.BOOL_ARRAY,    # Boolean array data type
    'number': DataType.NUMBER,           # Number data type
    'number[]': DataType.NUMBER_ARRAY,   # Number array data type
    'date': DataType.DATE,               # Date data type
    'date[]': DataType.DATE_ARRAY,       # Date array data type
    'uuid': DataType.UUID,               # UUID data type
    'uuid[]': DataType.UUID_ARRAY,       # UUID array data type
    'geoCoordinates': DataType.GEO_COORDINATES,  # Geo coordinates data type
    'blob': DataType.BLOB,               # Blob data type
    'phoneNumber': DataType.PHONE_NUMBER, # Phone number data type
    'object': DataType.OBJECT,           # Object data type
    'object[]': DataType.OBJECT_ARRAY    # Object array data type
}

class RecordManager_Util:
    def __init__(self, weaviate_url=None, weaviate_api_key=None, docs_index_name=None, record_man_url=None, singleton=False, text_key='page_content'):
        """
        Initializes the RecordManager_Util class.

        Parameters:
        - weaviate_url: URL for Weaviate instance.
        - weaviate_api_key: API key for Weaviate.
        - docs_index_name: The index name for documents in Weaviate (optional).
        - record_man_url: URL for the record manager (optional).
        - text_key: The key to use for text content (optional).
        """
        load_dotenv()  # Load environment variables

        self.text_key = text_key
        self.docs_index_name = docs_index_name
        self.record_man_url = record_man_url or os.getenv('RECORD_MANAGER_DB_URL')
        self.record_manager = None

        if docs_index_name and record_man_url:
            self.record_manager = self.init_record_manager()

        self.weaviate_url = weaviate_url or os.getenv('WEAVIATE_URL')
        self.weaviate_api_key = weaviate_api_key or os.getenv('WEAVIATE_API_KEY')

        # Parse the Weaviate URL to extract host and port
        self.host, self.port = self._parse_weaviate_url(self.weaviate_url)

        self.client = self.get_singleton_weaviate_client()

        self.collection_config = self.get_collection_def()
        self.properties = self.get_properties()

    def _parse_weaviate_url(self, weaviate_url):
        """
        Helper method to parse the Weaviate URL to extract host and port.

        Parameters:
        - weaviate_url: The URL for the Weaviate instance.

        Returns:
        - host: The host part of the URL.
        - port: The port part of the URL.
        """
        if weaviate_url:
            host = weaviate_url.split("//")[-1].split(":")[0]
            port = int(weaviate_url.split(":")[-1])
            return host, port
        return None, None

    def get_singleton_weaviate_client(self):
        return singleton_weaviate_client()
    
    def is_client_ready(self):
        return self.client.is_ready()
    
    def close_weaviate_client(self):
        return close_weaviate_client()

    @contextmanager
    def get_weaviate_client(self, weaviate_url=None, weaviate_api_key=None):
        if not self.weaviate_url or not self.weaviate_api_key:
            if not weaviate_url or not weaviate_api_key:
                raise ValueError("Both weaviate_url and weaviate_api_key must be provided.")
            else:
                self.weaviate_url = weaviate_url
                self.weaviate_api_key = weaviate_api_key
                self.host, self.port = self._parse_weaviate_url(weaviate_url)
        elif weaviate_url or weaviate_api_key:
            raise ValueError("weaviate_url and weaviate_api_key have already been set and cannot be changed.")

        # Create auth credentials
        auth_credentials = Auth.api_key(self.weaviate_api_key)

        # Connect to the Weaviate instance using v4 client
        client = weaviate.connect_to_local(
            host=self.host,
            port=self.port,
            grpc_port=50051,  # Default gRPC port; adjust if necessary
            auth_credentials=auth_credentials
        )

        try:
            yield client
        finally:
            client.close()


    def get_collection(self):
        return self.client.collections.get(self.docs_index_name)

    def get_collection_def(self):
        collection = self.client.collections.get(self.docs_index_name)
        return collection.config.get()
    
    def get_collection_schema(self):
        schema = self.collection_config.to_dict()
        return schema['properties']

    def get_all_collection_names(self):
        return self.client.collections.list_all(simple=False)
    
    def get_properties(self):
        collection_config = self.collection_config
        docs_index_name = self.docs_index_name

        if not collection_config:
            print(f"No schema found for index '{docs_index_name}'.")
            return None

        # Extract all property names and types
        properties = []
        for prop in collection_config.properties:
            properties.append({
                'name': prop.name,
                'data_type': prop.data_type,
                'description': getattr(prop, 'description', None),
                'index_filterable': getattr(prop, 'index_filterable', None),
                'index_range_filters': getattr(prop, 'index_range_filters', None),
                'index_searchable': getattr(prop, 'index_searchable', None),
                'nested_properties': getattr(prop, 'nested_properties', None),
                'tokenization': getattr(prop, 'tokenization', None),
                'vectorizer_config': getattr(prop, 'vectorizer_config', None),
                'vectorizer': getattr(prop, 'vectorizer', None),
            })

        self.properties = properties
        return self.properties

    # get_metadata_fields
    def get_property_keys(self, property_key):
        """
        Returns a list of values for the specified property key from the properties list.

        Parameters:
        - property_key: A string containing one of the property keys (e.g., 'name', 'data_type', 'description').

        Returns:
        - A list of values corresponding to the property key.
        """
        if not hasattr(self, 'properties') or not self.properties:
            print("Properties list is empty or undefined.")
            return None
        
        # Ensure the property_key is valid
        if not isinstance(property_key, str):
            raise ValueError("property_key must be a string.")

        # Extract values for the given property_key
        values = [prop[property_key] for prop in self.properties if property_key in prop]
        
        if not values:
            print(f"No values found for property '{property_key}'.")
            return None
        
        return values

    def get_all_field_values(self):
        all_property_names = self.get_property_keys('name')
        return self.get_field_values(field = all_property_names)

    def get_field_values(self, fields, property_key='name'):
        """
        Retrieves the values for specified property keys from all objects in the collection.

        Parameters:
        - fields: A list of strings representing the property keys.
        - property_key: A string representing the property key used for validation (optional).

        Returns:
        - A list of dictionaries, where each dictionary contains field-value pairs for the specified property keys.
        """
        if not isinstance(fields, list):
            fields = [fields]

        property_values = []



        if 'vector' in fields:
            vector = True
        else:
            vector = False

        for item in self.iterate_over_entire_collection(include_vector=vector):
            item_values = {}

            for field in fields:
                if field == 'uuid':
                    item_values[field] = str(item.uuid)

                elif field == 'vector':
                    item_values[field] = item.vector.get('default')

                else:
                    # Check if the field is in self.get_property_keys(property_key)
                    if not hasattr(self, 'properties') or field not in self.get_property_keys(property_key):
                        raise ValueError(f"'{field}' is not a valid property key.")

                    # Append the value of the property to the dictionary if it exists
                    if field in item.properties:
                        item_values[field] = item.properties[field]
                    else:
                        item_values[field] = None  # Handle cases where the property is missing

            property_values.append(item_values)

        return property_values

    def iterate_over_entire_collection(
        self,
        include_vector=False,
        return_metadata=None,
        return_properties=None,
        return_references=None,
        after=None,
    ):

        return self.get_collection().iterator(
            include_vector=include_vector,
            return_metadata=return_metadata,
            return_properties=return_properties,
            return_references=return_references,
            after=after,
            )


    def _check_valid_fields(self, field_names):
        docs_index_name = self.docs_index_name

        if isinstance(field_names, str):
            field_names = [field_names]

        count = 0

        valid_field_names = []
        valid_field_types = []
        if 'uuid' in field_names:
            field_names.remove('uuid')
            valid_field_names.append('uuid')
            valid_field_types.append(None)
            count += 1
        if 'vector' in field_names:
            field_names.remove('vector')
            valid_field_names.append('vector')
            valid_field_types.append(None)
            count += 1

        aval_field_names = self.get_property_keys('name')
        aval_field_types = self.get_property_keys('data_type')


        invalid_field_names = []
        # Ensure field_names is a list
        if isinstance(field_names, str):
            if field_names not in aval_field_names and count==0:
                raise ValueError(f"""Field {field_names} is not a valid field name for index {docs_index_name}""")
            else:
                valid_field_names = field_names
                valid_field_types = aval_field_types
        else:
            # Use a list comprehension to filter and extend both lists accordingly
            valid_fields = [(field, aval_field_types[aval_field_names.index(field)]) for field in field_names if field in aval_field_names]

            # Unpack the filtered fields into valid_field_names and valid_field_types
            valid_field_names.extend([field for field, _ in valid_fields])
            valid_field_types.extend([ftype for _, ftype in valid_fields])
            
            if len(field_names) != len(valid_field_names) - count:
                invalid_field_names = [field for field in field_names if field not in aval_field_names]

        if invalid_field_names:
            print(f"Invalid field names removed: {invalid_field_names}")

        return valid_field_names, valid_field_types
    
    def get_data_type(self, data_type_str):
        """
        Looks up the DataType enum corresponding to the provided string.

        Parameters:
        - data_type_str: A string representing the data type (e.g., 'text', 'int', etc.)

        Returns:
        - The corresponding DataType enum value if found, or None if not found.
        """
        data_type_enum = DATATYPES.get(data_type_str)

        if data_type_enum:
            print(f"The DataType for '{data_type_str}' is {data_type_enum}")
        else:
            print(f"No DataType found for '{data_type_str}'")

        return data_type_enum

    def set_field_values_by_ids(self, ids, field_name, value):
        collection = self.get_collection()
        if not isinstance(ids, list):
            ids = [ids]
        if not isinstance(value, list):
            value = [value]

        if len(ids)> 1:
            if len(value) == 1:
                value = [value[0] for _ in ids]
            elif len(value) != len(ids):
                raise ValueError(f"""
'values' must be either a single value or a list of values where len(value) == len(ids) \
'values' is length {len(value)} but 'ids' is length {len(ids)}""")


        for uuid, v in zip(ids,value):
            try:
                logger.info(f"Attempting to update UUID: {uuid} with field: {field_name} and value: {v}")
                collection.data.update(
                    uuid=uuid,
                    properties={
                        field_name: v,
                    }
                )
                logger.info(f"Successfully updated UUID: {uuid}")



            except UnexpectedStatusCodeError as e:
                if "404" in str(e):  # Checking if the error is a 404
                    logger.error(f"UUID {uuid} not found: {e}")
                else:
                    logger.error(f"Failed to update UUID: {uuid} due to an unexpected error: {e}")
                    raise e  # Re-raise the exception for other status codes

        return




    def set_field_values_for_all_ids(self, field_name,value):
        ids_values = []
        ids = self.get_field_values('uuid')
        if not isinstance(ids, list):
            ids = [ids]
        

        if isinstance(ids[0], dict):
            for dictionary in self.get_field_values('uuid'):
                ids_values.extend(dictionary.values())
        else:
            ids_values = ids
        return self.set_field_values_by_ids(ids_values, field_name,value)

    def add_new_field(self, field_name, field_type, default_value, tokenization=None):

        collection = self.get_collection()

        # Check if the field already exists
        if any(prop== field_name for prop in self.get_property_keys('name')):
            raise ValueError(f"Field '{field_name}' already exists in class '{self.docs_index_name}'.")

        
        collection.config.add_property(
            Property(
                name=field_name,
                data_type=self.get_data_type(field_type)
            )
        )

        return self.set_field_values_for_all_ids(field_name,default_value)

    def get_last_update_to_collection(self):

        collection = self.get_collection()

        response = collection.query.fetch_objects(
            return_metadata=wvc.query.MetadataQuery(last_update_time=True),
            sort=Sort.by_property(name="_lastUpdateTimeUnix", ascending=False),
            limit=1
        )
        
        creation_time = response.objects[0].metadata.last_update_time.isoformat()

        return creation_time # example format: '2024-08-12T18:24:21.725000+00:00'

    def _validate_and_convert_values(self, field_types, values):
        # Conversion and validation functions
        def to_text(val): return str(val)
        def to_int(val): return int(val)
        def to_bool(val): return val.lower() in ['true', '1', 'yes'] if isinstance(val, str) else bool(val)
        def to_number(val): return float(val)
        def to_date(val): return val  # Assuming date validation happens elsewhere
        def to_uuid(val): return val  # Assuming UUID validation happens elsewhere
        def to_geo_coordinates(val): return val  # Assuming GeoCoordinates validation happens elsewhere
        def to_blob(val): return val  # Assuming Blob validation happens elsewhere
        def to_phone_number(val): return val  # Assuming PhoneNumber validation happens elsewhere
        def to_object(val): return val  # Assuming Object validation happens elsewhere

        # Map DataType to corresponding validation/conversion function
        validation_functions = {
            DataType.TEXT: to_text,
            DataType.TEXT_ARRAY: lambda val: [to_text(v) for v in val],
            DataType.INT: to_int,
            DataType.INT_ARRAY: lambda val: [to_int(v) for v in val],
            DataType.BOOL: to_bool,
            DataType.BOOL_ARRAY: lambda val: [to_bool(v) for v in val],
            DataType.NUMBER: to_number,
            DataType.NUMBER_ARRAY: lambda val: [to_number(v) for v in val],
            DataType.DATE: to_date,
            DataType.DATE_ARRAY: lambda val: [to_date(v) for v in val],
            DataType.UUID: to_uuid,
            DataType.UUID_ARRAY: lambda val: [to_uuid(v) for v in val],
            DataType.GEO_COORDINATES: to_geo_coordinates,
            DataType.BLOB: to_blob,
            DataType.PHONE_NUMBER: to_phone_number,
            DataType.OBJECT: to_object,
            DataType.OBJECT_ARRAY: lambda val: [to_object(v) for v in val]
        }

        # Ensure field_types and values are lists
        if not isinstance(field_types, list):
            field_types = [field_types]
        if not isinstance(values, list):
            values = [values]

        # Ensure the lists have the same length
        if len(field_types) != len(values):
            raise ValueError("The number of fields must match the number of values")

        # Validate and convert each value based on the corresponding field_type
        validated_values = []
        for field_type, value in zip(field_types, values):
            if field_type in validation_functions:
                try:
                    validated_value = validation_functions[field_type](value)
                    validated_values.append(validated_value)
                except Exception as e:
                    raise ValueError(f"Invalid value '{value}' for type {field_type}: {str(e)}")
            else:
                raise ValueError(f"Unsupported field type: {field_type}")

        return validated_values

    def get_filtered_data(
            self, 
            field, 
            value, 
            field_names, 
            vector=False, 
            operator=None, 
            logical_operator=None, 
            return_last_updated_time=False,
            filter_by_last_update_time=None
        ):
        docs_index_name = self.docs_index_name
        # if not isinstance(value, int) and not isinstance(value, list):
        #     value = json.dumps(value)[1:-1]

        try:
            if 'uuid' in field:
                if isinstance(field,list):
                    if len(field) != 1:
                        field.remove('uuid') 
                        field, field_type = self._check_valid_fields(field)
                        field.append('uuid')
                        field_type.append('string')
                    else:
                        field = field[0]
                        field_type = 'string'
                else:
                    field = 'uuid'
                    field_type = 'string'
            else:
                field, field_type = self._check_valid_fields(field)
                # Ensure values match the expected data types
                if field:
                    value = self._validate_and_convert_values(field_type, value)
                else:
                    return None

            if not field:
                raise ValueError(f"""Field {field} is not a valid field name for index {docs_index_name}""")
            
            # Here we need to replace 'uuid' with ID_FIELD_NAME if 'uuid' is present
            field_names, _ = self._check_valid_fields(field_names)

            if not field_names:
                raise ValueError(f"""field_names {field_names} is not a valid field name for index {docs_index_name}""")
            # Ensure id is always included in the field names

            collection = self.get_collection()
            
            offset = 0
            limit = 200
            all_results = []

            if not operator:
                operator = ['equal' for _ in field]
            elif not isinstance(operator,list):
                operator = [operator]
            if not logical_operator:
                logical_operator= "&"

            if not isinstance(value,list):
                value = [value]

            filters = self.build_filters(field, value, operator, logical_operator,filter_by_last_update_time)

            # last_id = None

            while True:
                response = collection.query.fetch_objects(
                    filters=filters,
                    limit=limit,
                    offset=offset,
                    # after=last_id,
                    include_vector=vector,
                    return_metadata=MetadataQuery(last_update_time=return_last_updated_time)
                )

                # # Cursor
                # last_id = response.objects[-1].uuid

                # Append the current batch of results to the all_results list
                all_results.extend(response.objects)  # Assuming response['objects'] contains the results

                # If the number of results fetched is less than the limit, break the loop
                if len(response.objects) < limit:
                    break

                # Increment the offset by the limit to fetch the next batch
                offset += limit

            returned_properties = []
            for o in all_results:
                # Create a new dictionary with only the desired properties
                returned_property = {prop: o.properties[prop] for prop in field_names if prop in o.properties}
                returned_property['uuid'] = str(o.uuid)
                if vector:
                    returned_property['vector'] = o.vector
                if return_last_updated_time:
                    # RFC3339 format.
                    returned_property['return_last_updated_rfc3339_time'] = o.metadata.last_update_time.isoformat()
                returned_properties.append(returned_property)

        except Exception as e:
            raise RuntimeError(f"get_filtered_data() method, defined in the RecordManager_Util Class, failed execution: {str(e)}")
            returned_properties = None

        # Format the data to include 'uuid' and 'vector' fields appropriately
        return returned_properties

    def build_filters(self, properties, values, operators, logical_operator, last_update_time=None):
        # Start with the first condition
        filter_condition = getattr(Filter.by_property(properties[0]), operators[0])(values[0])

        # Loop through the remaining properties and combine the filters
        for i in range(1, len(properties)):
            new_condition = getattr(Filter.by_property(properties[i]), operators[i])(values[i])
            
            if logical_operator == "&":
                filter_condition = filter_condition & new_condition
            elif logical_operator == "|":
                filter_condition = filter_condition | new_condition
            else:
                raise ValueError(f"Unsupported logical operator: {logical_operator}")
        
        if last_update_time:
            last_update_time_condition = Filter.by_update_time().greater_than(last_update_time)
            filter_condition = filter_condition & last_update_time_condition
           

        return filter_condition   

    def get_data_filter_by_id(self, ids):
        results = []
        collection = self.get_collection()

        # Handle a single str or UUID object
        if isinstance(ids, UUID) or isinstance(ids, str):            
            results = collection.query.fetch_object_by_id(ids)
                
        elif isinstance(ids, list) and (all(isinstance(id, UUID) for id in ids) or all(isinstance(id, str) for id in ids)):
                for id in ids:
                    result = collection.query.fetch_object_by_id(id)
                    results.append(result)
            
        # Raise an error for invalid types
        else:
            raise ValueError(f"""\
id(s) {ids} is not a valid data type. id(s) is type {type(ids)}. \
It should be either a string, a list of strings, a UUID, or a list of UUID objects.""")

        return results
        
        
        

# if __name__ == "__main__":
#     # Instantiate the class
#     weaviate_url =  os.getenv('WEAVIATE_URL')
#     weaviate_api_key = os.getenv('WEAVIATE_API_KEY')
#     collection = 'SEPs_F_T_C_W_A_V_Summaries'# 'Injected_URL3'
#     try:
#         RM= RecordManager_Util(
#             weaviate_url=weaviate_url, 
#             weaviate_api_key=weaviate_api_key,
#             docs_index_name=collection,
#             singleton=True,
#         )

        
#         # Perform operations with the client
#         print("Connected to Weaviate:", RM.is_client_ready())

#         ids = RM.get_field_values('uuid')
#         RM.set_field_values_for_all_ids('use4RAG',True)
#         # results = RM.get_filtered_data('use4RAG', True, 'text_as_html')
#         results = RM.get_filtered_data(['use4RAG','page_number'], [True, 1], ['text_as_html','page_number'])
#         RM.get_data_filter_by_id(ids[0])
#         RM.set_field_values_for_all_ids('test_this','test')
#         result = RM.get_field_values('test_this')
#         result = RM.get_field_values('uuid')
#         RM.add_new_field('test_this', 'text', 'test')
#         x, y = RM._check_valid_fields(['uuid', 'use4RAG', 'goodf'])
#         result= RM.get_field_values('use4RAG', 'name')

        
#         for r in result[:100]:
#             print(r)
#         print(len(result))
#         RM.close_weaviate_client()
#         exit()

#         value = RM.get_property_keys('name')



#         results = RM.get_property_keys('name')
        

#         for r in results:
#             print(r)

#         print('***************')

#         aval_field_types = [item['data_type'] for item in results2]
#         aval_field_names = [item['name'] for item in results2]

#         for r in aval_field_names:
#             print(r)

#         print('***************')

#         for r in aval_field_types:
#             print(r)

#     finally:
        # closer= RecordManager_Util(singleton=True)       
        # closer.close_weaviate_client()


```

```python
# weaviate_recordmanager_utils\_index.py

from __future__ import annotations

from typing import Callable, Iterable, Literal, Optional, Sequence, Union, cast

from langchain.document_loaders.base import BaseLoader
from langchain.indexes._api import (IndexingResult, _batch,
                                    _deduplicate_in_order,
                                    _get_source_id_assigner, _HashedDocument)
from langchain.indexes.base import RecordManager
from langchain.schema.document import Document
from langchain.schema.vectorstore import VectorStore


def index(
    docs_source: Union[BaseLoader, Iterable[Document]],
    record_manager: RecordManager,
    vector_store: VectorStore,
    *,
    batch_size: int = 100,
    cleanup: Literal["incremental", "full", None] = None,
    source_id_key: Union[str, Callable[[Document], str], None] = None,
    cleanup_batch_size: int = 1_000,
    force_update: bool = False,
) -> IndexingResult:
    """Index data from the loader into the vector store.

    Indexing functionality uses a manager to keep track of which documents
    are in the vector store.

    This allows us to keep track of which documents were updated, and which
    documents were deleted, which documents should be skipped.

    For the time being, documents are indexed using their hashes, and users
     are not able to specify the uid of the document.

    IMPORTANT:
       if auto_cleanup is set to True, the loader should be returning
       the entire dataset, and not just a subset of the dataset.
       Otherwise, the auto_cleanup will remove documents that it is not
       supposed to.

    Args:
        docs_source: Data loader or iterable of documents to index.
        record_manager: Timestamped set to keep track of which documents were
                         updated.
        vector_store: Vector store to index the documents into.
        batch_size: Batch size to use when indexing.
        cleanup: How to handle clean up of documents.
            - Incremental: Cleans up all documents that haven't been updated AND
                           that are associated with source ids that were seen
                           during indexing.
                           Clean up is done continuously during indexing helping
                           to minimize the probability of users seeing duplicated
                           content.
            - Full: Delete all documents that haven to been returned by the loader.
                    Clean up runs after all documents have been indexed.
                    This means that users may see duplicated content during indexing.
            - None: Do not delete any documents.
        source_id_key: Optional key that helps identify the original source
            of the document.
        cleanup_batch_size: Batch size to use when cleaning up documents.
        force_update: Force update documents even if they are present in the
            record manager. Useful if you are re-indexing with updated embeddings.

    Returns:
        Indexing result which contains information about how many documents
        were added, updated, deleted, or skipped.
    """
    if cleanup not in {"incremental", "full", None}:
        raise ValueError(
            f"cleanup should be one of 'incremental', 'full' or None. "
            f"Got {cleanup}."
        )

    if cleanup == "incremental" and source_id_key is None:
        raise ValueError("Source id key is required when cleanup mode is incremental.")

    # Check that the Vectorstore has required methods implemented
    methods = ["delete", "add_documents"]

    for method in methods:
        if not hasattr(vector_store, method):
            raise ValueError(
                f"Vectorstore {vector_store} does not have required method {method}"
            )

    if type(vector_store).delete == VectorStore.delete:
        # Checking if the vectorstore has overridden the default delete method
        # implementation which just raises a NotImplementedError
        raise ValueError("Vectorstore has not implemented the delete method")

    if isinstance(docs_source, BaseLoader):
        try:
            doc_iterator = docs_source.lazy_load()
        except NotImplementedError:
            doc_iterator = iter(docs_source.load())
    else:
        doc_iterator = iter(docs_source)

    source_id_assigner = _get_source_id_assigner(source_id_key)

    # Mark when the update started.
    index_start_dt = record_manager.get_time()
    num_added = 0
    num_skipped = 0
    num_updated = 0
    num_deleted = 0

    for doc_batch in _batch(batch_size, doc_iterator):
        hashed_docs = list(
            _deduplicate_in_order(
                [_HashedDocument.from_document(doc) for doc in doc_batch]
            )
        )

        source_ids: Sequence[Optional[str]] = [
            source_id_assigner(doc) for doc in hashed_docs
        ]

        if cleanup == "incremental":
            # If the cleanup mode is incremental, source ids are required.
            for source_id, hashed_doc in zip(source_ids, hashed_docs):
                if source_id is None:
                    raise ValueError(
                        "Source ids are required when cleanup mode is incremental. "
                        f"Document that starts with "
                        f"content: {hashed_doc.page_content[:100]} was not assigned "
                        f"as source id."
                    )
            # source ids cannot be None after for loop above.
            source_ids = cast(Sequence[str], source_ids)  # type: ignore[assignment]

        exists_batch = record_manager.exists([doc.uid for doc in hashed_docs])

        # Filter out documents that already exist in the record store.
        uids = []
        docs_to_index = []
        uids_to_refresh = []
        for hashed_doc, doc_exists in zip(hashed_docs, exists_batch):
            if doc_exists and not force_update:
                uids_to_refresh.append(hashed_doc.uid)
                continue
            uids.append(hashed_doc.uid)
            docs_to_index.append(hashed_doc.to_document())

        # Update refresh timestamp
        if uids_to_refresh:
            record_manager.update(uids_to_refresh, time_at_least=index_start_dt)
            num_skipped += len(uids_to_refresh)

        # Be pessimistic and assume that all vector store write will fail.
        # First write to vector store
        if docs_to_index:
            vector_store.add_documents(docs_to_index, ids=uids)
            num_added += len(docs_to_index)

        # And only then update the record store.
        # Update ALL records, even if they already exist since we want to refresh
        # their timestamp.
        record_manager.update(
            [doc.uid for doc in hashed_docs],
            group_ids=source_ids,
            time_at_least=index_start_dt,
        )

        # If source IDs are provided, we can do the deletion incrementally!
        if cleanup == "incremental":
            # Get the uids of the documents that were not returned by the loader.

            # mypy isn't good enough to determine that source ids cannot be None
            # here due to a check that's happening above, so we check again.
            for source_id in source_ids:
                if source_id is None:
                    raise AssertionError("Source ids cannot be None here.")

            _source_ids = cast(Sequence[str], source_ids)

            uids_to_delete = record_manager.list_keys(
                group_ids=_source_ids, before=index_start_dt
            )
            if uids_to_delete:
                # Then delete from vector store.
                vector_store.delete(uids_to_delete)
                # First delete from record store.
                record_manager.delete_keys(uids_to_delete)
                num_deleted += len(uids_to_delete)

    if cleanup == "full":
        while uids_to_delete := record_manager.list_keys(
            before=index_start_dt, limit=cleanup_batch_size
        ):
            # First delete from record store.
            vector_store.delete(uids_to_delete)
            # Then delete from record manager.
            record_manager.delete_keys(uids_to_delete)
            num_deleted += len(uids_to_delete)

    return {
        "num_added": num_added,
        "num_updated": num_updated,
        "num_skipped": num_skipped,
        "num_deleted": num_deleted,
    }

```

