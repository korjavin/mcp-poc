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
    *   You will see the Client ID and Client Secret. You will also need other details from the downloaded JSON file (like Project ID, Auth URI, Token URI) for the `.env` file. **Do not commit the downloaded JSON file or the `.env` file.**

3.  **Configure Environment Variables:**
    *   Create a `.env` file by copying the example:
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
        *   `GOOGLE_REDIRECT_URI` (ensure this matches *exactly* one of the URIs registered in step 2 and the port exposed by the bot, e.g., `http://localhost:8080/callback`)

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