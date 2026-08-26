async function analyzeText() {
    const text = document.getElementById('activityText').value;
    if (!text.trim()) {
        alert('Please describe your daily activities.');
        return;
    }

    try {
        const response = await fetch('http://localhost:5000/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        const data = await response.json();
        displayResults(data);
    } catch (error) {
        console.error('Error:', error);
        alert('Error connecting to the backend server.');
    }
}

function displayResults(data) {
    document.getElementById('results').style.display = 'block';
    document.getElementById('totalCO2').textContent = data.total_co2_kg;
    document.getElementById('benchmarkMsg').textContent = data.benchmark.message;

    const breakdownList = document.getElementById('breakdownList');
    breakdownList.innerHTML = '';

    if (data.breakdown && data.breakdown.length > 0) {
        data.breakdown.forEach(item => {
            const div = document.createElement('div');
            div.className = 'breakdown-item';
            div.innerHTML = `
                <div>
                    <strong>${item.activity}</strong>
                    <span class="category-badge">${item.category}</span>
                </div>
                <span class="co2-val">${item.co2_kg} kg</span>
            `;
            breakdownList.appendChild(div);
        });
    } else {
        breakdownList.innerHTML = '<p style="text-align:center; color:#888;">No recognizable activities found. Try: "I drove my car 20 km"</p>';
    }
}