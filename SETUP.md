# Quick Setup Guide

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/nl2sql-gemini.git
cd nl2sql-gemini
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure the Application
```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` with your settings:
- Add your PostgreSQL database credentials
- Add your Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

### 4. Set Up Test Database (Optional)
```bash
chmod +x setup_database.sh
./setup_database.sh
```

### 5. Run the Application
```bash
python app.py
```

Visit `http://localhost:3001` and start querying your database in natural language!

## 🔑 Required Credentials

- **PostgreSQL Database**: Connection details (host, username, password, database)
- **Gemini API Key**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)

## 🎯 Example Queries

- "Show me all users"
- "List products that are out of stock"
- "How many orders were placed this month?"
- "Find the top 5 customers by order count"