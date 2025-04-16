import logging
import os
import json
import pickle # For saving/loading credentials
import asyncio # For running web server concurrently
from pathlib import Path # For handling file paths

# Google Auth/API Libraries
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleAuthRequest # Alias to avoid conflict
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Web Server for OAuth Callback
from aiohttp import web

# Bot/OpenAI Libraries
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, PicklePersistence

# Load environment variables from .env file
# Assuming .env is in the parent directory relative to bot/main.py
dotenv_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Get Telegram Bot Token from environment variable
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
    exit(1)

# --- Constants ---
# GOOGLE_CLIENT_SECRETS_FILE = '/app/credentials.json' # No longer needed
# Scopes required for calendar access (read/write)
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']
# Redirect URI for OAuth flow - must match Google Cloud Console and docker-compose port mapping
# Ensure the port (e.g., 8080) matches the EXPOSE in Dockerfile and ports in docker-compose.yml
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8080/callback")
# Directory to store user credentials persistently (maps to volume in docker-compose)
TOKEN_STORAGE_DIR = Path("/app/token_storage")
TOKEN_STORAGE_DIR.mkdir(parents=True, exist_ok=True) # Ensure directory exists

# --- OpenAI Client Setup ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY not found in environment variables!")
    # Decide if exit is necessary, maybe some commands don't need OpenAI
    # exit(1)
    openai_client = None
else:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

# --- Tool Definitions for OpenAI (Will remain similar, but execution changes) ---
# These describe the functions the bot can perform using the Google Calendar API
tools = [
    {
        "type": "function",
        "function": {
            "name": "list_calendar_events",
            "description": "Get a list of events from the user's Google Calendar within a specified time range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": "The start date/time in ISO 8601 format (e.g., 2025-04-17T00:00:00Z). Required.",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "The end date/time in ISO 8601 format (e.g., 2025-04-18T00:00:00Z). Required.",
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "The ID of the calendar to query. Defaults to 'primary'. Optional.",
                    },
                },
                "required": ["start_time", "end_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Create a new event on the user's Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "The title or summary of the event. Required.",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "The start date/time in ISO 8601 format (e.g., 2025-04-17T14:00:00Z). Required.",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "The end date/time in ISO 8601 format (e.g., 2025-04-17T15:00:00Z). Required.",
                    },
                    "description": {
                        "type": "string",
                        "description": "A longer description for the event. Optional.",
                    },
                     "location": {
                        "type": "string",
                        "description": "The location of the event. Optional.",
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "The ID of the calendar to add the event to. Defaults to 'primary'. Optional.",
                    },
                },
                "required": ["summary", "start_time", "end_time"],
            },
        },
    },
    # TODO: Add tools for update_event, delete_event based on MCP capabilities
]


# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=None, # Add keyboard later if needed
    )
    await update.message.reply_text(
        "I can help you manage your Google Calendar. "
        "Use /auth to connect your Google Account.\n\n"
        "Once authorized, you can tell me things like:\n"
        "- 'What's on my calendar tomorrow?'\n"
        "- 'Schedule a meeting for Friday at 3 PM called Project Kickoff'"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays info on how to use the bot."""
    await update.message.reply_text(
        "Use /start to see introduction.\n"
        "Use /auth to connect your Google Calendar.\n"
        "Then, just send me messages in natural language to interact with your calendar."
        )

async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Starts the Google OAuth flow using google-auth-oauthlib."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    logger.info(f"User {user_id} in chat {chat_id} initiated /auth command.")

    # Store chat_id to send message after callback
    # Using context.user_data which is persisted by PicklePersistence
    context.user_data['auth_chat_id'] = chat_id

    try:
        # Construct client_config dictionary from environment variables
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        project_id = os.getenv("GOOGLE_PROJECT_ID")
        auth_uri = os.getenv("GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth")
        token_uri = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")
        auth_provider_x509_cert_url = os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs")
        # Redirect URIs are handled by the REDIRECT_URI constant directly in the flow

        if not all([client_id, client_secret, project_id]):
            logger.error("Missing required Google OAuth environment variables (CLIENT_ID, CLIENT_SECRET, PROJECT_ID).")
            await update.message.reply_text("Error: Authentication configuration is incomplete in environment variables.")
            return

        client_config = {
            "web": {
                "client_id": client_id,
                "project_id": project_id,
                "auth_uri": auth_uri,
                "token_uri": token_uri,
                "auth_provider_x509_cert_url": auth_provider_x509_cert_url,
                "client_secret": client_secret,
                "redirect_uris": [REDIRECT_URI] # Use the single configured redirect URI
            }
        }

        # Create flow instance using the constructed config dictionary
        flow = Flow.from_client_config(
            client_config=client_config, # Use loaded dictionary
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )

        # Generate authorization URL, passing user_id in state for callback verification
        # State should be securely generated and verified in a real app
        state = f"user_{user_id}" # Simple state for now
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Request refresh token
            include_granted_scopes='true',
            state=state # Pass user identifier in state
        )

        # Store the state in context for the callback handler to verify
        context.user_data['oauth_state'] = state
        logger.info(f"Generated OAuth URL for user {user_id} with state: {state}")

        await update.message.reply_text(
            "Please click the link below to authorize access to your Google Calendar. "
            "Make sure you are logged into the correct Google account in your browser.\n\n"
            f"{authorization_url}\n\n"
            "After authorizing, I will notify you here."
        )

    except FileNotFoundError:
        logger.error(f"Google client secrets file not found at {GOOGLE_CLIENT_SECRETS_FILE}")
        await update.message.reply_text("Error: Authentication configuration is missing.")
    except Exception as e:
        logger.error(f"Error creating OAuth flow for user {user_id}: {e}")
        await update.message.reply_text("An error occurred while starting the authentication process.")

# --- Credential Storage ---

def get_user_token_path(user_id: int) -> Path:
    """Returns the path to the user's token file."""
    return TOKEN_STORAGE_DIR / f"user_{user_id}.pickle"

def save_credentials(user_id: int, credentials):
    """Saves user credentials to a file."""
    token_path = get_user_token_path(user_id)
    try:
        with open(token_path, "wb") as token_file:
            pickle.dump(credentials, token_file)
        logger.info(f"Credentials saved successfully for user {user_id} to {token_path}")
    except Exception as e:
        logger.error(f"Failed to save credentials for user {user_id}: {e}")

def load_credentials(user_id: int) -> Credentials | None:
    """Loads user credentials from a file and refreshes if necessary."""
    token_path = get_user_token_path(user_id)
    creds = None
    if token_path.exists():
        try:
            with open(token_path, "rb") as token_file:
                creds = pickle.load(token_file)
            logger.debug(f"Credentials loaded for user {user_id} from {token_path}")
            # Check if credentials have expired and refresh if necessary
            if creds and creds.expired and creds.refresh_token:
                logger.info(f"Credentials for user {user_id} expired. Refreshing...")
                try:
                    creds.refresh(GoogleAuthRequest())
                    save_credentials(user_id, creds) # Save refreshed credentials
                    logger.info(f"Credentials refreshed successfully for user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to refresh credentials for user {user_id}: {e}")
                    # Delete the invalid token file
                    token_path.unlink(missing_ok=True)
                    return None # Return None if refresh fails
        except Exception as e:
            logger.error(f"Failed to load or refresh credentials for user {user_id} from {token_path}: {e}")
            # Corrupted file? Delete it.
            token_path.unlink(missing_ok=True)
            return None
    return creds

# --- Google API Tool Execution Logic ---

async def execute_google_api_tool(tool_call, user_id) -> str:
    """Executes a specific tool call using the Google Calendar API."""
    function_name = tool_call.function.name
    try:
        arguments = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse arguments for tool {function_name}: {tool_call.function.arguments}")
        return f"Error: Invalid arguments received for {function_name}."

    logger.info(f"Executing Google API tool '{function_name}' for user {user_id} with args: {arguments}")

    # Load credentials for the user
    creds = load_credentials(user_id)
    if not creds or not creds.valid:
        logger.warning(f"No valid credentials found for user {user_id}. Cannot execute tool {function_name}.")
        # Instruct user to re-authenticate
        return "Error: Authentication required or token expired. Please use /auth again."

    try:
        # Build the Google Calendar service client
        service = build('calendar', 'v3', credentials=creds, cache_discovery=False) # Disable cache

        result = None
        # Map tool names to Google API calls
        if function_name == "list_calendar_events":
            calendar_id = arguments.get('calendar_id', 'primary')
            start_time = arguments.get('start_time')
            end_time = arguments.get('end_time')
            if not start_time or not end_time:
                return "Error: start_time and end_time are required for list_calendar_events."

            logger.info(f"Calling events().list for user {user_id}, calendarId={calendar_id}, timeMin={start_time}, timeMax={end_time}")
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            result = events_result.get('items', [])
            # Limit result size for display if necessary
            max_events_display = 10
            limited_result = result[:max_events_display]
            result_text = f"Success: Found {len(result)} events."
            if len(result) > max_events_display:
                result_text += f" (Displaying first {max_events_display})"
            result_text += f"\nResult:\n```json\n{json.dumps(limited_result, indent=2)}\n```"
            return result_text

        elif function_name == "create_calendar_event":
            calendar_id = arguments.get('calendar_id', 'primary')
            # Construct event body carefully, handling potential missing fields
            event_body = {'start': {}, 'end': {}}
            if 'summary' in arguments: event_body['summary'] = arguments['summary']
            if 'location' in arguments: event_body['location'] = arguments['location']
            if 'description' in arguments: event_body['description'] = arguments['description']
            if 'start_time' in arguments: event_body['start']['dateTime'] = arguments['start_time']
            if 'end_time' in arguments: event_body['end']['dateTime'] = arguments['end_time']
            # Assume UTC for simplicity, could be enhanced to use user's timezone
            event_body['start']['timeZone'] = 'UTC'
            event_body['end']['timeZone'] = 'UTC'

            if not event_body.get('summary') or not event_body['start'].get('dateTime') or not event_body['end'].get('dateTime'):
                 return "Error: summary, start_time, and end_time are required for create_calendar_event."

            logger.info(f"Calling events().insert for user {user_id}, calendarId={calendar_id}, body={event_body}")
            created_event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
            result = created_event.get('htmlLink')
            return f"Success: Event created! Link: {result}\nDetails:\n```json\n{json.dumps(created_event, indent=2)}\n```"

        # TODO: Implement other functions like update_event, delete_event
        else:
            logger.warning(f"Unknown tool function called for Google API: {function_name}")
            return f"Error: Unknown action '{function_name}'."

    except HttpError as error:
        logger.error(f"Google API error for user {user_id} calling {function_name}: {error}")
        error_details = f"Status: {error.resp.status}"
        try:
            error_content = json.loads(error.content.decode('utf-8'))
            error_details += f", Message: {error_content.get('error', {}).get('message', 'Unknown error')}"
        except Exception:
            error_details += f", Content: {error.content.decode('utf-8', errors='ignore')}"
        # Check for specific auth errors
        if error.resp.status in [401, 403]:
             error_details += ". Please try using /auth again."
        return f"Error interacting with Google Calendar: {error_details}"
    except Exception as e:
        logger.error(f"Unexpected error executing Google API tool {function_name} for user {user_id}: {e}")
        return f"Error: An unexpected error occurred while performing the action '{function_name}'."


# --- Message Handler ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles regular user messages to interact with OpenAI and Google Calendar API."""
    message_text = update.message.text
    user_id = update.effective_user.id
    logger.info(f"Received message from user {user_id}: {message_text}")

    # 1. Check if user is authenticated (by loading credentials)
    credentials = load_credentials(user_id)
    if not credentials or not credentials.valid:
        logger.info(f"User {user_id} is not authenticated or token invalid. Prompting to use /auth.")
        await update.message.reply_text("Please use the /auth command first (or again) to connect your Google Calendar.")
        return

    # 2. Check if OpenAI client is available
    if not openai_client:
        logger.error("OpenAI client not initialized. Cannot process message.")
        await update.message.reply_text("Sorry, the AI service is not available right now.")
        return

    # 3. Send message to OpenAI API
    logger.info(f"Sending message from user {user_id} to OpenAI.")
    try:
        # Construct messages for OpenAI
        # TODO: Add conversation history management later
        messages = [
            {"role": "system", "content": "You are a helpful assistant managing Google Calendar. Use the available tools to fulfill user requests. Ask for clarification if needed. Assume the current year is 2025 unless specified otherwise."},
            {"role": "user", "content": message_text}
        ]

        response = openai_client.chat.completions.create(
            model="gpt-4o", # Or another suitable model like gpt-4-turbo
            messages=messages,
            tools=tools,
            tool_choice="auto",  # Let the model decide whether to use tools
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # 4. Process OpenAI response
        if tool_calls:
            logger.info(f"OpenAI response for user {user_id} contains tool calls: {tool_calls}")

            # Execute Google API tools and collect results
            tool_results = []
            for tool_call in tool_calls:
                # Use the function to call Google API directly
                result = await execute_google_api_tool(tool_call, user_id)
                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": result, # Result from execute_mcp_tool
                })

            # For simplicity now, just send the raw results back to the user
            # TODO: Optionally send results back to OpenAI for a final summary response
            results_text = "\n\n".join([f"Tool: {r['name']}\nResult:\n{r['content']}" for r in tool_results])
            await update.message.reply_text(f"Executed Actions:\n{results_text}")

        else:
            # No tool calls, just send the text response back
            ai_response_text = response_message.content
            logger.info(f"OpenAI response for user {user_id} (no tool calls): {ai_response_text}")
            await update.message.reply_text(ai_response_text or "I received that, but I don't have a specific action to take.")

    except Exception as e:
        logger.error(f"Error calling OpenAI or processing response for user {user_id}: {e}")
        await update.message.reply_text("Sorry, I encountered an error trying to process your request with the AI.")



# --- Main Function ---

# --- Web Server for OAuth Callback ---

async def oauth_callback(request: web.Request) -> web.Response:
    """Handles the redirect from Google OAuth."""
    try:
        # Get state and code from query parameters
        state = request.query.get('state')
        code = request.query.get('code')
        error = request.query.get('error')

        if error:
            logger.error(f"OAuth callback received error: {error}")
            # TODO: Notify the user via Telegram if possible
            return web.Response(text=f"OAuth Error: {error}. Please try /auth again.", content_type='text/html')

        if not state or not code:
            logger.error("OAuth callback missing state or code.")
            return web.Response(text="Error: Invalid callback request.", content_type='text/html')

        logger.info(f"Received OAuth callback with state: {state}")

        # Extract user_id from state (assuming format "user_{user_id}")
        try:
            user_id = int(state.split('_')[1])
        except (IndexError, ValueError):
            logger.error(f"Invalid state format received: {state}")
            return web.Response(text="Error: Invalid state parameter.", content_type='text/html')

        # Retrieve the original chat_id and expected state from user_data
        # Accessing bot data requires the application object passed during web server setup
        bot_app = request.app['bot_app']
        user_data = await bot_app.persistence.get_user_data()
        stored_state = user_data.get(user_id, {}).get('oauth_state')
        chat_id = user_data.get(user_id, {}).get('auth_chat_id')

        # Verify state parameter
        if not stored_state or stored_state != state:
            logger.warning(f"OAuth state mismatch for user {user_id}. Expected '{stored_state}', got '{state}'.")
            if chat_id:
                 await bot_app.bot.send_message(chat_id, "Authentication failed (state mismatch). Please try /auth again.")
            return web.Response(text="Error: State mismatch. Please try authenticating again.", content_type='text/html')

        logger.info(f"OAuth state verified for user {user_id}.")

        # Exchange code for credentials
        # Construct client_config again for the callback
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        project_id = os.getenv("GOOGLE_PROJECT_ID")
        auth_uri = os.getenv("GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth")
        token_uri = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")
        auth_provider_x509_cert_url = os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs")

        if not all([client_id, client_secret, project_id]):
             logger.error("Missing required Google OAuth environment variables during callback.")
             if chat_id:
                 await bot_app.bot.send_message(chat_id, "Error processing authentication callback (missing config).")
             return web.Response(text="Error: Missing authentication configuration during callback.", status=500)

        client_config = {
            "web": {
                "client_id": client_id,
                "project_id": project_id,
                "auth_uri": auth_uri,
                "token_uri": token_uri,
                "auth_provider_x509_cert_url": auth_provider_x509_cert_url,
                "client_secret": client_secret,
                "redirect_uris": [REDIRECT_URI]
            }
        }

        flow = Flow.from_client_config(
            client_config=client_config, # Use constructed dictionary
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
            state=state # Pass state back to flow
        )
        # Use the full URL from the request to fetch the token
        authorization_response = request.url.human_repr()
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials

        # Save credentials persistently
        save_credentials(user_id, credentials)

        # Clean up state from user_data
        if user_id in user_data and 'oauth_state' in user_data[user_id]:
            del user_data[user_id]['oauth_state']
            # No need to explicitly update persistence here, PTB handles it
            # await bot_app.persistence.update_user_data(user_id, user_data[user_id])

        # Notify user in Telegram
        if chat_id:
            try:
                await bot_app.bot.send_message(chat_id, "✅ Google Calendar authentication successful! You can now use calendar commands.")
                logger.info(f"Sent success notification to user {user_id} in chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send success message to user {user_id} in chat {chat_id}: {e}")
        else:
             logger.warning(f"Could not find chat_id for user {user_id} to send success message.")

        # Return success page to browser
        return web.Response(text="Authentication successful! You can close this window and return to Telegram.", content_type='text/html')

    except Exception as e:
        logger.exception("Error processing OAuth callback:") # Log full traceback
        # Attempt to notify user if possible
        state = request.query.get('state')
        if state:
            try:
                user_id = int(state.split('_')[1])
                bot_app = request.app['bot_app']
                user_data = await bot_app.persistence.get_user_data()
                chat_id = user_data.get(user_id, {}).get('auth_chat_id')
                if chat_id:
                    await bot_app.bot.send_message(chat_id, "An error occurred during authentication. Please try /auth again later.")
            except Exception as notify_err:
                 logger.error(f"Failed to notify user about callback error: {notify_err}")
        return web.Response(text="An internal error occurred during authentication. Please try again later.", status=500, content_type='text/html')


async def start_web_server(bot_app: Application):
    """Starts the aiohttp web server."""
    app = web.Application()
    app['bot_app'] = bot_app # Make bot application accessible to handlers
    app.add_routes([web.get('/callback', oauth_callback)])

    runner = web.AppRunner(app)
    await runner.setup()
    # Determine port from REDIRECT_URI, but always bind to 0.0.0.0 for external accessibility
    host = '0.0.0.0'
    try:
        from urllib.parse import urlparse
        parsed_uri = urlparse(REDIRECT_URI)
        port = parsed_uri.port or 8080
    except Exception:
        port = 8080
        logger.warning(f"Could not parse port from REDIRECT_URI ('{REDIRECT_URI}'), defaulting web server port to {port}")

    site = web.TCPSite(runner, host, port)
    logger.info(f"Starting web server on {host}:{port} (accessible externally) for OAuth callback...")
    await site.start()
    logger.info("Web server started.")
    # Keep it running until cancelled
    await asyncio.Event().wait() # This will wait indefinitely until cancelled


async def main() -> None:
    """Runs the bot and web server concurrently."""
    # --- Setup Persistence ---
    persistence_path = TOKEN_STORAGE_DIR / 'bot_persistence.pickle'
    persistence = PicklePersistence(filepath=persistence_path)

    # Create the Application and pass it your bot's token and persistence.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).persistence(persistence).build()

    # --- Register Handlers ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("auth", auth_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Initialize application and persistence (needed for web server access)
    await application.initialize()

    # Start the web server task first
    web_server_task = asyncio.create_task(start_web_server(application))

    # Start the bot polling
    logger.info("Starting bot polling...")
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Bot polling started.")

    # Wait for web server task to complete (which it shouldn't unless cancelled)
    await web_server_task

    # Shutdown application
    logger.info("Shutting down application...")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    logger.info("Application shut down.")


if __name__ == "__main__":
    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested via KeyboardInterrupt.")
    except Exception as e:
        logger.exception("Application crashed unexpectedly:")