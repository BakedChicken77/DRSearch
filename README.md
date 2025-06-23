# Files:
*docker-compose.init.yml* creates docker volumes that contain already ingested documents
*docker-compose.app.yml* creates 4 containers:
1) frontend
2) backend
3) weaviate (vector databasae)
4) postgresql (recordmanager)

weaviate and postgresql will create empty docker volumes if docker-compose.init.yml was not used to create the volumnes and add data.

# Create docker volumes for vector database and postgresql and load data. This can be skipped if you don't have embedding data or if you want to start fresh with no documents ingested into the databases
```powershell
docker-compose -f docker-compose.init.yml up --build
```
Note: if there are left over containers after this setp, you can delete them.

# Create the application containers:
```powershell
docker-compose -f docker-compose.app.yml build --no-cache
```
# Start the application containers:
```powershell
docker-compose -f docker-compose.app.yml up -d  
```


# landing page is located at *localhost:3000*




# TO DISABLE ENTRA ID AUTH:
in drsearch_frontend\.env, set these to False:
```.env
AUTH_ENABLED=False
NEXT_PUBLIC_AUTH_ENABLED=False
```

in drsearch_backend\.env, uncomment these lines:
```.env
# AUTH_ENABLED=False
# NEXT_PUBLIC_AUTH_ENABLED=False
```

# TO SET FRONTEND TO DEVELOPMENT MODE:
in drsearch_frontend\Dockerfile.frontend, comment out these lines:
```Dockerfile
# FROM node:20.10-buster
# WORKDIR /app
# # 2) Copy only the built frontend assets and node_modules needed to run Next.js
# COPY --from=stage1 /app/.next ./.next
# COPY --from=stage1 /app/public ./public
# COPY --from=stage1 /app/node_modules ./node_modules
# COPY --from=stage1 /app/package.json ./package.json
```
and change
```Dockerfile
CMD ["yarn", "start"]
```
to
```Dockerfile
CMD ["yarn", "dev"]
```

## Streaming Chat API

The `/chat` endpoint streams `StreamEvent` objects using Server-Sent Events. Each
event has an SSE `event` field equal to `StreamEvent.type` and the JSON body is
the serialized dataclass:

```
event: raw_response_event
data: {"type":"raw_response_event","data":{"delta":"hi"}}

event: run_item_stream_event
data: {"type":"run_item_stream_event","name":"tool_output","item":{...}}
```

Clients should listen for these events and end the stream when an `end` event is
received.
