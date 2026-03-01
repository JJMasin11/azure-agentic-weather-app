# Azure Agentic Weather App

A full-stack agent-driven web application that integrates the Weatherstack API through a Microservice Communication Proxy (MCP Server) and an LLM backend with structured tool calling.

---

### Prerequisites

**Software:**

- Python 3.10+
- Git

**Accounts:**

- Azure account (for Azure AI Foundry Access)

---

### 1. Clone the Repository

```
git clone https://github.com/JJMasin11/azure-agentic-weather-app
cd azure-agentic-weather-app
```

---

### 2. Install Dependencies

All dependencies and their respective versions are listed in `requirements.txt`. Simply run:

```
python -m venv venv
source venv/bin/activate    # Mac/Linux
venv\Scripts\Activate.bat   # Windows
pip install -r requirements.txt
```

---

### 3. Obtain Required API Keys

This project requires:

#### Weatherstack API Key

1. Visit: [https://weatherstack.com/](https://weatherstack.com/)
2. Create a free account
3. Generate an API key

#### Azure AI Foundry Credentials

This project uses Azure AI Foundry to access an LLM with tool-calling capability.

**Step 1 - Create an Azure AI Foundry Project**

1. Sign in to the Azure Portal.
2. Navigate to Azure AI Foundry.
3. Create or select an existing AI Project.
4. Deploy a model that supports function/tool calling (e.g., GPT-4o or equivalent).

**Step 2 - Retrieve Required Values**

From your Azure AI Foundry project, collect:

- AZURE_AI_SERVICES_ENDPOINT
- AZURE_AI_API_KEY
- AZURE_API_VERSION
- MODEL_DEPLOYMENT_NAME

These values can be found under:

- "Keys and Endpoint"
- Your deployed model configuration

---

### 4. Configure Environment Variables

Create a copy of `.env.example` in the project root and name it `.env`. Copy and paste all API keys and information into `.env`.

Do not commit `.env` files to version control.

---

### 5. Run the Application

#### Quick Start (Recommended)

Run the unified entrypoint scripts:

```
python main.py
```

This will:

- Start the MCP server on `http://localhost:8000`.
- Start the LLM Agent Backend on `http://localhost:8001`.
- Start the Frontend on `http://localhost:8501`.

Open your browser and navigate to:

```
http://localhost:8501
```

#### Manual Startup (Optional)

If you prefer to start the services individually:

**Start MCP Server**

```
cd mcp-server
python mcp_server.py
```

**Start Agent Backend**

```
cd agent-backend
python agent_server.py
```

**Start Frontend**

```
cd frontend
streamlit run app.py
```

---

### Project Structure

```
.
├── docs/              # System requirements document
├── frontend/          # Web UI
├── agent_backend/     # LLM agent with tool calling
├── mcp_server/        # API wrapper microservice
├── main.py            # Unified entrypoint
├── requirements.txt
├── .env.example
└── README.md
```
