# Telegram Bot with OpenAI and Google Calendar Integration (via MCP)

This project implements a Telegram bot that allows users to interact with their Google Calendar using natural language commands. It leverages OpenAI for understanding requests and Google Calendar access is primarily handled via the `google-calendar-mcp` server, with a fallback to direct Google API integration. The application is designed to be deployed using Docker Compose (or Podman Compose).

## Features

*   Natural language interaction with Google Calendar via Telegram.
*   Uses OpenAI (GPT models) for intent recognition and parameter extraction.
*   Connects to Google Calendar using the `google-calendar-mcp` server (primary) or Google's Python client library (fallback).
*   User-specific Google OAuth2 authentication.
*   Containerized deployment using Docker Compose.

## Architecture

*(Insert Mermaid diagram from PLAN.md here later)*

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
    *   Download the credentials JSON file. Rename it to `credentials.json` and place it in the root directory of this project. **Do not commit this file.**

3.  **Clone the MCP Server (if not using a pre-built image):**
    *   The current `docker-compose.yml` assumes you will build the MCP server from source.
    *   Clone the repository into the `mcp/` directory:
        ```bash
        git clone https://github.com/Jackson88/google-calendar-mcp.git mcp
        ```
    *   *(If a reliable Docker image becomes available, update `docker-compose.yml` and remove this step)*

4.  **Configure Environment Variables:**
    *   Create a `.env` file by copying the example:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and fill in your actual values for:
        *   `TELEGRAM_BOT_TOKEN`
        *   `OPENAI_API_KEY`
        *   `GOOGLE_CLIENT_ID` (from `credentials.json`)
        *   `GOOGLE_CLIENT_SECRET` (from `credentials.json`)
        *   `GOOGLE_REDIRECT_URI` (ensure it matches step 2 and your setup)
        *   Verify `MCP_SERVER_URL` if needed.

5.  **Build and Run with Docker Compose:**
    ```bash
    # Using Docker Compose
    docker-compose up --build -d

    # Using Podman Compose
    podman-compose up --build -d
    ```

## Usage

1.  **Start a Chat:** Find your bot on Telegram and send the `/start` command.
2.  **Authorize Google Calendar:** Use the `/auth` command (or similar, depending on implementation). The bot will provide a link. Open the link in your browser, log in to your Google account, and grant the requested permissions. You should be redirected back (to the MCP server or the bot's callback handler).
3.  **Interact:** Once authorized, you can send natural language commands like:
    *   "What's on my calendar tomorrow?"
    *   "Schedule a meeting with Roo on Friday at 2 PM for 1 hour called 'MCP Project Sync'"
    *   "Do I have anything scheduled next Monday morning?"

## Development

*(Add details about running locally, testing, etc., later)*

## Troubleshooting

*(Add common issues and solutions later)*

---

*This README is based on the initial plan. Details will be refined as development progresses.*