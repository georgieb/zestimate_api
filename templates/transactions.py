<!-- templates/transactions.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nearby Transactions</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .transaction-card {
            margin-bottom: 1rem;
            transition: transform 0.2s;
        }
        .transaction-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .stats-card {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
    </style>
</head>
<body>
    <div class="container mt-4">
        <h1 class="mb-4">Nearby Property Transactions</h1>
        
        <!-- Search Form -->
        <div class="card mb-4">
            <div class="card-body">
                <form id="searchForm">
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label for="address" class="form-label">Address</label>
                            <input type="text" class="form-control" id="address" required>
                        </div>
                        <div class="col-md-3 mb-3">
                            <label for="radius" class="form-label">Radius (miles)</label>
                            <input type="number" class="form-control" id="radius" value="0.5" step="0.1" min="0.1">
                        </div>
                        <div class="col-md-3 mb-3">
                            <label for="limit" class="form-label">Number of Results</label>
                            <input type="number" class="form-control" id="limit" value="10" min="1" max="50">
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">Search</button>
                </form>
            </div>
        </div>

        <!-- Summary Statistics -->
        <div id="summary" class="stats-card d-none">
            <h3>Summary Statistics</h3>
            <div class="row">
                <div class="col-md-3">
                    <p><strong>Total Transactions:</strong> <span id="totalTransactions"></span></p>
                </div>
                <div class="col-md-3">
                    <p><strong>Average Price:</strong> <span id="averagePrice"></span></p>
                </div>
                <div class="col-md-3">
                    <p><strong>Average Sq Ft:</strong> <span id="averageSquareFeet"></span></p>
                </div>
                <div class="col-md-3">
                    <p><strong>Avg Price/Sq Ft:</strong> <span id="averagePricePerSqFt"></span></p>
                </div>
            </div>
        </div>

        <!-- Transactions List -->
        <div id="transactionsList" class="row"></div>
    </div>

    <script>
        document.getElementById('searchForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const address = document.getElementById('address').value;
            const radius = document.getElementById('radius').value;
            const limit = document.getElementById('limit').value;
            
            try {
                const response = await fetch(`/api/nearby-transactions?address=${encodeURIComponent(address)}&radius=${radius}&limit=${limit}`);
                const data = await response.json();
                
                if (response.ok) {
                    displayResults(data);
                } else {
                    alert(data.error || 'Error fetching transactions');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error fetching transactions');
            }
        });

        function displayResults(data) {
            // Display summary
            document.getElementById('summary').classList.remove('d-none');
            document.getElementById('totalTransactions').textContent = data.summary.totalTransactions;
            document.getElementById('averagePrice').textContent = formatCurrency(data.summary.averagePrice);
            document.getElementById('averageSquareFeet').textContent = formatNumber(data.summary.averageSquareFeet) + ' sq ft';
            document.getElementById('averagePricePerSqFt').textContent = formatCurrency(data.summary.averagePricePerSqFt) + '/sq ft';

            // Display transactions
            const transactionsList = document.getElementById('transactionsList');
            transactionsList.innerHTML = '';
            
            data.transactions.forEach(transaction => {
                const card = document.createElement('div');
                card.className = 'col-md-6 col-lg-4';
                card.innerHTML = `
                    <div class="card transaction-card">
                        <div class="card-body">
                            <h5 class="card-title">${formatCurrency(transaction.salesPrice)}</h5>
                            <h6 class="card-subtitle mb-2 text-muted">${transaction.address}</h6>
                            <p class="card-text">
                                <strong>Date:</strong> ${formatDate(transaction.recordingDate)}<br>
                                <strong>Square Feet:</strong> ${formatNumber(transaction.squareFeet)}<br>
                                <strong>Price/Sq Ft:</strong> ${formatCurrency(transaction.pricePerSqFt)}/sq ft<br>
                                <strong>Type:</strong> ${transaction.documentType}<br>
                                ${transaction.buyerName ? `<strong>Buyer:</strong> ${Array.isArray(transaction.buyerName) ? transaction.buyerName.join(', ') : transaction.buyerName}<br>` : ''}
                                ${transaction.sellerName ? `<strong>Seller:</strong> ${Array.isArray(transaction.sellerName) ? transaction.sellerName.join(', ') : transaction.sellerName}` : ''}
                            </p>
                        </div>
                    </div>
                `;
                transactionsList.appendChild(card);
            });
        }

        function formatCurrency(value) {
            if (!value) return 'N/A';
            return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
        }

        function formatNumber(value) {
            if (!value) return 'N/A';
            return new Intl.NumberFormat('en-US').format(value);
        }

        function formatDate(dateString) {
            if (!dateString) return 'N/A';
            return new Date(dateString).toLocaleDateString('en-US');
        }
    </script>
</body>
</html>