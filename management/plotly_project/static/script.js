let port;

async function getConfig() {
    const response = await fetch('/config');
    const config = await response.json();
    port = config.port;
    await populateCollectionDropdown(); // Populate the collection dropdown
    checkDatabaseInitStatus(); // Start checking the database status after fetching the config
}

async function checkDatabaseInitStatus() {
    try {
        const response = await fetch('http://localhost:8025/check_database_init_status');
        const data = await response.json();

        if (data.status === 'OK') {
            document.getElementById('status-container').classList.add('hidden');
            document.getElementById('main-content').classList.remove('hidden');
            document.getElementById('main-content').style.display = 'block'; // Ensure main content is shown
            initializeApplication();
        } else {
            displayNotInitializedMessage();
            setTimeout(checkDatabaseInitStatus, 5000); // Retry every 5 seconds if not initialized
        }
    } catch (error) {
        console.error('Error checking database status:', error);
        setTimeout(checkDatabaseInitStatus, 5000); // Retry every 5 seconds in case of error
    }
}

function displayNotInitializedMessage() {
    const statusMessage = document.getElementById('status-message');
    const initDatabaseBtn = document.getElementById('init-database-btn');

    statusMessage.textContent = 'Database Is Not Initialized for Post-Processing';
    initDatabaseBtn.classList.remove('hidden');
    initDatabaseBtn.onclick = initializeDatabase;
}

async function initializeDatabase() {
    try {
        const response = await fetch('http://localhost:8025/initialize_database');
        const data = await response.json();

        if (data.status === 'Done') {
            checkDatabaseInitStatus(); // Trigger a status check after initialization
        } else {
            console.error('Database initialization failed:', data);
        }
    } catch (error) {
        console.error('Error initializing database:', error);
    }
}

function initializeApplication() {
    console.log("Configured port:", port);
    // Clear existing plots
    Plotly.purge('scatter_plot');
    Plotly.purge('bar_plot');
    Plotly.purge('centroid_plot');

    createPlot('scatter_plot', '/plotV1/scatter_plot/visible', plotScatter);
    createPlot('bar_plot', '/plotV1/bar_plot/visible', plotBar);
    createPlot('centroid_plot', '/plotV1/centroid_plot/visible', plotCentroid);

    const clearButton = document.getElementById('Reset_embeddings_btn');
    clearButton.addEventListener('click', async function() {
        try {
            const response = await fetch(`/plotV1/show_all_plot_data`, { method: 'GET' });
            if (response.ok) {
                const data = await response.json();
                console.log('Selected embeddings cleared successfully:', data);
                reloadScatterPlot();
            } else {
                throw new Error(`Failed to clear selected embeddings: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Error clearing selected embeddings:', error);
            alert('Failed to clear selected embeddings');
        }
    });

    updatePlotVisibility('scatter');
    window.addEventListener('resize', resizePlots);
}

async function fetchPlotData(endpoint) {
    try {
        const response = await fetch(endpoint);
        if (!response.ok) throw new Error(`Error loading ${endpoint}: ${response.statusText}`);
        return await response.json();
    } catch (error) {
        console.error(error);
        alert(`Failed to load data from ${endpoint}`);
    }
}

async function createPlot(containerId, endpoint, plotFunction) {
    const data = await fetchPlotData(endpoint);
    if (data) plotFunction(data, containerId);
}

function plotScatter(data, containerId) {
    console.log('Plotting Scatter Plot in', containerId);

    const traces = [];
    const clusters = Array.from(new Set(data.map(d => d.clusterID)));
    console.log('Clusters found:', clusters); // Log clusters

    clusters.forEach(clusterID => {
        console.log('Data received for plotting:', data);
        const clusterData = data.filter(d => d.clusterID === clusterID);
        console.log('UUIDs for this cluster:', clusterData.map(d => d.uuid)); // Check UUIDs

        traces.push({
            x: clusterData.map(d => d.tsne_x),
            y: clusterData.map(d => d.tsne_y),
            mode: 'markers',
            type: 'scatter',
            name: `Cluster ${clusterID}`,
            text: clusterData.map(d => `Cluster: ${d.clusterID}<br>Filename: ${d.filename}<br>Content: ${d.page_content.substring(0, 80)}<br>UUID: ${d.uuid}`),
            customdata: clusterData.map(d => d.uuid), // Include the id in customdata
            marker: { size: 10 }
        });
    });

    console.log('Traces created:', traces); // Log traces

    const layout = {
        title: 't-SNE Clustering of Documents',
        dragmode: 'lasso',
        hovermode: 'closest'
    };

    Plotly.newPlot(containerId, traces, layout);

    const scatterPlot = document.getElementById(containerId);
    scatterPlot.on('plotly_selected', function(eventData) {
        const selectedPoints = eventData.points.map(point => point.customdata);
    
        console.log('Selected Points:', selectedPoints); // Log selected points before sending
    
        fetch(`/plotV1/remove_points`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ selected_ids: selectedPoints })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Selected embeddings sent successfully:', data);
            reloadScatterPlot(); // Reload the scatter plot after saving embeddings
        })
        .catch(error => {
            console.error('Error sending selected embeddings:', error);
            alert('Failed to send selected embeddings');
        });
    });
}

function plotBar(data, containerId) {
    const trace = {
        x: data.x,
        y: data.y,
        type: 'bar'
    };

    const layout = {
        title: 'Cluster Distribution',
        xaxis: { title: 'Cluster' },
        yaxis: { title: 'Number of Documents' }
    };

    Plotly.newPlot(containerId, [trace], layout);
}

function plotCentroid(data, containerId) {
    const trace = {
        x: data.map(d => d.tsne_x),
        y: data.map(d => d.tsne_y),
        mode: 'markers',
        type: 'scatter',
        marker: { color: data.map(d => d.clusterID) }
    };

    const layout = {
        title: 't-SNE Visualization of Cluster Centroids',
        xaxis: { title: 't-SNE 1' },
        yaxis: { title: 't-SNE 2' }
    };

    Plotly.newPlot(containerId, [trace], layout);
}

function updatePlotVisibility(selectedPlot) {
    document.getElementById('scatter_plot').style.display = 'none';
    document.getElementById('bar_plot').style.display = 'none';
    document.getElementById('centroid_plot').style.display = 'none';

    if (selectedPlot === 'scatter') {
        document.getElementById('scatter_plot').style.display = 'block';
    } else if (selectedPlot === 'bar') {
        document.getElementById('bar_plot').style.display = 'block';
    } else if (selectedPlot === 'centroid') {
        document.getElementById('centroid_plot').style.display = 'block';
    }

    // Resize the visible plot
    resizePlots();
}

function handleOperationSelection() {
    const operationSelect = document.getElementById('operation-select');
    const selectedOperation = operationSelect.value;

    if (selectedOperation !== 'operations') {
        let maxClusters = null;
        let minClusters = null;


        // Check if the selected operation is related to clustering
        if (selectedOperation === 'recalc_clusters') {
            maxClusters = prompt('Enter the max number of clusters (an integer value):');
            minClusters = prompt('Enter the min number of clusters (an integer value):');
            if (maxClusters === null) {
                // If the user cancels the prompt, don't proceed with the operation
                operationSelect.value = 'operations';
                return;
            }
            if (minClusters === null) {
                // If the user cancels the prompt, don't proceed with the operation
                operationSelect.value = 'operations';
                return;
            }

            // Ensure the input is a valid integer
            maxClusters = parseInt(maxClusters, 10);
            if (isNaN(maxClusters) || maxClusters <= 0) {
                alert('Please enter a valid positive integer for the max number of clusters. Must be creater than Min Clusters');
                operationSelect.value = 'operations';
                return;
            }
            minClusters = parseInt(minClusters, 10);
            if (isNaN(minClusters) || minClusters <= 1) {
                alert('Please enter a valid positive integer for the min number of clusters. Must be greater than 2 abd less than Max Clusters');
                operationSelect.value = 'operations';
                return;
            }
        }

        const confirmed = confirm(`Are you sure you want to perform the operation: ${selectedOperation.replace('_', ' ')}?`);
        if (confirmed) {
            executeOperation(selectedOperation, maxClusters, minClusters);
        }

        // Reset to 'Operations' after selection
        operationSelect.value = 'operations';




    }
}

function handlePlotSelection() {
    const plotSelect = document.getElementById('plot-select');
    const selectedPlot = plotSelect.value;

    if (selectedPlot !== 'plot_type') {
        updatePlotVisibility(selectedPlot);

        // Reset to 'plot_type' after selection
        plotSelect.value = 'plot_type';
    }
}

async function executeOperation(operation, maxClusters = null, minClusters = null) {
    try {
        const requestData = {};
        
        // Include max_clusters in the request if provided
        if (maxClusters !== null) {
            requestData.max_clusters = maxClusters;
        }
        if (minClusters !== null) {
            requestData.min_clusters = minClusters;
        }

        const response = await fetch(`/data/operations/${operation}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        if (response.ok) {
            const data = await response.json();
            console.log(`${operation.replace('_', ' ')} executed successfully:`, data);
            initializeApplication()
        } else {
            throw new Error(`Failed to execute ${operation}: ${response.statusText}`);
        }
    } catch (error) {
        console.error(`Error executing ${operation}:`, error);
        alert(`Failed to execute ${operation}`);
    }
}

async function reloadScatterPlot() {
    // Clear the existing scatter plot
    Plotly.purge('scatter_plot');
    // Recreate the scatter plot
    await createPlot('scatter_plot', '/plotV1/scatter_plot/visible', plotScatter);
}

async function reloadBarPlot() {
    // Clear the existing bar plot
    Plotly.purge('bar_plot');
    // Recreate the bar plot
    await createPlot('bar_plot', '/plotV1/bar_plot/visible', plotBar);
}

async function reloadClusterPlot() {
    // Clear the existing cluster plot
    Plotly.purge('centroid_plot');
    // Recreate the cluster plot
    await createPlot('centroid_plot', '/plotV1/centroid_plot/visible', plotCentroid);
}

function resizePlots() {
    const scatterPlot = document.getElementById('scatter_plot');
    const barPlot = document.getElementById('bar_plot');
    const centroidPlot = document.getElementById('centroid_plot');

    if (scatterPlot.style.display === 'block') {
        Plotly.Plots.resize(scatterPlot);
    }
    if (barPlot.style.display === 'block') {
        Plotly.Plots.resize(barPlot);
    }
    if (centroidPlot.style.display === 'block') {
        Plotly.Plots.resize(centroidPlot);
    }
}

async function populateCollectionDropdown() {
    try {
        // Fetch collection names
        const response = await fetch('/data/schema/get_all_collection_names');
        const data = await response.json();
        const collections = data.result;
        
        // Fetch the currently selected collection
        const selectedResponse = await fetch('/data/schema/get_selected_collection');
        const selectedData = await selectedResponse.json();
        const selectedCollection = selectedData.selected_collection;
        
        const collectionSelect = document.getElementById('collection-select');
        
        // Clear existing options
        collectionSelect.innerHTML = '';
        
        // Add a default option
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Select Collection';
        defaultOption.disabled = true;
        collectionSelect.appendChild(defaultOption);
        
        // Populate the dropdown
        collections.forEach(collection => {
            const option = document.createElement('option');
            option.value = collection;
            option.textContent = collection;
            if (collection === selectedCollection) {
                option.selected = true;
            }
            collectionSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error fetching collection names:', error);
    }
}

async function handleCollectionSelection() {
    const collectionSelect = document.getElementById('collection-select');
    const selectedCollection = collectionSelect.value;
    
    if (selectedCollection) {
        // Send the selected collection to the backend
        try {
            const response = await fetch('/data/schema/set_selected_collection', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ collection_name: selectedCollection })
            });
            
            const data = await response.json();
            if (response.ok) {
                console.log('Selected collection set successfully:', data);
                // Re-initialize the application with the new collection
                initializeApplication();
            } else {
                console.error('Error setting selected collection:', data);
            }
        } catch (error) {
            console.error('Error setting selected collection:', error);
        }
    }
}


window.onload = getConfig; // Start the configuration fetching on window load
