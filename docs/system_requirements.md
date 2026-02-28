# Azure Agentic Weather App

## Requirements and Architecture Document

### 1. Project Overview

#### 1.1 Objective

The objective of this project is to design and implement a full-stack, agent-driven web application that retrieves real-time weather data using a structured LLM tool-calling architecture.

The system integrates:

- The Weatherstack REST API.
- A Microservice Communication Proxy (MCP Server)
- An LLM agent backend with structured function-calling capability
- A frontend web interface for user interaction.

The solution must demonstrate clean architectural separation, deterministic tool invocation, normalized data handling, and production-aware design principles.

---

### 2. Functional Requirements

#### 2.1 Public API Integration

The system must integrate with the Weatherstack `/current` endpoint to retrieve real-time weather data.

The integration must:

- Store API keys securely using environment variables.
- Send properly formatted HTTP requests.
- Parse structured JSON responses.
- Handle the following external API errors:
  - 4xx client errors.
  - 5xx server errors.
  - Network timeouts.
  - Invalid location responses.

The system must not expose the Weatherstack API's key to any external service.

---

#### 2.2 MCP Server (Microservice Wrapper)

The MCP Server must be implemented as an independent microservice responsible for abstracting and normalizing Weatherstack API communication.

#### Endpoint Contract

The MCP server must expose:

`GET /weather?location=<city>`

#### Parameter Validation

- `location` must be a non-empty string.
- Return HTTP 400 for missing or invalid parameters.

#### Responsibilities

The MCP server must:

- Communicate securely with the Weatherstack `/current` endpoint.
- Normalize external API responses into a consistent internal schema.
- Prevent exposure of API credentials.
- Be independently runnable.
- Log incoming requests and external API failures.

#### Normalized JSON Response

The MCP server must return responses in the following structure:

```
{
    "location": "Austin",
    "temperature": 72,
    "feels_like": 75,
    "humidity": 65,
    "wind_speed": 10,
    "wind_direction": "NW",
    "weather_description": "Partly cloudy",
    "uv_index": 5,
    "visibility": 10,
    "cloud_cover": 40
}
```

#### Error Handling

The MCP server must:

- Return 400 for invalid request parameters.
- Return 404 if the requested location is not found.
- Return 502 if the external API fails or times out.
- Return structured JSON error responses:

```
{
    "error": "Location not found"
}
```

#### Service Boundary

The MCP server must be the only service permitted to communicate with the Weatherstack API.

---

#### 2.3 LLM Agent Backend

The LLM Agent Backend must orchestrate user queries and structured tool invocation.

#### Model Requirements

The agent must:

- Utilize an LLM that supports structured function/tool calling.
- Be configured with low temperature (≤ 0.3) to promote deterministic behavior.
- Rely on structured tool-call responses rather than parsing free-form text.

#### Tool Definition

The system must define at least one tool:

**Tool Name**: `get_current_weather`

**Parameters**:

- `location` (string, required)

The tool must correspond to the MCP server endpoint.

#### Agent Behavior

The agent must:

- Analyze user queries.
- Determine when to invoke the weather tool.
- Generate structured tool-call JSON.
- Execute HTTP requests to the MCP server.
- Parse tool responses.
- Format user-facing responses.

#### Query Handling Rules

**1. General Weather Queries**

Example: "What's the weather in Austin?"

- Must call the weather tool.
- Must return a concise summary including temperature and weather description.

**2. Specific Attribute Queries**

Example: "What's the wind speed in Austin?"

- Must call the weather tool.
- Must extract and return only the requested attribute when possible.

**3. Out-of-Scope Queries**

If a query is unrelated to weather:

- The agent must respond that it is specialized for weather-related queries.

**4. Condition-Based Advisories**

After a successful weather tool invocation, the agent must evaluate environmental conditions and determine whether one or more advisories should be issued.

Advisory decisions must be derived from the LLM-based contextual reasoning and must not rely on hard-coded numeric thresholds.

The agent must support the following advisory categories:

**Heat Risk Advisory**

Must consider:

- Temperature
- Feels Like
- Humidity

If elevated head conditions are detected, the agent must:

- Classify severity level.
- Provide a concise explanation.
- Provide recommended precautionary action.

**Cold Risk Advisory**

Must consider:

- Feels Like
- Wind Speed

If hazardous cold conditions are detected, the agent must:

- Classify severity level.
- Provide a concise explanation.
- Provide recommended precautionary action.

**Wind Hazard Advisory**

Must consider:

- Wind Speed
- Weather Description

If hazardous wind conditions are detected, the agent must:

- Classify severity level.
- Provide a concise explanation.
- Provide recommended precautionary action.

**Driving Conditions Advisory**

Must consider:

- Visibility
- Wind Speed
- Weather Description

If unsafe driving conditions are detected, the agent must:

- Classify driving conditions.
- Provide a concise explanation.
- Provide recommended precautionary action.

Multiple advisories may be issued simultaneously if multiple risk conditions are identified.

Advisory evaluation must be performed using the same structured weather response returned by the MCP server.

#### Error Handling

The agent must handle:

- Invalid tool-call arguments.
- MCP server errors.
- Unexpected execution failures.
- Malformed LLM tool responses

User-facing error responses must be clear and concise.

---

#### 2.4 Frontend Web Application

The frontend must:

- Provide a user input field.
- Submit user queries to the LLM agent backend.
- Display structured responses.
- Display loading states.
- Display user-friendly error messages.

The frontend does not require advanced styling or authentication.

The frontend must not have access to any API keys.

---

### 3. Non-Functional Requirements

#### 3.1 Architecture

The system must demonstrate:

- Clean separation of concerns.
- Microservice-based structure.
- Logical code organization.
- Environment variable configuration.
- Strict service boundaries.

---

#### 3.2 Maintainability

The codebase must:

- Use descriptive function and variable names.
- Include inline comments for complex logic.
- Follow consistent naming conventions.
- Include setup and configuration instructions in the README.
- Provide an `.env.example` file.

---

#### 3.3 Observability

The backend service must log:

- Incoming user queries.
- Tool invocation attempts.
- MCP server responses.
- External API errors.
- Unexpected execution failures.

#### 3.4 Scalability (Conceptual)

The architecture must allow for future:

- Independent scaling of frontend, agent backend, and MCP server.
- Additional tool/plugin integration.
- Containerization via Docker.
- Cloud deployment using Azure Container Apps or similar services.

---

### 4. System Architecture

#### 4.1 High-Level Flow

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

| **Component**    | **Responsibility**                           |
| ---------------- | -------------------------------------------- |
| Frontend         | Collect user input and display results       |
| LLM Agent        | Interpret queries and orchestrate tool calls |
| MCP Server       | Abstract external API and normalize data     |
| Weatherstack API | Provide raw weather data                     |

---

### 5. Tool Invocation Requirements

The system must:

- Use structured function calling.
- Avoid free-form text-based tool extraction.
- Ensure deterministic tool invocation behavior.
- Maintain a clear schema contract between agent and MCP server.

---

### 6. Security Requirements

- API keys must not be hard-coded.
- Environment variables must be use for configuration.
- The MCP server must be the only service communicating with the Weatherstack API.
- The frontend must never have access to backend credentials.
- Secrets must not be committed to source control.

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

Each service must be independently runnable.

---

### 8. Deployment Considerations (Conceptual)

The system should be deployable using:

- Docker containers (one per service).
- Azure Container Apps or equivalent container hosting.
- Environment-based configuration.
- Independent service deployment.

---

### 9. Documentation Requirements

The repository must include:

- Setup instructions.
- Environment variable configuration steps.
- API key acquisition instructions.
- Instructions for running each service locally.
