let isSelecting = false;
let initialSelectionState = false;
let lastCell = null;
let startCell = null;

const tableHead = document.querySelector('thead tr');
const tableBody = document.querySelector('tbody');

// Generate the column headers dynamically
for (let col = 0; col < 24; col++) {
  const newHeader = document.createElement('th');
  newHeader.textContent = col;
  tableHead.appendChild(newHeader);
}

// Generate the rows and cells
const cells = [];
for (let row = 0; row < 7; row++) {
  cells[row] = [];
  const newRow = document.createElement('tr');

  const rowHeader = document.createElement('th');
  rowHeader.textContent = getDayOfWeek(row);
  newRow.appendChild(rowHeader);

  for (let col = 0; col < 24; col++) {
    const newCell = document.createElement('td');
    newCell.addEventListener('mousedown', handleMouseDown);
    newRow.appendChild(newCell);

    // Save cell reference for later use
    cells[row][col] = newCell;
  }

  tableBody.appendChild(newRow);
}


// Function to get the day of the week based on the index
function getDayOfWeek(index) {
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    return days[index];
}


// Function to handle mouse down event for starting selection
function handleMouseDown(event) {
    isSelecting = true;
    const cell = event.target;
    lastCell = cell;
    startCell = cell;
    const startRow = cell.parentNode.rowIndex - 1; // Subtract 1 to account for the first row
    const startCol = cell.cellIndex - 1; // Subtract 1 to account for the first column

    initialSelectionState = !cell.dataset.selected || cell.dataset.selected === "false";

    if (initialSelectionState) {
        cell.dataset.selected = "true";
    } else {
        cell.dataset.selected = "false";
    }

    table.addEventListener('mouseover', handleMouseOver);
    table.addEventListener('mouseup', handleMouseUp);
}


// Function to handle mouse over event for selecting or deselecting multiple cells
function handleMouseOver(event) {
    if (isSelecting) {
        const cell = event.target;
        if (cell.tagName === 'TD' && cell !== lastCell) {
        lastCell = cell;

        // Get the start and end row/column indices
        const startRow = startCell.parentNode.rowIndex - 1; // Subtract 1 to account for the first row
        const startCol = startCell.cellIndex - 1; // Subtract 1 to account for the first column
        const endRow = cell.parentNode.rowIndex - 1; // Subtract 1 to account for the first row
        const endCol = cell.cellIndex - 1; // Subtract 1 to account for the first column

        // Determine the selection state based on the initial selection
        const shouldSelect = initialSelectionState;

        // Update the selection rectangle
        selectRectangle(startRow, startCol, endRow, endCol, shouldSelect);
        }
    }
}


// Function to handle mouse up event for ending selection
function handleMouseUp() {
    isSelecting = false;
    lastCell = null;
    table.removeEventListener('mouseover', handleMouseOver);
    table.removeEventListener('mouseup', handleMouseUp);
    sendMatrixToServer();
}


// Function to select or deselect a rectangle of cells
function selectRectangle(startRow, startCol, endRow, endCol, shouldSelect) {
  const minRow = Math.min(startRow, endRow);
  const maxRow = Math.max(startRow, endRow);
  const minCol = Math.min(startCol, endCol);
  const maxCol = Math.max(startCol, endCol);

  for (let row = minRow; row <= maxRow; row++) {
    for (let col = minCol; col <= maxCol; col++) {
      const cell = cells[row][col];
      if (shouldSelect) {
          cell.dataset.selected = "true";
      } else {
          cell.dataset.selected = "false";
      }
    }
  }
}


// Function to convert the selected matrix to JSON and send to the server
function sendMatrixToServer() {
    const selectedMatrix = {};

    for (const rowKey in cells) {
      const row = cells[rowKey];
      for (const columnKey in row) {
        const cell = row[columnKey];

        if (!selectedMatrix[rowKey]) {
            selectedMatrix[rowKey] = [];
        }

        if (cell.dataset.selected === "true"){
            selectedMatrix[rowKey][columnKey] = true;
        } else {
            selectedMatrix[rowKey][columnKey] = false;
        }
      }
    }

    const jsonData = JSON.stringify(selectedMatrix);

    // Send the JSON data to the server
    fetch('/matrix', {
        method: 'POST',
        headers: {
        'Content-Type': 'application/json'
        },
        body: jsonData
    })
    .then(response => response)
    .then(data => {
        console.log('OK');
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

// Function to update matrix on page
function drawMatrix(data) {
    // Process the received JSON data and update the table
    for (const rowKey in data) {
      const row = data[rowKey];
      for (const columnKey in row) {
        const value = row[columnKey];
        const cell = cells[rowKey][columnKey];
        cell.dataset.selected = value;
      }
    }
  }
// Attach mouse event listeners to the table
const table = document.querySelector('table');
