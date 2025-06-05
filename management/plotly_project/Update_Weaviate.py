import weaviate
import os
import json
from contextlib import contextmanager
from weaviate.auth import AuthApiKey

def get_weaviate_ids_from_field_values(client, index, field, value) -> list[str]:
    try:
        value = json.dumps(value)[1:-1]  # Remove the quotes added by json.dumps
        # Query to get objects with fields values equal to value
        def get_query(field: str, value: str, index: str) -> str:
            return f"""
{{
Get {{
    {index}(
    where: {{
        path: ["{field}"],
        operator: Equal,
        valueText: "{value}"
    }}
    ) {{
    _additional {{ id }}
    acronym_list
    }}
}}
}}
"""
        query = get_query(field, value, index)
        response = client.query.raw(query)

        results = []
        for rsp in response['data']['Get'][index]:
            results.append(rsp['_additional']['id'])

        if results:      
            return results
        return None
    
    except KeyError as e:
        print(f"KeyError: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def update_weaviate_field_values(client, index, ids, field, value):
    try:
        if ids:
            if not isinstance(ids, list):
                ids = [ids]

            value = json.dumps(value)[1:-1] 

            for id in ids:
                client.data_object.update(
                    data_object={field: value},
                    class_name=index,
                    uuid=id
                )
            return ids
        else:
            print("No elements found that match the filtered criteria")
            return None
    except Exception as e:
        print(f"An error occurred while updating: {e}")

# Context manager for Weaviate client
@contextmanager
def weaviate_client(WEAVIATE_URL, WEAVIATE_API_KEY):
    client = weaviate.Client(
        url=WEAVIATE_URL,
        auth_client_secret=AuthApiKey(api_key=WEAVIATE_API_KEY),
    )
    try:
        yield client
    finally:
        # Explicitly close the HTTP session
        client._connection.close()



def _replace_weaviate_field_values(client, index, filter_field, filter_value, update_field, update_value):
    # Example usage
    ids = get_weaviate_ids_from_field_values(
        client, 
        index, 
        filter_field, 
        filter_value
    )
    # Update field values for example IDs
    ids = update_weaviate_field_values(
        client, 
        index, 
        ids, 
        update_field, 
        update_value
    )
    return ids

def replace_weaviate_field_values(index, filter_field, filter_value, update_field, update_value,client=None, url=None, key=None):
    if not client:
        with weaviate_client(WEAVIATE_URL, WEAVIATE_API_KEY) as client:
            return _replace_weaviate_field_values(
                client, 
                index, 
                filter_field, 
                filter_value, 
                update_field,
                update_value,
            )
    else:
        return _replace_weaviate_field_values(
            client, 
            index, 
            filter_field, 
            filter_value, 
            update_field,
            update_value,
        )

if __name__ == "__main__":
    WEAVIATE_URL = os.environ.get("WEAVIATE_URL")
    WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")
    WEAVIATE_DOCS_INDEX_NAME = 'SEPs_F_T_C_W_A_V' 
    filter_field = "file_path"
    filter_value = "\\home.drs.com@ssl\\DavWWWRoot\\business03\\home\\SEPs\\SEP-17 Business Development\\SEP-17-08(I) Color Teams Guidelines.docx"
    update_field = filter_field#"acronym_list"
    test_list = ["The first", "the second", "the third"]
    update_value = filter_value#f"{test_list}"

    # filter_field = "acronym_list"
    # filter_value = f"""["The first", "the second", "the third"]"""
    
    ids = replace_weaviate_field_values(
        index=WEAVIATE_DOCS_INDEX_NAME, 
        filter_field=filter_field, 
        filter_value=filter_value, 
        update_field=update_field, 
        update_value=update_value,
        url=WEAVIATE_URL, 
        key=WEAVIATE_DOCS_INDEX_NAME
    )

    print(ids)
