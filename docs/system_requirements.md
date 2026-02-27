# Azure Agentic Weather App

## Requirements and Architecture Document

### 1. Project Overview

#### 1.1 Objective

The objective of this project is to design and implement a full-stack, agent-driven web application that integrates:

- The Weatherstack REST API.
- A microservice wrapper (MCP Server).
- An LLM agent with tool/function-calling capability.
- A frontend interface for user interaction.

The system must demonstrate clean architectural separation, proper agent orchestration, and structured tool invocation.

---

### 2. Functional Requirements

#### 2.1 Public API Integration

The system must:

- Integrate with the Weatherstack REST API.
- Securely store and manage API keys via environment variables.
- Retrieve structured JSON data from the API.
- Handle API errors gracefully.

---

#### 2.2 MCP Server (Microservice Wrapper)

The MCP Server must:

- Be implemented as an independent microservice.
- Expose REST endpoints that abstract the Weatherstack API.
- Validate incoming parameters.
- Handle external API communication.
- Return normalized JSON responses.
- Prevent direct exposure of the Weatherstack API key.

The MCP server must be independently runnable.

---

#### 2.3 LLM Agent Backend

The agent backend must:

- Utilize an LLM capable of tool/function calling.
- Define at least one tool schema corresponding to MCP functionality.
- Allow the LLM to decide when to invoke the tool.
- Execute tool calls via HTTP requests to the MCP server.
- Format final responses for user display.
- Handle invalid tool calls and execution errors.

---

#### 2.4 Frontend Web Application

The frontend must:

- Provide a user input field.
- Submit user queries to the agent backend.
- Display responses returned by the agent.
- Handle loading and error states.

The frontend does not require advanced styling or authentication.

---

### 3. Non-Functional Requirements

#### 3.1 Architecture

The system must demonstrate:

- Clean separation of concerns.
- Microservice-based structure.
- Logical code organization.
- Environment variable configuration.

---

#### 3.2 Maintainability

The codebase must:

- Use descriptive function and variable names.
- Include inline comments for complex logic.
- Provide a well-structured repository layout.
- Include setup instructions in the README.

---

#### 3.3 Scalability (Conceptual)

The solution must allow for future:

- Containerization via Docker.
- Independent scaling of services.
- Additional tool/plugin integration.
- Cloud deployment.

---

### 4. System Architecture

#### 4.1 High-Level Architecture

```
Frontend (Web App)
        ↓
LLM Agent Backend
        ↓
MCP Server (Wrapper)
        ↓
Public REST API
```

---

#### 4.2 Component Responsibilities

| **Component**    | **Responsibility**                       |
| ---------------- | ---------------------------------------- |
| Frontend         | Collect user input and display results   |
| LLM Agent        | Orchestrate conversation and tool calls  |
| MCP Server       | Abstract external API and normalize data |
| Weatherstack API | Provide weather data                     |

---

### 5. Tool Definition Requirements

The system must define:

- A structured tool schema.
- Clear input parameter definitions.
- Human-readable tool description.
- JSON-based output.

The agent must invoke tools deterministically via function calling rather than relying on free-from text prompting

---

### 6. Security Requirements

- API keys must not be hard-coded.
- Environment variables must be used.
- The MCP server must act as the only service communicating with the Weatherstack API.

---

### 7. Repository Structure

Example Structure:

```
/frontend
/agent-backend
/mcp-server
/docs
README.md
requirements.txt
.env.example
```

---

### 8. Deployment Considerations (Conceptual)

The system should be deployable using:

- Docker containers (one per service).
- Cloud container hosting (e.g., Azure Container Apps).
- Environment-based configuration.

Each service should be independently deployable.

---

### 9. Documentation Requirements

The repository must include:

- Setup instructions.
- Environment variable configuration.
- API key acquisition instructions.
- Instructions for running each service locally.
