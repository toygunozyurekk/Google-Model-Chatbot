from flask import Flask, request, jsonify
from flask_cors import CORS
import os 
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain import hub
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_community.agent_toolkits import GmailToolkit
from langchain_community.tools.gmail.utils import (
    build_resource_service,
    get_gmail_credentials,
)
import boto3 
from botocore.exceptions import NoCredentialsError


# Load environment variables from .env file
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Create Flask app instance
app = Flask(__name__)
CORS(app)

s3 = boto3.client('s3',
                  aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                  aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))

def download_file_from_s3(bucket_name, file_name):
    # Check if the file exists locally
    if os.path.exists(file_name):
        print("File already exists locally. Skipping download.")
        return True

    try:
        with open(file_name, 'wb') as f:
            s3.download_fileobj(bucket_name, file_name, f)
        return True
    except NoCredentialsError:
        return False
    

# Define route for handling mail requests
@app.route("/mail", methods=['POST'])
def get_mail():
    bucket_name = 'googlemethods'
    token_file_name = 'token.json'
    credentials_file_name = 'credentials.json'
    if download_file_from_s3(bucket_name, token_file_name) and download_file_from_s3(bucket_name, credentials_file_name):
        # Get Gmail credentials
        credentials = get_gmail_credentials(
            token_file=token_file_name,
            scopes=["https://mail.google.com/"],
            client_secrets_file=credentials_file_name,
        )
    # Build Gmail API resource service
    api_resource = build_resource_service(credentials=credentials)
    # Create Gmail toolkit
    toolkit = GmailToolkit(api_resource=api_resource)

    # Get query from request JSON
    query = request.json.get('query', '')

    # Set instructions for the agent
    
    instructions = """As an assistant, I specialize in managing tasks related to Google GMail, Google Calendar, and Google Meet. For queries outside of these areas, I'll respond with either 'I don't know' or 'I can't do this for you.'  I will provide the same responses when queried in other languages."""
    # Pull base prompt from langchain hub with specific options
    base_prompt = hub.pull("langchain-ai/openai-functions-template")

    # Partially complete the prompt with instructions
    prompt = base_prompt.partial(instructions=instructions)

    # Create OpenAI ChatOpenAI language model
    llm = ChatOpenAI(api_key=OPENAI_API_KEY, temperature=0)
    # Create OpenAI functions agent
    agent = create_openai_functions_agent(llm, toolkit.get_tools(), prompt)
    # Create agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=toolkit.get_tools(),
        # Set verbose to False to prevent email information from showing on screen
        # Normally, it is helpful to have it set to True however.
        verbose=False,
    )

    # Invoke agent with query
    result = agent_executor.invoke({"input": query})

    return result

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)