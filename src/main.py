"""Main entry point for the Listing Sleuth Apify Actor.

This module contains the main entry point for the Actor, which searches for real estate
listings based on user-specified criteria.
"""

import os
import sys
import json
from apify import Actor
from dotenv import load_dotenv

from .models.property import SearchCriteria
from .search_agent import SearchAgentCrew

# Load environment variables from .env file if present
load_dotenv()


async def main() -> None:
    """Main entry point for the Apify Actor.
    
    This function initializes the Actor, processes input data, runs the search agent,
    and saves the results to the Actor's dataset.
    """
    # Enter the context of the Actor.
    async with Actor:
        # Log the Actor's version
        Actor.log.info(f"Listing Sleuth is starting...")
        
        # Charge for actor start
        await Actor.charge('actor-start')
        
        # Retrieve the Actor input, and use default values if not provided.
        actor_input = await Actor.get_input() or {}
        
        # For local testing, try to load from INPUT.json if actor_input is empty
        if not actor_input or 'location' not in actor_input:
            try:
                if os.path.exists('INPUT.json'):
                    with open('INPUT.json', 'r') as f:
                        actor_input = json.load(f)
                    Actor.log.info(f"Loaded input from INPUT.json: {actor_input}")
            except Exception as e:
                Actor.log.error(f"Error loading from INPUT.json: {str(e)}")
        
        Actor.log.info(f"Using input: {actor_input}")
        
        # Parse location (required)
        location = actor_input.get("location")
        if not location:
            Actor.log.error("No location specified in Actor input, exiting...")
            # Just exit with an error code
            sys.exit(1)
        
        # Parse other inputs with defaults
        property_type = actor_input.get("propertyType", "any")
        min_bedrooms = int(actor_input.get("minBedrooms", 1))
        max_bedrooms = actor_input.get("maxBedrooms")
        if max_bedrooms is not None:
            max_bedrooms = int(max_bedrooms)
        
        min_price = float(actor_input.get("minPrice", 0))
        max_price = actor_input.get("maxPrice")
        if max_price is not None:
            max_price = float(max_price)
        
        # Amenities as a list
        amenities = actor_input.get("amenities", [])
        
        # Search type (rent/buy)
        search_type = actor_input.get("searchType", "rent")
        
        # Data sources to search
        sources = actor_input.get("sources", ["zillow", "realtor", "apartments"])
        
        # LLM API token (optional)
        llm_api_token = actor_input.get("llmApiToken") or os.environ.get("OPENAI_API_KEY")
        
        # Create search criteria
        search_criteria = SearchCriteria(
            location=location,
            property_type=property_type,
            min_bedrooms=min_bedrooms,
            max_bedrooms=max_bedrooms,
            min_price=min_price,
            max_price=max_price,
            amenities=amenities,
            search_type=search_type,
            sources=sources,
            llm_api_token=llm_api_token
        )
        
        Actor.log.info(f"Search criteria: {search_criteria}")
        
        # Create and run the search agent
        search_agent = SearchAgentCrew(search_criteria)
        results = search_agent.run()
        
        # Charge for each property found
        if results.total_results > 0:
            await Actor.charge('property-found', count=results.total_results)
        
        # Log results
        Actor.log.info(f"Search complete. Found {results.total_results} properties.")
        Actor.log.info(f"New listings: {results.new_results}")
        
        # Charge for search completion
        await Actor.charge('search-completed')
        
        # The results have already been saved to the dataset by the search agent
