// Sample data for CENRO Activity Logs
// This array can be used to populate the activity logs table dynamically with JavaScript

const sampleActivityLogs = [
    {
        task: "User Login",
        user_id: "1001",
        name: "John Doe",
        timestamp: "2023-10-01T08:30:00Z"
    },
    {
        task: "File Upload",
        user_id: "1002",
        name: "Jane Smith",
        timestamp: "2023-10-01T09:15:00Z"
    },
    {
        task: "Data Export",
        user_id: "1003",
        name: "Bob Johnson",
        timestamp: "2023-10-01T10:45:00Z"
    },
    {
        task: "Profile Update",
        user_id: "1004",
        name: "Alice Brown",
        timestamp: "2023-10-01T11:20:00Z"
    },
    {
        task: "System Backup",
        user_id: "1005",
        name: "Charlie Wilson",
        timestamp: "2023-10-01T12:00:00Z"
    },
    {
        task: "Password Reset",
        user_id: "1006",
        name: "Diana Davis",
        timestamp: "2023-10-01T13:30:00Z"
    },
    {
        task: "Report Generation",
        user_id: "1007",
        name: "Edward Miller",
        timestamp: "2023-10-01T14:45:00Z"
    },
    {
        task: "Account Creation",
        user_id: "1008",
        name: "Fiona Garcia",
        timestamp: "2023-10-01T15:10:00Z"
    },
    {
        task: "User Logout",
        user_id: "1009",
        name: "George Taylor",
        timestamp: "2023-10-01T16:25:00Z"
    },
    {
        task: "Database Update",
        user_id: "1010",
        name: "Helen Anderson",
        timestamp: "2023-10-01T17:00:00Z"
    }
];

// Example function to populate the table with sample data
function populateActivityLogsTable() {
    const tableBody = document.querySelector('.activity-table tbody');

    if (!tableBody) {
        console.error('Activity logs table not found');
        return;
    }

    // Clear existing rows except the "No activity logs found" row if present
    tableBody.innerHTML = '';

    if (sampleActivityLogs.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="4" style="padding: 20px; border: 1px solid #ccc; text-align: center">
                    No activity logs found.
                </td>
            </tr>
        `;
        return;
    }

    // Populate table with sample data
    sampleActivityLogs.forEach(log => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td style="padding: 10px; border: 1px solid #ccc">${log.task}</td>
            <td style="padding: 10px; border: 1px solid #ccc">${log.user_id}</td>
            <td style="padding: 10px; border: 1px solid #ccc">${log.name}</td>
            <td style="padding: 10px; border: 1px solid #ccc">${log.timestamp}</td>
        `;
        tableBody.appendChild(row);
    });
}

// Call the function when the page loads (optional)
// document.addEventListener('DOMContentLoaded', populateActivityLogsTable);
