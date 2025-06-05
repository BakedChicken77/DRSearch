# rm_operations.py
from weaviate import Client
# from weaviate_recordmanager_utils.record_manager_util import RecordManager_Util
from weaviate_recordmanager_utils.weaviate_v4_recordmanager_utils import RecordManager_Util

# class RMOperations:
#     def __init__(self, docs_index_name: str):
#         self.RM = RecordManager_Util(docs_index_name=docs_index_name)

#     def set_all_ids_visible(self, client: Client):
#         self.RM._update_all_field_values(client, 'plot_code', 1)

#     def set_field_values_by_id(self, client: Client, ids: list, field_name: str, value):
#         self.RM.set_field_values_by_id(client, ids, field_name, value)

#     def set_ids_to_visible(self, client: Client, ids: list):
#         self.RM.set_field_values_by_id(client, ids, 'plot_code', 1)

#     def set_ids_to_nonvisible(self, client: Client, ids: list):
#         self.RM.set_field_values_by_id(client, ids, 'plot_code', 0)

#     def get_filtered_data(self, client: Client, field_name: str, value, fields: list):
#         return self.RM.get_filtered_data(client, field_name, value, fields)
    
#     def get_filtered_by_plot_code(self, client: Client, plot_code, returned_fields: list):
#         return self.RM.get_filtered_data(client, 'plot_code', plot_code, returned_fields)
    
    
#     def get_all_field_names(self, client):
#         return self.RM.get_metadata_fields(client)


class RMOperations:
    def __init__(self, docs_index_name: str):
        self.RM = RecordManager_Util(docs_index_name=docs_index_name,singleton=True)

    def set_all_ids_visible(self):
        self.RM.set_field_values_for_all_ids('plot_code', 1)
        self.RM.set_field_values_for_all_ids('use4RAG', True)

    def set_field_values_by_id(self, ids: list, field_name: str, value):
        self.RM.set_field_values_by_ids(ids, field_name, value)

    def set_ids_to_visible(self, ids: list):
        self.RM.set_field_values_by_ids(ids, 'plot_code', 1)

    def set_ids_no_rag(self, ids: list):
        self.RM.set_field_values_by_ids(ids, 'use4RAG', False)

    def set_ids_yes_rag(self, ids: list):
        self.RM.set_field_values_by_ids(ids, 'use4RAG', True)

    def set_ALL_ids_yes_rag(self):
        self.RM.set_field_values_for_all_ids('use4RAG', True)

    def set_ids_to_nonvisible(self, ids: list):
        self.RM.set_field_values_by_ids(ids, 'plot_code', 0)

    def get_filtered_data(self, field_name: str, value, fields: list):
        return self.RM.get_filtered_data(field_name, value, fields)
    
    def get_filtered_by_plot_code(self, plot_code, returned_fields: list):
        # return self.RM.get_filtered_data('plot_code', plot_code, returned_fields)
        return self.RM.get_filtered_data(['plot_code','use4RAG'], [plot_code, True], returned_fields)
        
    def get_all_field_names(self):
        return self.RM.get_property_keys('name')
    
    def close_client(self):
        return self.RM.close_weaviate_client()
    
    def get_last_update(self):
        return self.RM.get_last_update_to_collection()
    
    def get_collection_schema(self):
        return self.RM.get_collection_schema()
    
    def get_collection_names(self):
        return self.RM.get_all_collection_names()
       
    def _check_valid_fields(self, fields):
        return self.RM._check_valid_fields(fields)
    
    def add_new_field(self, field, type, value):
        return self.RM.add_new_field(field, type, value)

    def get_field_values(self, fields):
        return self.RM.get_field_values(fields) 
    
    def reset_plot_field_values(self,field_name,value):
        return self.RM.set_field_values_for_all_ids(field_name,value)
    
    def set_all_values_per_filename(self,filename,field,value):
        uuid = self.RM.get_filtered_data('filename', filename, 'uuid')
        return self.RM.set_field_values_by_ids(uuid, field, value )        
    
