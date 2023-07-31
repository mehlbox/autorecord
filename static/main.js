let update = true

function get_data() {
    if (update) {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function() {
            if (this.readyState == 4 && this.status == 200) {
            data = JSON.parse(xhttp.responseText)
            /* fileinfo */
            for (const [key, value] of Object.entries(data.fileinfo)) {
                try {
                    document.getElementById(key).innerHTML = value
                } catch(err) {}
            }
            /* status */
            for (const [key, value] of Object.entries(data.status)) {
                if ( key == 'fileprogressbar'){ //key == 'buffer' | key == 'audiochunk' |
                    document.getElementById(key).style.width = value + '%'
                } else {
                    try {
                        document.getElementById(key).innerHTML = value
                    } catch(err) {}
                }
            }
            /* config */
            for (const [key, value] of Object.entries(data.config)) {
                if ( key == 'storage_mode'){
                    document.getElementById(key).innerHTML = value
                } else {
                    try {
                        document.getElementById(key).value = value
                    } catch(err) {}
                }
            }
            /* main */
            for (const [key, value] of Object.entries(data)) {
                if (key == 'gpio'){
                    if (value == 1) {
                        document.getElementById(key).classList.remove("led-red");
                        document.getElementById(key).classList.add("led-green");
                    } else {
                        document.getElementById(key).classList.remove("led-green");
                        document.getElementById(key).classList.add("led-red");
                    }
                } else {
                    try {
                        document.getElementById(key).innerHTML = value
                    } catch(err) {}
                }
            }
            set_status(data.status.status)
            }
        };
        xhttp.open("POST", "get_all_data", true);
        xhttp.send();
    }
    setTimeout(get_data, 1000);
}

function set_status(status) {
    //console.log(status)
    if (status == "standby") {
        document.getElementById('standby').style.backgroundColor = '#71A971';
    } else {
        document.getElementById('standby').style.backgroundColor = "gray";
    }
    if (status == "start") {
        document.getElementById('start').style.backgroundColor = '#71A971';
    } else {
        document.getElementById('start').style.backgroundColor = "gray";
    }
    if (status == "run") {
        document.getElementById('run').style.backgroundColor = '#71A971';
    } else {
        document.getElementById('run').style.backgroundColor = "gray";
    }
    if (status == "stop") {
        document.getElementById('stop').style.backgroundColor = '#71A971';
    } else {
        document.getElementById('stop').style.backgroundColor = "gray";
    }
}

function set_settings() {

    let data = {
        "sample_rate" : document.getElementById('sample_rate').value,
        "bit_depth" : document.getElementById('bit_depth').value,
        "file_limit" : document.getElementById('file_limit').value,
    }
    data = JSON.stringify(data)

    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            data = JSON.parse(xhttp.responseText)
            for (const [key, value] of Object.entries(data)) {
                try {
                    document.getElementById(key).value = value
                } catch(err) {}
            }
        }
    };
    
    xhttp.open("POST", "set_config", true);
    xhttp.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
    xhttp.send(data);

}

function call_split() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            data = JSON.parse(xhttp.responseText)
            for (const [key, value] of Object.entries(data)) {
                try {
                    console.log(key, value)
                } catch(err) {}
            }
        }
    };
    xhttp.open("POST", "call_split", true);
    xhttp.send();
}

function call_reboot() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            data = JSON.parse(xhttp.responseText)
            for (const [key, value] of Object.entries(data)) {
                try {
                    console.log(key, value)
                } catch(err) {}
            }
        }
    };
    xhttp.open("POST", "reboot", true);
    xhttp.send();
}

function call_exit() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            data = JSON.parse(xhttp.responseText)
            for (const [key, value] of Object.entries(data)) {
                try {
                    console.log(key, value)
                } catch(err) {}
            }
            setTimeout(get_settings, 5000);
        }
    };
    xhttp.open("POST", "exit", true);
    xhttp.send();
}

function show_reboot() {
    document.getElementById('plus_button').style.display = 'none'
    document.getElementById('hidden_reboot').style.display = 'block'
}


// Function to fetch the JSON data asynchronously
async function fetchJSONData(fetch_path) {
    try {
        const response = await fetch(fetch_path);
        const jsonData = await response.json();
        return jsonData;
    } catch (error) {
        console.error('Error fetching JSON data:', error);
    }
    }

// Function to populate the table with the JSON data
async function populateSchedule() {

    var jsonData = await fetchJSONData("get_schedule");
    var table = document.getElementById("feiertage");
    drawMatrix(jsonData.schedule_matrix);
    table.innerHTML  =  "<thead>\
                            <tr>\
                            <th>Datum</th>\
                            <th>Feiertag</th>\
                            </tr>\
                        </thead>"

    for (var date in jsonData.holidays) {
        var row = document.createElement("tr");

        var dateCell = document.createElement("td");
        var dateText = document.createTextNode(date);
        dateCell.appendChild(dateText);

        var holidayCell = document.createElement("td");
        var holidayText = document.createTextNode(jsonData.holidays[date]);
        holidayCell.appendChild(holidayText);

        row.appendChild(dateCell);
        row.appendChild(holidayCell);

        table.appendChild(row);
    }
}

// Function to populate the table with the JSON data
async function populateLog() {
    try {
      var response = await fetch('get_log');
      var logData = await response.text();
      
      var textarea = document.getElementById("log");
      textarea.value = logData;
    } catch (error) {
      console.error('Error fetching log data:', error);
    }
  }

// Get the content element by its id
var container = document.getElementById('container');

// Get all the menu items
var menuItems = document.querySelectorAll('.nav-link');

// Attach event listener to each menu item
menuItems.forEach(function(item) {
    item.addEventListener('click', function() {
        // Set the width of the content element
        if (item.id == "pills-status-tab") {
            container.style.maxWidth = 25 + 'rem';
            update = true;
        }
        if (item.id == "pills-schedule-tab") {
            container.style.maxWidth = 50 + 'rem';
            update = false;    
        }
        if (item.id == "pills-admin-tab") {
            container.style.maxWidth = 25 + 'rem';
            update = false;    
        }
        if (item.id == "pills-log-tab") {
            container.style.maxWidth = 70 + 'rem';
            update = false;    
        }
    });
});


get_data();