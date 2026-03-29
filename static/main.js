let update = true
const THEME_STORAGE_KEY = 'autorecord_theme';

function applyTheme(themeName) {
    const normalized = themeName === 'modern' ? 'modern' : 'vintage';
    document.documentElement.setAttribute('data-theme', normalized);

    const vintageBtn = document.getElementById('theme_vintage');
    const modernBtn = document.getElementById('theme_modern');
    if (vintageBtn) {
        vintageBtn.classList.toggle('is-active', normalized === 'vintage');
    }
    if (modernBtn) {
        modernBtn.classList.toggle('is-active', normalized === 'modern');
    }
}

function setTheme(themeName) {
    applyTheme(themeName);
    try {
        localStorage.setItem(THEME_STORAGE_KEY, themeName);
    } catch(err) {}
}

function initTheme() {
    let saved = 'vintage';
    try {
        saved = localStorage.getItem(THEME_STORAGE_KEY) || 'vintage';
    } catch(err) {}
    applyTheme(saved);
}

function setRadioValue(groupName, value) {
    const target = String(value);
    const radio = document.querySelector(`input[name="${groupName}"][value="${target}"]`);
    if (radio) {
        radio.checked = true;
    }
}

function getRadioValue(groupName) {
    const checked = document.querySelector(`input[name="${groupName}"]:checked`);
    return checked ? checked.value : '';
}

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
                } else if (key == 'sample_rate' || key == 'bit_depth') {
                    setRadioValue(key, value);
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
    const states = ['standby', 'start', 'run', 'stop'];
    states.forEach(state => {
        const node = document.getElementById(state);
        if (node) {
            node.classList.toggle('is-active', state === status);
        }
    });

    const root = document.getElementById('container');
    if (root) {
        root.classList.toggle('is-recording', status === 'run');
    }
}

function set_settings() {

    let data = {
        "sample_rate" : getRadioValue('sample_rate'),
        "bit_depth" : getRadioValue('bit_depth'),
        "file_limit" : document.getElementById('file_limit').value,
    }
    data = JSON.stringify(data)

    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            data = JSON.parse(xhttp.responseText)
            for (const [key, value] of Object.entries(data)) {
                if (key == 'sample_rate' || key == 'bit_depth') {
                    setRadioValue(key, value);
                    continue;
                }
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

// Function to populate the log textarea
async function populateLog() {
    var textarea = document.getElementById("log");
    try {
        var response = await fetch('get_log');
        var logData = await response.text();
        textarea.value = logData;        
        setTimeout(function () {
            textarea.scrollTop = textarea.scrollHeight;
          }, 100); // Add a slight delay to allow rendering before scrolling down
    } catch (error) {
        console.error('Error fetching log data:', error);
        textarea.value = 'Error fetching log data:' + error;

    }
  }


// Get the content element by its id
var container = document.getElementById('container');

// Get all the menu items
var menuItems = document.querySelectorAll('.nav-link');

// Attach event listener to each menu item
menuItems.forEach(function(item) {
    item.addEventListener('click', function() {
        if (item.id == "pills-status-tab") {
            update = true;
        }
        if (item.id == "pills-schedule-tab") {
            update = false;    
        }
        if (item.id == "pills-admin-tab") {
            update = false;    
        }
        if (item.id == "pills-log-tab") {
            update = false;    
        }
    });
});


initTheme();
get_data();
