
## docker cp "C:\Users\Steve.Long\OneDrive - Leonardo DRS\Documents\_AI_TEAM\Ingestion_Docker\main.py" Ingest:/app/main.py

from fastapi import FastAPI, BackgroundTasks, Query, File, UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import subprocess
import os
import io
from pathlib import Path
from partition_pdf_and_docx_Final5 import process_file
from unstructured.documents.elements import Element


import truststore   # ensure OS-level CA store is honoured
# Inject corporate root/intermediate certs into the SSL truststore
truststore.inject_into_ssl()

app = FastAPI()

# Define the log file path from the environment variable
log_file = os.getenv('LOG_FILE_PATH', '/app/_RUN_INFO_WARNINGS_AND_ERRORS.txt')
#python_path = os.getenv('PYTHON_PATH', '/usr/bin/python3')

# Ensure the log file exists
with open(log_file, "w") as f:
    pass  # Create or clear the log file

@app.get("/")
def read_root():
    return {"message": "Welcome to the document processing GUI"}

@app.post("/run-script/")
def run_script(background_tasks: BackgroundTasks):
    def run():
        with open(log_file, "a") as f:
            # Run the run_ingest.py script and redirect its output to the log file
            process = subprocess.Popen(["python", "run_ingest.py"], stdout=f, stderr=f, env=os.environ)
            process.wait()  # Wait for the process to complete

    background_tasks.add_task(run)
    return {"message": "Script is running"}

# curl -Method POST -Uri "http://localhost:8000/run-script/JACSKE_TEST_20241126?max_chunk_size=5000&html_summaries=false&store_debug_files_files=false&element_dir_path=my_elements&docs_to_ingest=my_docs"
# curl -Method POST -Uri "http://localhost:8000/run-script/JACSKE_TEST_20241126?max_chunk_size=5000&html_summaries=false&store_debug_files_files=false"


@app.post("/run-script/{index}")
def run_script_with_index(
    index: str,
    background_tasks: BackgroundTasks,
    max_chunk_size: int = Query(None),
    html_summaries: bool = Query(None),
    store_debug_files_files: bool = Query(None),
    element_dir_path: str = Query(None),
    docs_to_ingest: str = Query(None)    
):
    def run():
        with open(log_file, "a") as f:
            # Build the command with arguments
            command = ["python", "run_ingest.py", index]

            # Append optional arguments if they are provided
            if max_chunk_size is not None:
                command.extend(["--max_chunk_size", str(max_chunk_size)])
            if html_summaries is not None:
                command.extend(["--html_summaries", str(html_summaries)])
            if store_debug_files_files is not None:
                command.extend(["--store_debug_files_files", str(store_debug_files_files)])
            if element_dir_path is not None:
                command.extend(["--element_dir_path", element_dir_path])
            if docs_to_ingest is not None:
                command.extend(["--docs_to_ingest", docs_to_ingest])

            # Run the run_ingest.py script with arguments
            process = subprocess.Popen(command, stdout=f, stderr=f, env=os.environ)
            process.wait()  # Wait for the process to complete

    background_tasks.add_task(run)
    return {"message": f"Script is running with index '{index}'"}

@app.get("/logs/")
def get_logs():
    def log_stream():
        with open(log_file, "r") as f:
            while True:
                line = f.readline()
                if not line:
                    break
                yield line

    return StreamingResponse(log_stream(), media_type="text/plain")

@app.get("/gui/")
def get_gui():
    return FileResponse("static/index.html")

@app.post("/ingest-new-docs/{collection}")
def check_new_docs(collection: str, background_tasks: BackgroundTasks):
    def run():
        with open(log_file, "a") as f:
            # Run the run_ingest.py script and redirect its output to the log file
            process = subprocess.Popen(["python", "ingest_docs.py"], stdout=f, stderr=f, env=os.environ)
            process.wait()  # Wait for the process to complete

    background_tasks.add_task(run)
    return {"message": f"Ingesting '{collection}'"}


## curl -X POST "http://localhost:8000/extract-text" -H "Content-Type: multipart/form-data" -F "file=@C:\\Users\\Steve.Long\\OneDrive - Leonardo DRS\\Desktop\\EmPower_Docs_Test_EmPower_Auth_Script\\HDD22011330_00.pdf"


@app.post("/extract-text")
async def extract_text(
    file: UploadFile = File(...),
    max_chunk_size: int = Query(8000),
    html_summaries: bool = Query(True)
):
    """
    Accepts a PDF, DOC, or DOCX file using multipart/form-data, processes it with
    the appropriate partitioning function, and returns extracted text chunks and metadata.
    """
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was uploaded."
        )

    # Validate file extension
    filename = file.filename.lower()
    if not (filename.endswith(".pdf") or filename.endswith(".doc") or filename.endswith(".docx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only PDF, DOC, or DOCX files are supported."
        )

    # Read file content into a BytesIO buffer
    file_content = await file.read()
    file_like = io.BytesIO(file_content)


    # Determine which partitioning function to use based on extension
    try:

        elements = process_file(
            file_path=None,
            input_file=file_like,
            base_dir=None, 
            elements_dir=Path(r"elements_dir"), 
            json_path=Path(r"elements_dir"), 
            max_chunk_size=max_chunk_size,
            html_summaries=html_summaries,
            doc_name=Path(filename)
        )
        
        # Construct the response data
        response_data = []
        for elem in elements:
            elem.metadata['category'] = elem.category
            response_data.append({
                "page_content": elem.page_content,
                "metadata": elem.metadata,
            })
        return {"elements": response_data}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )


## curl -X POST "http://localhost:8000/extract-text-test-only" -H "Content-Type: multipart/form-data" -F "file=@C:\\Users\\Steve.Long\\OneDrive - Leonardo DRS\\Desktop\\EmPower_Docs_Test_EmPower_Auth_Script\\HDD22011330_00.pdf"
@app.post("/extract-text-test-only")
async def extract_text(
    file: UploadFile = File(...),
    max_chunk_size: int = Query(8000),
    html_summaries: bool = Query(True)
):
    """
    Accepts a PDF, DOC, or DOCX file using multipart/form-data and returns Fake Data (extracted text chunks and metadata).
    """
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was uploaded."
        )

    # Validate file extension
    filename = file.filename.lower()
    if not (filename.endswith(".pdf") or filename.endswith(".doc") or filename.endswith(".docx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only PDF, DOC, or DOCX files are supported."
        )

    # Read file content into a BytesIO buffer
    file_content = await file.read()
    file_like = io.BytesIO(file_content)

    elements = []
    for index, _ in enumerate(range(5),start=1):
        x = Element()
        x.text = f'This is the text for element {index}'
        setattr(x, 'page_content', getattr(x, 'text'))
        x.metadata.filepath = f'this is the filepath for element {index}'

        if index ==1:
            x.metadata.image_base64 = [f"{index}VBORw0KGgoAAAANSUhEUgAA",f"{index}VBORw0KGgoAAAANSUhEUgBB"]
        else:
            x.metadata.image_base64 = [f"{index}VBORw0KGgoAAAANSUhEUgAA"]

        x.metadata.category = 'test_category'
        x.metadata.document_title = 'test_doc_title'
        x.metadata.filename = 'test_filename'
        x.metadata.text_as_html = ''
        x.metadata.url = ''

        x.metadata = x.metadata.to_dict()
        elements.append(x)

    try:
        # Construct the response data
        response_data = []
        for elem in elements:
            response_data.append({
                "page_content": elem.page_content,
                "metadata": elem.metadata
            })
        return {"elements": response_data}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )



app.mount("/static", StaticFiles(directory="static"), name="static")
