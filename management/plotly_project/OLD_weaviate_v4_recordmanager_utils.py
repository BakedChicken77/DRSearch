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

    def get_field_values(self, field, property_key='name'):
        """
        Retrieves the values for a specified property key from all objects in the collection.

        Parameters:
        - property_key: A string representing the property key.

        Returns:
        - A list of values for the specified property key.
        """
        property_values = []
        if field == 'uuid' or field == 'uuid':
            # Iterate over all objects in the collection
            collection = self.get_collection()
            for item in collection.iterator():
                property_values.append(item.uuid)

        elif field == 'vector' or field == 'vectors':
            # Iterate over all objects in the collection
            collection = self.get_collection()
            for item in collection.iterator():
                property_values.append(item.vector)

        else:
            # Check if the field is in self.get_property_keys(property_key)
            if not hasattr(self, 'properties') or field not in self.get_property_keys(property_key):
                raise ValueError(f"'{property_key}' is not a valid property key.")

            # Iterate over all objects in the collection
            collection = self.get_collection()
            for item in collection.iterator():
                # Append the value of the property to the list if it exists
                if field in item.properties:
                    property_values.append(item.properties[field])
                else:
                    property_values.append(None)  # Handle cases where the property is missing

        return property_values



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
        
        for uuid in ids:
            try:
                logger.info(f"Attempting to update UUID: {uuid} with field: {field_name} and value: {value}")
                collection.data.update(
                    uuid=uuid,
                    properties={
                        field_name: value,
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
        ids= self.get_field_values('uuid')
        return self.set_field_values_by_ids(ids, field_name,value)

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
        
        
        

if __name__ == "__main__":
    # Instantiate the class
    weaviate_url =  os.getenv('WEAVIATE_URL')
    weaviate_api_key = os.getenv('WEAVIATE_API_KEY')
    collection = 'SEPs_F_T_C_W_A_V_Summaries'# 'Injected_URL3'#
    try:
        RM= RecordManager_Util(
            weaviate_url=weaviate_url, 
            weaviate_api_key=weaviate_api_key,
            docs_index_name=collection,
            singleton=True,
        )

        
        # Perform operations with the client
        print("Connected to Weaviate:", RM.is_client_ready())


        results = RM.get_filtered_data(
            'use4RAG', 
            True, 
            'text_as_html', 
            return_last_updated_time=True, 
            # filter_by_last_update_time='1723487058.239'
        )

        results = RM.get_last_update_to_collection()
        
        RM.set_field_values_by_ids('87d8e09c-e155-5cb1-9b47-bad70ae8bf2c', 'plot_code', 0)
        ids = RM.get_field_values('uuid')
        RM.set_field_values_for_all_ids('use4RAG',True)
        # results = RM.get_filtered_data('use4RAG', True, 'text_as_html')
        results = RM.get_filtered_data(['use4RAG','page_number'], [True, 1], ['text_as_html','page_number'])
        RM.get_data_filter_by_id(ids[0])
        RM.set_field_values_for_all_ids('test_this','test')
        result = RM.get_field_values('test_this')
        result = RM.get_field_values('uuid')
        RM.add_new_field('test_this', 'text', 'test')
        x, y = RM._check_valid_fields(['uuid', 'use4RAG', 'goodf'])
        result= RM.get_field_values('use4RAG', 'name')

        
        for r in result[:100]:
            print(r)
        print(len(result))
        RM.close_weaviate_client()
        exit()

        value = RM.get_property_keys('name')



        results = RM.get_property_keys('name')
        

        for r in results:
            print(r)

        print('***************')

        aval_field_types = [item['data_type'] for item in results2]
        aval_field_names = [item['name'] for item in results2]

        for r in aval_field_names:
            print(r)

        print('***************')

        for r in aval_field_types:
            print(r)

    finally:
        closer= RecordManager_Util(singleton=True)       
        closer.close_weaviate_client()
