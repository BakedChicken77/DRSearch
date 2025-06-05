// Function to send request to the backend
function sendRequest(endpoint) {
    const settings = {};

    // Collecting input values
    for (let i = 1; i <= 5; i++) {
        const value = document.getElementById(`setting${i}`).value;
        if (value) {
            settings[`setting${i}`] = value;
        }
    }

    // Creating the request object
    const requestOptions = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
    };

    // Sending the request
    fetch(`http://localhost:8025/data/${endpoint}`, requestOptions)
        .then(response => response.json())
        .then(data => displayMessage(data))
        .catch(error => displayMessage(`Error: ${error}`));
}

// Function to display response in the message window
function displayMessage(message) {
    const messageWindow = document.getElementById('messageWindow');
    messageWindow.innerText = JSON.stringify(message, null, 2);
}

// Function to retrieve and display a PDF
function retrievePDF(pdfName) {
    const url = `http://localhost:8025/documents/pdf/${pdfName}`;
    
    // Open the PDF in a new browser window
    window.open(url, '_blank');
}

// Function to clear input fields
function clearInputs() {
    for (let i = 1; i <= 5; i++) {
        document.getElementById(`setting${i}`).value = '';
    }
    document.getElementById('messageWindow').innerText = '';
}
