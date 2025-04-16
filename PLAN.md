# Plan: Telegram Bot with OpenAI and Google Calendar Integration via MCP

**Project Goal:** Create a Telegram bot that allows users to interact with their Google Calendar using natural language. The interaction will be facilitated by OpenAI's function-calling/tool-use capabilities, connecting to Google Calendar primarily via an external MCP server, with a fallback to direct Google API integration if needed. The entire application will be containerized using Docker Compose for easy deployment on a remote server using Podman Compose.

**Core Components:**

1.  **Telegram Bot (Python):** Handles user interaction (via `python-telegram-bot`), manages user-specific Google OAuth authentication, interacts with the OpenAI API, and orchestrates calls to the Google Calendar functionality.
2.  **OpenAI API:** Used for natural language understanding (interpreting user requests) and determining *which* calendar action (tool) to execute and with what parameters.
3.  **Google Calendar Access:**
    *   **Primary Approach:** Utilize the external `google-calendar-mcp` server ([https://github.com/Jackson88/google-calendar-mcp](https://github.com/Jackson88/google-calendar-mcp)), running as a separate service in Docker Compose. The bot will interact with this server's MCP endpoints.
    *   **Fallback Approach:** If the external MCP server proves unsuitable for multi-user authentication or other issues arise, integrate Google's official Python client library (`google-api-python-client`, `google-auth-oauthlib`) directly within the Telegram bot code. The bot will manage tokens and expose calendar functions as internal "tools" to OpenAI.
4.  **Docker Compose:** Defines and runs the application services: the Telegram bot and the `google-calendar-mcp` server. Manages networking, volumes, and environment variables.

**Architecture Diagram:**

```mermaid
graph TD
    subgraph User Interaction
        User([User]) -- Telegram Message --> TelegramBot[Telegram Bot (Python Service)]
        TelegramBot -- Formatted Response --> User
    end

    subgraph Bot Logic
        TelegramBot -- User Message + Tool Schema --> OpenAI{OpenAI API}
        OpenAI -- Tool Call Instruction --> TelegramBot
        TelegramBot -- Executes Instruction --> CalendarAccess{Calendar Access Logic}
        CalendarAccess -- Result --> TelegramBot
        TelegramBot -- Stores/Retrieves Token --> UserDB[(User Auth Tokens / Session State)]
        User -- OAuth2 Flow --> AuthHandler{Auth Handler (in Bot or MCP)}
    end

    subgraph Calendar Access Options
        subgraph "Primary: External MCP"
            CalendarAccess -- MCP Request --> ExternalMCP[google-calendar-mcp Service]
            ExternalMCP -- Google API Call --> GoogleAPI[Google Calendar API]
            AuthHandler -- Redirects User --> ExternalMCPAuth{MCP Auth Endpoints}
            ExternalMCPAuth -- Handles OAuth --> GoogleAPI
        end
        subgraph "Fallback: Internal Client"
            CalendarAccess -- Direct Call (with User Token) --> InternalClient[Google Client Lib (in Bot)]
            InternalClient -- Google API Call --> GoogleAPI
            AuthHandler -- Handles OAuth --> InternalClient
        end
    end

    subgraph Deployment
        Compose[docker-compose.yml] --> TelegramBot
        Compose -- Defines & Links --> ExternalMCP
        HostEnv[.env File] -- Reads Variables --> Compose
        Credentials[credentials.json] -- Mounted --> Bot/MCP
        TokensVolume[Volume] -- Persists Tokens --> Bot/MCP
    end

    style "Fallback: Internal Client" fill:#f9f,stroke:#333,stroke-width:1px,opacity:0.6
    note right of "Fallback: Internal Client" Fallback if External MCP is unsuitable
```

**Detailed Implementation Steps:**

1.  **Project Setup:**
    *   Create the main project directory (e.g., `telegram-cal-bot`).
    *   Initialize Git: `git init`.
    *   Create `.gitignore` (include `.env`, `credentials.json`, `token_storage/`, `__pycache__/`, `*.pyc`, etc.).
    *   Create subdirectories: `bot/` (for Python bot code), potentially `mcp/` if cloning the MCP server locally for modifications or inspection.
    *   Create initial files:
        *   `bot/requirements.txt`: (`python-telegram-bot[ext]`, `openai`, `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`, `python-dotenv`, `requests` (for MCP calls)).
        *   `bot/Dockerfile`: To containerize the bot.
        *   `docker-compose.yml`: Defines `bot` and `google-calendar-mcp` services.
        *   `README.md`: Project documentation.
        *   `.env.example`: Template for `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` (likely `http://localhost:PORT/callback` or similar, matching MCP/bot config), `MCP_SERVER_URL` (e.g., `http://google-calendar-mcp:3000`).
        *   Instructions in `README.md` on where to place `credentials.json`.

2.  **Google OAuth Setup:**
    *   Document steps in `README.md` for creating Google Cloud Project, enabling Calendar API, creating OAuth 2.0 Client ID (Web Application), and downloading `credentials.json`. Emphasize setting the correct redirect URI(s) in Google Cloud Console (one for the MCP server's callback, potentially one for the bot's fallback).

3.  **External MCP Server Setup (`docker-compose.yml`):**
    *   Define a service for `google-calendar-mcp`.
    *   Use its official Docker image if available, otherwise include instructions to clone its repo and build it via Docker Compose.
    *   Configure its environment variables (`AUTH_METHOD=google_cloud`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `PORT`).
    *   Map the necessary port (e.g., 3000).
    *   Define a volume for its token storage if it persists tokens to disk.
    *   Ensure the bot service can reach it via Docker networking (e.g., using the service name `google-calendar-mcp`).

4.  **Telegram Bot Implementation (`bot/`):**
    *   **Core:** Use `python-telegram-bot` (`ApplicationBuilder`, `CommandHandler`, `MessageHandler`, `filters`).
    *   **Configuration:** Load environment variables (`.env`).
    *   **Authentication Flow (Primary - MCP):**
        *   Create a command (e.g., `/auth`) that initiates the flow.
        *   Fetch the auth URL from the MCP server (`GET MCP_SERVER_URL/mcp/auth/url`).
        *   Send this URL to the user.
        *   *Crucially:* The MCP server needs to handle the callback (`/mcp/auth/callback`) and associate the resulting token/session with the *initial request context* or provide a way for the bot to know which user completed the flow. This might require modification or careful handling if the MCP server wasn't designed for this specific multi-user bot scenario. The bot might need to pass a unique `state` parameter to the auth URL and verify it on callback if the MCP supports it.
        *   Store confirmation that the user is authenticated (e.g., in a simple dictionary or file mapping `telegram_user_id` to `True`).
    *   **Authentication Flow (Fallback - Internal):**
        *   Implement the OAuth flow using `google-auth-oauthlib.flow`.
        *   Run a simple web server (e.g., using `http.server` or Flask/FastAPI within the bot) temporarily or persistently to handle the `/callback` redirect from Google.
        *   Store the obtained `Credentials` object (containing refresh token) securely per `telegram_user_id` (e.g., serialize to a file in a persistent volume).
    *   **OpenAI Interaction:**
        *   Define the tool schema for calendar actions (`create_event`, `list_events`, etc.) matching the MCP server's capabilities or the internal functions.
        *   On receiving a user message, send it to OpenAI Chat Completions API (`gpt-4o`, `gpt-4-turbo`, etc.) with the defined tools.
    *   **Calendar Tool Execution:**
        *   If OpenAI response contains `tool_calls`:
            *   **Primary (MCP):** For each tool call, make the corresponding HTTP request (e.g., `POST`, `GET`) to the `MCP_SERVER_URL` endpoint (e.g., `MCP_SERVER_URL/mcp/events/create`). *Crucially*, the bot needs to pass authentication context (like a session cookie obtained post-auth, or potentially an access token if the MCP supports it per request) specific to the Telegram user making the request. This is the most complex part when using the external MCP.
            *   **Fallback (Internal):** Load the user's stored `Credentials`. Refresh the access token if necessary. Use the `googleapiclient.discovery.build` function to get a Calendar service object authenticated for that user. Call the appropriate service method (e.g., `service.events().insert(...)`).
        *   Format the result (success message, list of events, error) and send it back to the user via Telegram.
    *   **Error Handling:** Implement robust error handling for Telegram API errors, OpenAI API errors, Google API errors (or MCP server errors), network issues, and authentication failures.

5.  **Dockerization (`bot/Dockerfile`, `docker-compose.yml`):**
    *   **`bot/Dockerfile`:** Python base image, install `requirements.txt`, copy bot code, set entry point (`python main.py`).
    *   **`docker-compose.yml`:**
        *   Define `bot` service (build from `bot/Dockerfile`).
        *   Define `google-calendar-mcp` service (as described in step 3).
        *   Mount `credentials.json` into the appropriate service(s).
        *   Pass environment variables from host `.env` file.
        *   Define named volumes for persistent storage (e.g., `bot_token_storage`, `mcp_token_storage`).
        *   Configure depends_on if necessary.

6.  **README.md:**
    *   Detailed setup instructions (prerequisites, cloning, Google Cloud setup, Telegram Token, OpenAI Key, `.env` creation, `podman-compose up --build`).
    *   Explanation of the `/auth` command and the Google authorization process for users.
    *   Basic usage examples (natural language commands).
    *   Troubleshooting tips.
    *   Mention the fallback mechanism if applicable.

**Key Considerations & Risks:**

*   **MCP Multi-User Auth:** The primary risk is whether `google-calendar-mcp` handles concurrent authentication sessions for different users correctly without token conflicts. Testing this early is crucial. How does the bot associate an incoming Telegram message with the correct authenticated session/token on the MCP server? This might require careful session management or modifications to the MCP server.
*   **OAuth Callback Handling:** Implementing the callback receiver reliably within the bot (especially for the fallback) requires careful setup (running a web server, handling state).
*   **Token Storage Security:** Ensure token files/database are stored securely in a persistent volume with appropriate permissions.
*   **Rate Limits:** Be mindful of API rate limits (Telegram, OpenAI, Google).
*   **Complexity:** Integrating multiple external services and handling authentication securely adds complexity.

This plan prioritizes using the existing MCP server but acknowledges the potential need for the fallback, providing a structured approach to development.