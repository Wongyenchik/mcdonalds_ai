from langchain.chains import LLMChain
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.agents import Tool, initialize_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import create_engine
from langchain_community.utilities.sql_database import SQLDatabase
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set environment variables after loading from .env
os.environ['TAVILY_API_KEY'] = os.getenv('TAVILY_API_KEY')
os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Connect to the database using environment variables
db_url = f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
engine = create_engine(db_url)
database = SQLDatabase(engine)

# SQL tools
sql_toolkit = SQLDatabaseToolkit(db=database, llm=llm)
sql_tools = sql_toolkit.get_tools()
for tool in sql_tools:
    if tool.name == "sql_db_query":
        tool.description = "Use this tool FIRST to query the McDonald's database for outlet information including addresses, names, and other details"
    elif tool.name == "sql_db_schema":
        tool.description = "Use this to get the database schema to help form your SQL queries"

# TavilySearchResults for search
search_tool = TavilySearchResults(max_results=3)
search_tool = Tool(
    name="web_search",
    func=search_tool.run,
    description="ONLY use this tool if the information cannot be found in the database first"
)
# Create a default response for non-McDonald's queries
def default_response():
    return "I apologize, but I can only answer questions about McDonald's outlets in Kuala Lumpur. Please ask me about McDonald's outlet locations, operating hours, or other outlet-related information in KL."

#====================================
# First agent (Detection agent) 
def detect_and_transform_query(query: str):
    """Detect and transform queries about McDonald's outlets in Kuala Lumpur"""
    detection_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a query detector that transforms questions about outlets in Kuala Lumpur.
        DO NOT USE OR MENTION ANY TOOLS. Simply transform or reject the query based on the rules below.

        TRANSFORMATION RULES:
        1. When a query contains "outlet" WITHOUT mentioning any restaurant name:
           RETURN THE TRANSFORMED QUERY:
           - Add "McDonald's" and "in Kuala Lumpur" to the query
           Example: "Which outlet allows birthday parties?" -> "Which McDonald's outlet in Kuala Lumpur allows birthday parties?"

        2. When a query explicitly mentions "McDonald's":
           RETURN THE TRANSFORMED QUERY:
           - Add "in Kuala Lumpur" if needed
           Example: "What are McDonald's outlet hours?" -> "What are McDonald's outlet hours in Kuala Lumpur?"

        3. For invalid queries (other restaurants or unrelated topics):
           RETURN EXACTLY: "INVALID"

        DO NOT return any other messages or mention any tools.
        """),
        
        ("human", """{input}""")
    ])

    detection_chain = LLMChain(
        llm=llm,
        prompt=detection_prompt
    )

    return detection_chain.run(query).strip()

#====================================
# Second agent (Search agent)
def search_mcdonalds_outlets(query: str):
    """Search for specific McDonald's outlets in Kuala Lumpur based on user query"""
    custom_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a McDonald's Kuala Lumpur outlets expert. Your task is to search for SPECIFIC McDonald's outlets in Kuala Lumpur based on what the user asks.

        SEARCH GUIDELINES:
        - ALWAYS include "McDonald's" in your search query, even if the user doesn't mention it
        - Search specifically for outlet names that match the user's criteria
        - Only return specific outlet names and their relevant information
        - If no specific outlets can be found, respond with "I cannot find specific McDonald's outlets in Kuala Lumpur that match your criteria."
        - DO NOT provide general information or website links
        - DO NOT make assumptions or provide alternative information
        - Format responses with bullet points when listing multiple outlets
        Example Searches and Responses:
        User: "Which outlet allows birthday parties?"
        Good Response:
        - McDonald's Bukit Bintang: Offers birthday party facilities
        - McDonald's KLCC: Has dedicated party room
        
        Bad Response (DO NOT DO THIS):
        - "You can host birthday parties at McDonald's outlets..."
        - "Visit McDonald's website for party bookings..."
        - "McDonald's offers party packages..."
        
        Response Format:
        - McDonald's [Outlet Name]: [Specific information about this outlet]
        OR
        "I cannot find specific McDonald's outlets in Kuala Lumpur that match your criteria."
        """),
        
        ("human", """ALWAYS search for at least 3 times before giving the response, if still cannot find, then give the response. {input}""")
    ])

    search_agent = initialize_agent(
        tools=[search_tool], 
        llm=llm,
        agent_type="zero-shot-react-description",
        verbose=True,
        agent_kwargs={'prompt': custom_prompt}
    )

    return search_agent.run(query)

#====================================
# Third agent (Transform agent)
def transform_response_to_query(response):
    transform_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helper that transforms statements about SPECIFIC McDonald's locations into database validation questions.
        
        RULES:
        1. IF SPECIFIC McDonald's outlet names are detected in the input:
           - For EACH specific outlet, create TWO questions:
             a. One with the original name EXACTLY AS IS (preserve all numbers and special characters)
             b. One with DT added (if no DT) or removed (if has DT)
           - ALWAYS include "McDonald's" in the outlet name
           - NEVER remove or modify numbers in outlet names
           - If name ends with DT, create version without DT
           - If name doesn't end with DT, create version with DT added at the end
        
        2. Return EXACTLY "INVALID" if:
           - No specific outlet names are mentioned
           - Only general references to "McDonald's" or "McDonald's outlets"
           - Information about McDonald's services/facilities in general
        
        Examples:
        Input: "McDonald's Mid Valley 3 is open 24 hours"
        Output:
        Is McDonald's Mid Valley 3 exist in mcdonalds_outlets table?
        Is McDonald's Mid Valley 3 DT exist in mcdonalds_outlets table?
        
        Input: "McDonald's KLCC 2 DT and McDonald's Pandan Mewah are open"
        Output:
        Is McDonald's KLCC 2 DT exist in mcdonalds_outlets table?
        Is McDonald's KLCC 2 exist in mcdonalds_outlets table?
        Is McDonald's Pandan Mewah exist in mcdonalds_outlets table?
        Is McDonald's Pandan Mewah DT exist in mcdonalds_outlets table?

        Input: "You can host a birthday party at McDonald's outlets"
        Output: "INVALID"

        [IMPORTANT] If the output is found, append this sql query at the end of the output:
        Please use this query to get the information of the outlet: SELECT * FROM mcdonalds_outlets WHERE name IN ('McDonald's [outlet1]', 'McDonald's [outlet2]', ...)
        """),
        
        ("human", """Transform this statement ONLY if it contains specific McDonald's outlet names:
        {response}""")
    ])
    
    # Create a chain for the transformation
    transform_chain = LLMChain(
        llm=llm,  # Using the same LLM we defined earlier
        prompt=transform_prompt,
    )
    
    # Transform the response
    transformed_query = transform_chain.run(response=response)
    
    return transformed_query.strip()

#====================================
# Fourth agent (Validation agent)
def evaluate_response(query: str):
    """Evaluate if a McDonald's outlet exists in Kuala Lumpur"""
    system = """ You are an expert at identifying valid McDonald's outlets in Kuala Lumpur.

    Your task is to check if each outlet name exists in the mcdonalds_outlets table:
    1. FIRST, run this SQL query:
       SELECT name FROM mcdonalds_outlets;

    2. Then for each outlet name in the input:
       - Check if it exists in the query results
       - If exists: Return the exact name as found in the results
       - If not found: Return "The outlet is not in Kuala Lumpur"

    Example Process:
    Input: "Is McDonald's BHP Jalan Kepong DT in Kuala Lumpur?"
    1. Run SELECT name FROM mcdonalds_outlets query
    2. Check results -> If found: "Yes, McDonald's BHP Jalan Kepong is in Kuala Lumpur"
                     -> If not found: "The outlet is not in Kuala Lumpur"

    Input: "Is McDonald's XYZ in Kuala Lumpur?"
    1. Run SELECT name FROM mcdonalds_outlets query
    2. Check results -> "The outlet is not in Kuala Lumpur"

    IMPORTANT: Always run the SELECT name FROM mcdonalds_outlets query to check any outlets.
    """

    evaluation_prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", """Please check if these outlets exist in the mcdonalds_outlets table:
        {input}""")
    ])

    evaluation_chain = initialize_agent(
        tools=sql_tools,
        llm=llm,
        agent_type="zero-shot-react-description",
        verbose=True,
        agent_kwargs={'prompt': evaluation_prompt}
    )

    evaluation_input = {'input': query}
    return evaluation_chain.run(evaluation_input)

#====================================
# Fifth agent (Compile agent)
def create_final_response(original_query, first_agent_response, second_agent_response):
    conclusion_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helper that modifies the original search results based on the user's question while ensuring all outlets pass location validation.

        Your main tasks:
        1. Take the original search results
        2. Check the location validation results for both DT and non-DT versions of each outlet
        3. Update outlet names to match the database version (with or without DT)
        4. Ensure the modified results directly answer the user's original question

        Format Rules:
        1. Respond in complete, natural sentences instead of bullet points
        2. For outlet names:
           - If either version (with/without DT) exists in database:
             * Use the exact name from database validation results
             * Keep the original information but update the outlet name
           Example: 
           Original: "McDonald's BHP Jalan Kepong DT is open 24 hours"
           Database name: "McDonald's BHP Jalan Kepong"
           Final: "McDonald's BHP Jalan Kepong is open 24 hours."

        3. For non-existent outlets:
           - If neither version exists in database:
             * If outlet was specifically mentioned in original query:
                 Include "I cannot provide information about [Original Outlet Name] as it is not in Kuala Lumpur."
             * If outlet was NOT specifically mentioned in original query:
                 Simply exclude it from the final response
        
        Example:
        Original Results:
        - McDonald's Pandan Mewah: Open 24 hours
        - McDonald's BHP Jalan Kepong DT: Drive-thru available

        Validation Results:
        Is McDonald's Pandan Mewah in Kuala Lumpur? No
        Is McDonald's Pandan Mewah DT in Kuala Lumpur? Yes, as McDonald's Pandan Mewah DT
        Is McDonald's BHP Jalan Kepong DT in Kuala Lumpur? No
        Is McDonald's BHP Jalan Kepong in Kuala Lumpur? Yes, as McDonald's BHP Jalan Kepong

        Final Output:
        McDonald's Pandan Mewah DT is open 24 hours, and McDonald's BHP Jalan Kepong offers drive-thru service."""),
        
        ("human", """Original user question:
        {original_query}

        Original search results:
        {first_response}
        
        Location validation results:
        {second_response}
        
        Please modify the original search results based on the validation results, updating outlet names to match the database version and ensure it answers the original question in complete sentences.""")
    ])
    
    # Create a chain for the conclusion
    conclusion_chain = LLMChain(
        llm=llm,
        prompt=conclusion_prompt
    )
    
    # Generate the final response
    final_response = conclusion_chain.run(
        original_query=original_query,
        first_response=first_agent_response,
        second_response=second_agent_response
    )
    
    return final_response.strip()


#====================================
# Main process function
def process_query(query):
    # First, detect and transform if valid
    detection_result = detect_and_transform_query(query)
    print("Detection result:", detection_result)
    
    # If detection returns "INVALID", use default_response
    if detection_result == "INVALID":
        return default_response()
    
    # Otherwise, use the transformed query with the research chain
    first_agent_response = search_mcdonalds_outlets(detection_result)
    # print("First agent response:", first_agent_response)
    # first_agent_response = "The McDonald's outlets in Kuala Lumpur that allow birthday parties include McDonald's Bandar Sri Damansara DT, McDonald's BHP Jalan Kepong DT, McDonald's Danau Kota DT, McDonald's Pandan Mewah, and McDonald's Pantai Sentral Park DT."

    transformed_response = transform_response_to_query(first_agent_response)
    print("Transformed response:", transformed_response)
    # If transformed response is exactly the same as first_agent_response, stop the chain
    if transformed_response == "INVALID" or transformed_response == first_agent_response:
        return first_agent_response
    
    # Only continue if transformation occurred (meaning McDonald's locations were found)
    evaluated_response = evaluate_response(transformed_response)
    print("Evaluated response:", evaluated_response)
    print("--------------------------------")
    final_response = create_final_response(detection_result,first_agent_response, evaluated_response)
    # print("Final response:", final_response)
    return final_response

#====================================
# Usage example
# query = "What is the operation hours of McDonald's Bandar Puteri Puchong?"
# result = process_query(query)
# print(result)