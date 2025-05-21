

import hashlib
import os
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, create_engine, inspect, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
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
    group_id = Column(String, index=True, nullable=False) # this is the file_path without the extension (.docx, .pdf, etc... are removed)
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

    def get_document_status(self, file_path, group_id=None):
        """Checks the status of a document (new, modified, or current).

        Args:
            group_id: The group ID of the document.

        Returns:
            The status of the document ('new', 'modified', or 'current').
        """
        if not group_id:
            group_id = os.path.splitext(file_path)[0]
            

        group_id= str(group_id)
        session = self.Session()
        try:
            doc_record = session.query(DocRecord).filter_by(group_id=group_id, namespace=self.namespace).first()
            if doc_record:
                file_hash = self.get_document_hash(file_path)
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

        """
        ISSUE SUMMARY:

        The current implementation of the `delete_document` method does not properly delete old chunks from the Weaviate database when a document is updated. 
        While the method correctly identifies and deletes keys from the record manager based on `group_ids`, it fails to target and delete the corresponding 
        chunks from Weaviate. This results in both the old and new chunks coexisting in the database after an update.

        ROOT CAUSE:

        1. The deletion logic for Weaviate is flawed:
        - It retrieves all objects in the namespace using the Weaviate client query (`client.query.get(namespace)`).
        - It deletes these objects without filtering them based on the `group_ids` or the keys retrieved from the record manager.

        2. This indiscriminate deletion process:
        - Either deletes unrelated data in the namespace (if objects are present for other documents).
        - Or fails to delete the specific chunks associated with the `group_ids`, leaving old chunks in Weaviate.

        IMPACT:

        - Duplicate chunks: Old chunks remain in the Weaviate database alongside the newly inserted chunks.
        - Inefficiency: The script performs unnecessary operations by querying and deleting all objects in the namespace instead of targeting specific ones.
        - Inconsistency: The record manager accurately tracks the current state of the document, but Weaviate retains outdated data, causing a mismatch.

        RESOLUTION PLAN (TO BE IMPLEMENTED):

        1. Modify the `delete_document` method to use the `keys` (IDs) retrieved from `self.record_manager.list_keys(group_ids=group_ids)` 
        for deletions in Weaviate.
        2. Replace the direct interaction with the Weaviate client (`client.data_object.delete`) with the vector store's `delete` method:
        - Example: `vectorstore.delete(ids=keys)`
        3. Ensure the method deletes only the specific chunks associated with the `group_ids`, preventing duplication or unintended deletions.

        TEMPORARY WORKAROUND:

        Until this fix is implemented, manual cleanup of old chunks in the Weaviate database may be necessary to prevent duplication issues 
        when updating documents.

        """



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
            # Mapping from group_id (without extension) to full file_path (with extension)
            group_id_to_file_path = {}
            up_to_date_group_ids = []

            # Populate group_id_to_file_path from elements
            for element in elements:
                file_path = element.metadata['file_path']  # Full file path with extension
                group_id = os.path.splitext(file_path)[0]  # Remove extension
                if group_id:
                    group_id_to_file_path[group_id] = file_path

            # List of unique group IDs
            list_of_group_ids = list(group_id_to_file_path.keys())

            # Check the status of each document
            for group_id in list_of_group_ids:
                file_path = group_id_to_file_path[group_id]
                file_hash = self.get_document_hash(file_path)
                last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                existing_doc_status = self.get_document_status(group_id,file_path)
                
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
                batch_elements = [element for element in elements if os.path.splitext(element.metadata['file_path'])[0] in batch_group_ids]

                # Modify 'file_path' in metadata to remove the extension
                for element in batch_elements:
                    file_path_with_ext = element.metadata['file_path']
                    file_path_without_ext = os.path.splitext(file_path_with_ext)[0]
                    element.metadata['file_path'] = file_path_without_ext    # Update 'file_path' to be without extension

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
                            file_path = group_id_to_file_path[group_id]
                            file_hash = self.get_document_hash(file_path)
                            last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
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
