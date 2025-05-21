# Files:
*docker-compose.ingest.yml* creates Ingest docker container


## Note: the .\doc folder will be mounted to the container. Files contained in .\doc will be ingested when 'ingest' button is pressed in the GUI.
## Landling page is located at 'http://localhost:8000/gui/'
## weaviate and postgresql containers must be running when using the GUI.
## Project 'My_Python_Libraries\text_extractor' provides an API to ths Ingest application. Weaviate and Postgresql containers are not required when using the API ("/run-script/" endpoint) because the data is not stored in databases when using the API. The text, metadata, and embeddings are instead returned in the API response.

# 1) Create docker container for Ingest application:
```powershell
docker-compose -f docker-compose.ingest.yml build --no-cache
```
## The image is ~40GB so the build will take some time.


# 2) Start the application containers:
```powershell
docker-compose -f docker-compose.ingest.yml up -d  
```

# 3) landing page is *'http://localhost:8000/gui/'*
