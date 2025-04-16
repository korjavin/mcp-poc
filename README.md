# Telegram Bot with OpenAI and Google Calendar Integration

This project implements a Telegram bot that allows users to interact with their Google Calendar using natural language commands. It leverages OpenAI for understanding requests and integrates directly with the Google Calendar API using Google's Python client libraries for authentication and interaction. The application is designed to be deployed using Docker Compose (or Podman Compose).

## Features

*   Natural language interaction with Google Calendar via Telegram.
*   Uses OpenAI (GPT models) for intent recognition and parameter extraction.
*   Connects directly to the Google Calendar API using official Google client libraries.
*   Handles user-specific Google OAuth2 authentication flow within the bot.
*   Containerized deployment using Docker Compose.

## Architecture

The bot service handles all logic: Telegram communication, OpenAI calls, Google OAuth flow (including a callback endpoint), credential storage, and direct Google Calendar API interaction.

```mermaid
graph TD
    subgraph User Interaction
        User([User]) -- Telegram Message --> TelegramBot[Telegram Bot (Python Service)]
        TelegramBot -- Formatted Response --> User
    end

    subgraph Bot Logic
        TelegramBot -- User Message + Tool Schema --> OpenAI{OpenAI API}
        OpenAI -- Tool Call Instruction --> TelegramBot
        TelegramBot -- Executes Instruction --> CalendarAccess{Direct Google API Call}
        CalendarAccess -- Result --> TelegramBot
        TelegramBot -- Stores/Retrieves Token --> UserDB[(User Auth Tokens - Pickle Files)]
        User -- OAuth2 Flow --> AuthHandler{Bot's OAuth Handler}
        AuthHandler -- Handles Callback & Token Exchange --> GoogleOAuth[Google OAuth Endpoints]
        CalendarAccess -- Google API Call (with User Token) --> GoogleAPI[Google Calendar API]
    end

    subgraph Deployment
        Compose[docker-compose.yml] --> TelegramBot
        HostEnv[.env File] -- Reads Variables --> TelegramBot
        TokensVolume[Volume: bot_token_storage] -- Persists Tokens --> UserDB
    end
```

## Prerequisites

*   Docker and Docker Compose (or Podman and Podman Compose)
*   Git
*   A Google Account and a Google Cloud Project
*   A Telegram Bot Token
*   An OpenAI API Key

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url>
    cd telegram-cal-bot
    ```

2.  **Google Cloud Project & OAuth Setup:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project (or use an existing one).
    *   Enable the **Google Calendar API** for your project.
    *   Go to "APIs & Services" -> "Credentials".
    *   Click "Create Credentials" -> "OAuth client ID".
    *   Select "Web application" as the application type.
    *   Give it a name (e.g., "Telegram Bot Calendar Access").
    *   Under "Authorized redirect URIs", add the URI(s) required by the authentication flow. Based on the `docker-compose.yml` and `.env.example`:
        *   For the MCP Server: `http://localhost:3000/auth/callback`
        *   *(If using fallback)* For the Bot: `http://localhost:8080/callback` (Adjust port if changed)
        *   *Important:* Ensure these match the `GOOGLE_REDIRECT_URI` in your `.env` file.
    *   Click "Create".
    *   You will need the Client ID, Client Secret, Project ID, Auth URI, and Token URI from the downloaded `credentials.json` file to populate the `.env` file in the next step. **Do not commit the downloaded JSON file or the `.env` file.**

3.  **Configure Environment Variables:**
    *   Create a `.env` file in the project root by copying the example:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and fill in your actual values for:
        *   `TELEGRAM_BOT_TOKEN`
        *   `OPENAI_API_KEY`
        *   `GOOGLE_PROJECT_ID` (from the downloaded `credentials.json`)
        *   `GOOGLE_AUTH_URI` (usually `https://accounts.google.com/o/oauth2/auth`)
        *   `GOOGLE_TOKEN_URI` (usually `https://oauth2.googleapis.com/token`)
        *   `GOOGLE_AUTH_PROVIDER_X509_CERT_URL` (usually `https://www.googleapis.com/oauth2/v1/certs`)
        *   `GOOGLE_CLIENT_ID` (from the downloaded `credentials.json` or Cloud Console)
        *   `GOOGLE_CLIENT_SECRET` (from the downloaded `credentials.json` or Cloud Console)
        *   `GOOGLE_REDIRECT_URI` (ensure this matches *exactly* one of the URIs registered in step 2 and the port exposed by the bot in `docker-compose.yml`, e.g., `http://localhost:8080/callback`)

4.  **Build and Run with Docker Compose:**
    ```bash
    # Using Docker Compose
    *   Clone the repository into the `mcp/` directory:
        ```bash
        git clone https://github.com/Jackson88/google-calendar-mcp.git mcp
        ```
    # Using Podman Compose
    ```bash
    # Using Docker Compose
    docker-compose up --build -d

    # Using Podman Compose
    podman-compose up --build -d
    ```

## Usage

1.  **Start a Chat:** Find your bot on Telegram and send the `/start` command.
2.  **Authorize Google Calendar:** Use the `/auth` command. The bot will provide a link. Open the link in your browser, log in to your Google account, and grant the requested permissions. You should be redirected back to a page confirming success, and the bot should send you a confirmation message in Telegram.
3.  **Interact:** Once authorized, you can send natural language commands like:
    *   "What's on my calendar tomorrow?"
    *   "Schedule a meeting with Roo on Friday at 2 PM for 1 hour called 'MCP Project Sync'"
    *   "Do I have anything scheduled next Monday morning?"

## Development

*(Add details about running locally, testing, etc., later)*

## Troubleshooting

*   **ERR_CONNECTION_REFUSED / ERR_EMPTY_RESPONSE on callback:** Ensure the `GOOGLE_REDIRECT_URI` in your `.env` file uses the correct port (default `8080`) and matches the `ports` section in `docker-compose.yml`. Also ensure the URI is registered in your Google Cloud Console project.
*   **Authentication errors after successful auth:** Check bot logs (`podman-compose logs bot`). Ensure the `bot_token_storage` volume is working correctly and token files (`*.pickle`) are being created/updated in the volume on your host machine. You might need to re-authenticate using `/auth`.
*   **"Is a directory" error on startup:** This was related to volume mounting conflicts. The current setup (copying code via Dockerfile, no code volume mount) should prevent this. Ensure `docker-compose.yml` does *not* mount `./bot:/app`.

---

*This README reflects the implementation using direct Google API integration within the bot.*