// script2.js
let selectedFields = ['uuid', 'filename', 'page_content']; // Default selected fields
let ascending = true; // Sort order
let currentData = []; // Store the current data for updating fields
let selectedIds = new Set(); // Store selected IDs
let isSelectAllChecked = false; // Track the state of the select_all checkbox

async function loadSelectedEmbeddings(fieldNames = selectedFields) {
    try {
        const queryString = fieldNames.map(field => `fields=${encodeURIComponent(field)}`).join('&');
        const response = await fetch(`/plotV1/scatter_plot/nonvisible?${queryString}`);
        if (!response.ok) {
            throw new Error(`Error fetching data: ${response.statusText}`);
        }
        const data = await response.json();
        const lastUpdateTime = data.LAST_UPDATE_TIME; // Extract the timestamp
        currentData = data.rows; // Assuming `rows` is the array of row data

        // Update SQLite database with the retrieved data
        await updateSQLiteDatabase(currentData, lastUpdateTime);

        // Now update the table
        updateTable();
    } catch (error) {
        console.error('Error loading selected embeddings:', error);
    }
}

async function updateSQLiteDatabase(data, lastUpdateTime) {
    // Initialize SQLite_Manager
    const SM = new SQLite_Manager('embeddings_db'); // Or the appropriate name

    // Add data to SQLite
    for (const row of data) {
        await SM.set_field_values_by_ids([row.uuid], 'plot_code', row.plot_code);
        await SM.set_field_values_by_ids([row.uuid], 'filename', row.filename);
        await SM.set_field_values_by_ids([row.uuid], 'page_content', row.page_content);
        // Add more fields as necessary
    }

    // Store the last update time in SQLite (or in local storage for easy access)
    localStorage.setItem('LAST_UPDATE_TIME', lastUpdateTime);
}


async function updateTable() {
    const SM = new SQLite_Manager('embeddings_db'); // Initialize SQLite_Manager

    const tableBody = document.getElementById('embeddings_table').getElementsByTagName('tbody')[0];
    tableBody.innerHTML = ''; // Clear any existing rows

    const tableHeaders = document.getElementById('table_headers');
    tableHeaders.innerHTML = '<th><input type="checkbox" id="select_all"></th>'; // Clear existing headers

    // Add new table headers based on selected fields
    selectedFields.forEach(field => {
        const th = document.createElement('th');
        th.innerHTML = `${field} <button class="sort-btn" onclick="sortTable('${field}')"></button>`;
        th.appendChild(createResizeHandle());
        tableHeaders.appendChild(th);
    });

    // Query SQLite for data
    const query = 'SELECT * FROM embeddings_table WHERE plot_code = 1'; // Adjust as necessary
    const data = await SM.get_filtered_data(query);

    data.forEach(item => {
        const row = document.createElement('tr');
        const cellCheckbox = document.createElement('td');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'row-checkbox';
        checkbox.value = item.uuid;
        checkbox.checked = selectedIds.has(item.uuid) || isSelectAllChecked;
        checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
                selectedIds.add(item.uuid);
            } else {
                selectedIds.delete(item.uuid);
                isSelectAllChecked = false; // Uncheck select_all if any checkbox is unchecked
                document.getElementById('select_all').checked = false;
            }
        });
        cellCheckbox.appendChild(checkbox);
        row.appendChild(cellCheckbox);

        selectedFields.forEach(field => {
            const cell = document.createElement('td');
            const cellValue = item[field] || 'N/A';
            
            if (typeof cellValue === 'string' && cellValue.length > 80) {
                const shortValue = cellValue.substring(0, 80) + '...';
                cell.innerHTML = `<span class="viewable-text">${shortValue}</span>`;
                cell.addEventListener('click', () => {
                    document.getElementById('modalText').textContent = cellValue;
                    document.getElementById('myModal').style.display = "block";
                });
            } else {
                cell.textContent = cellValue;
            }

            row.appendChild(cell);
        });

        tableBody.appendChild(row);
    });

    // Handle "select all" checkbox and other UI updates
    document.getElementById('select_all').addEventListener('change', toggleSelectAllCheckboxes);
}

async function manageSQLiteMemory(SM, maxMemorySize) {
    // Query to determine the current size of the SQLite database
    const sizeQuery = "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();";
    const sizeResult = await SM.execute_query(sizeQuery);
    const currentSize = sizeResult.size;

    if (currentSize > maxMemorySize) {
        // Implement logic to delete old or least recently used data
        await SM.purge_oldest_data();
    }
}

async function synchronizeWithServer() {
    const lastUpdateTime = localStorage.getItem('LAST_UPDATE_TIME');
    const response = await fetch(`/data/sync?last_update_time=${lastUpdateTime}`);
    if (!response.ok) {
        throw new Error(`Error syncing with server: ${response.statusText}`);
    }
    const data = await response.json();
    await updateSQLiteDatabase(data.rows, data.LAST_UPDATE_TIME);
}


// Function to select or deselect all row checkboxes
function toggleSelectAllCheckboxes(event) {
    isSelectAllChecked = event.target.checked;
    const checkboxes = document.querySelectorAll('.row-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = isSelectAllChecked;
        if (checkbox.checked) {
            selectedIds.add(checkbox.value);
        } else {
            selectedIds.delete(checkbox.value);
        }
    });
}

// Function to create a resize handle for table columns
function createResizeHandle() {
    const resizeHandle = document.createElement('div');
    resizeHandle.className = 'resize-handle';

    resizeHandle.addEventListener('mousedown', initResize, false);

    return resizeHandle;
}

// Function to initialize column resizing
function initResize(e) {
    const th = e.target.parentElement;
    const startX = e.pageX;
    const startWidth = parseInt(document.defaultView.getComputedStyle(th).width, 10);

    function doDrag(e) {
        th.style.width = startWidth + e.pageX - startX + 'px';
    }

    function stopDrag() {
        document.documentElement.removeEventListener('mousemove', doDrag, false);
        document.documentElement.removeEventListener('mouseup', stopDrag, false);
    }

    document.documentElement.addEventListener('mousemove', doDrag, false);
    document.documentElement.addEventListener('mouseup', stopDrag, false);
}

// Function to select or deselect all row checkboxes
function toggleSelectAllCheckboxes(event) {
    const checkboxes = document.querySelectorAll('.row-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = event.target.checked;
        if (checkbox.checked) {
            selectedIds.add(checkbox.value);
        } else {
            selectedIds.delete(checkbox.value);
        }
    });
}


// Function to send selected data's 'uuid' to the server
function removeFromRAGSearch(event) {
    event.preventDefault();

    const selectedCheckboxes = document.querySelectorAll('.row-checkbox:checked');
    const selectedIdsArray = Array.from(selectedIds);

    fetch(`/plotV1/remove_from_rag`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ selected_ids: selectedIdsArray })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Selected embeddings sent successfully:', data);
        alert('Selected embeddings sent successfully');
    })
    .catch(error => {
        console.error('Error sending selected embeddings:', error);
        alert('Failed to send selected embeddings');
    });
}

// Function to send selected data's 'uuid' to the server
function addBackToPlot(event) {
    event.preventDefault();

    const selectedCheckboxes = document.querySelectorAll('.row-checkbox:checked');
    const selectedIdsArray = Array.from(selectedIds);

    fetch(`/plotV1/add_back_points`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ selected_ids: selectedIdsArray })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Selected embeddings sent successfully:', data);
        alert('Selected embeddings sent successfully');
    })
    .catch(error => {
        console.error('Error sending selected embeddings:', error);
        alert('Failed to send selected embeddings');
    });
}

// Get the modals
const modal = document.getElementById("myModal");
const configModal = document.getElementById("configModal");

// Get the <span> element that closes the modals
const span = document.getElementsByClassName("close")[0];
const spanConfig = document.getElementsByClassName("close-config")[0];

// When the user clicks on <span> (x), close the modals
span.onclick = function() {
    modal.style.display = "none";
}

spanConfig.onclick = function() {
    configModal.style.display = "none";
}

// When the user clicks anywhere outside of the modals, close them
window.onclick = function(event) {
    if (event.target == modal) {
        modal.style.display = "none";
    }
    if (event.target == configModal) {
        configModal.style.display = "none";
    }
}

// Function to load field names into config table
async function loadFieldNames() {
    try {
        const response = await fetch('/data/retrieve/field_names');
        if (!response.ok) {
            throw new Error(`Error fetching field names: ${response.statusText}`);
        }
        const fieldNames = await response.json();
        const tableBody = document.getElementById('config_table').getElementsByTagName('tbody')[0];

        // Clear any existing rows
        tableBody.innerHTML = '';

        // Add new rows with checkboxes
        fieldNames.forEach(field => {
            const row = document.createElement('tr');
            const cellField = document.createElement('td');
            const cellSelect = document.createElement('td');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = selectedFields.includes(field);

            cellField.textContent = field;
            cellSelect.appendChild(checkbox);

            row.appendChild(cellField);
            row.appendChild(cellSelect);
            tableBody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading field names:', error);
    }
}

// Function to select or deselect all checkboxes
function toggleSelectAll(selectAll) {
    const checkboxes = document.querySelectorAll('#config_table tbody input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAll;
    });
}

// Function to apply config and reload embeddings
function applyConfig() {
    const checkboxes = document.querySelectorAll('#config_table tbody input[type="checkbox"]');
    const newSelectedFields = [];

    checkboxes.forEach(checkbox => {
        if (checkbox.checked) {
            newSelectedFields.push(checkbox.closest('tr').children[0].textContent);
        }
    });

    selectedFields = newSelectedFields; // Update selectedFields directly
    loadSelectedEmbeddings(selectedFields); // Reload table with new selected fields
    configModal.style.display = "none"; // Close the config modal
}


// Function to sort the table based on a column
function sortTable(column) {
    const table = document.getElementById('embeddings_table');
    const rows = Array.from(table.rows).slice(1); // Exclude the header row
    const columnIndex = Array.from(table.rows[0].cells).findIndex(cell => cell.textContent.includes(column));

    rows.sort((a, b) => {
        const aText = a.cells[columnIndex].textContent.trim();
        const bText = b.cells[columnIndex].textContent.trim();

        if (ascending) {
            return aText.localeCompare(bText, undefined, {numeric: true});
        } else {
            return bText.localeCompare(aText, undefined, {numeric: true});
        }
    });

    ascending = !ascending; // Toggle sort order

    // Reattach sorted rows
    rows.forEach(row => table.appendChild(row));

    // Update sort button appearance
    document.querySelectorAll('.sort-btn').forEach(btn => btn.classList.remove('desc'));
    if (!ascending) {
        document.querySelectorAll(`.sort-btn[onclick="sortTable('${column}')"]`).forEach(btn => btn.classList.add('desc'));
    }
}

// Event listener for config table button
document.getElementById('config_table_btn').addEventListener('click', () => {
    configModal.style.display = "block";
    loadFieldNames();
});

// Event listener for apply config button
document.getElementById('apply_config_btn').addEventListener('click', applyConfig);

// Event listener for cancel config button
document.getElementById('cancel_config_btn').addEventListener('click', () => {
    configModal.style.display = "none";
});

// Event listener for select all button
document.getElementById('select_all_btn').addEventListener('click', () => toggleSelectAll(true));

// Event listener for deselect all button
document.getElementById('deselect_all_btn').addEventListener('click', () => toggleSelectAll(false));

// Load selected embeddings every 5 seconds
setInterval(() => loadSelectedEmbeddings(selectedFields), 1000);
window.onload = () => loadSelectedEmbeddings(selectedFields);
