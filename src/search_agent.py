"""Search agent for real estate properties."""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from crewai import Agent, Task, Crew
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from apify import Actor

from .models.property import PropertyListing, SearchCriteria, SearchResults
from .scrapers.zillow import ZillowScraper
from .scrapers.realtor import RealtorScraper
from .scrapers.apartments import ApartmentsScraper
from .utils.llm import filter_properties_with_llm, summarize_property
from .utils.storage import (
    load_previous_results,
    mark_new_listings,
    save_search_results,
    push_results_to_dataset
)


class SearchTool(BaseTool):
    """Tool for searching real estate listings."""
    
    name = "search_real_estate"
    description = "Search for real estate listings based on search criteria"
    search_criteria: SearchCriteria = None
    
    def __init__(self, search_criteria: SearchCriteria):
        """Initialize the search tool.
        
        Args:
            search_criteria: Search criteria
        """
        super().__init__()
        self.search_criteria = search_criteria
    
    def _run(self, query: str) -> Dict[str, Any]:
        """Run the search tool.
        
        Args:
            query: Search query (not used, but required by BaseTool)
            
        Returns:
            Search results
        """
        # Initialize scrapers
        scrapers = []
        if "zillow" in self.search_criteria.sources:
            scrapers.append(ZillowScraper(self.search_criteria))
        if "realtor" in self.search_criteria.sources:
            scrapers.append(RealtorScraper(self.search_criteria))
        if "apartments" in self.search_criteria.sources:
            scrapers.append(ApartmentsScraper(self.search_criteria))
        
        # Run scrapers
        all_listings = []
        sources_searched = []
        
        for scraper in scrapers:
            try:
                listings = scraper.scrape()
                all_listings.extend(listings)
                sources_searched.append(scraper.source_name)
            except Exception as e:
                Actor.log.exception(f"Error scraping {scraper.source_name}: {e}")
        
        # Load previous results
        previous_results = load_previous_results(self.search_criteria)
        
        # Mark new listings
        marked_listings = mark_new_listings(all_listings, previous_results)
        
        # Create search results
        results = SearchResults(
            search_criteria=self.search_criteria,
            results=marked_listings,
            total_results=len(marked_listings),
            new_results=sum(1 for listing in marked_listings if listing.is_new),
            sources_searched=sources_searched
        )
        
        # Save results
        save_search_results(results)
        push_results_to_dataset(results)
        
        # Return results
        return {
            "total_results": results.total_results,
            "new_results": results.new_results,
            "sources_searched": results.sources_searched,
            "search_date": results.search_date.isoformat()
        }
    
    async def _arun(self, query: str) -> Dict[str, Any]:
        """Async version of _run.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        return self._run(query)


class FilterTool(BaseTool):
    """Tool for filtering property listings with LLM."""
    
    name = "filter_properties"
    description = "Filter property listings based on search criteria using LLM"
    search_criteria: SearchCriteria = None
    
    def __init__(self, search_criteria: SearchCriteria):
        """Initialize the filter tool.
        
        Args:
            search_criteria: Search criteria
        """
        super().__init__()
        self.search_criteria = search_criteria
    
    def _run(self, query: str) -> Dict[str, Any]:
        """Run the filter tool.
        
        Args:
            query: Filter query (not used, but required by BaseTool)
            
        Returns:
            Filtered search results
        """
        # Try to load saved results
        try:
            results_dict = None
            
            # Try to load from Apify KV store if available
            if hasattr(Actor, 'main_kv_store'):
                results_dict = Actor.main_kv_store.get_value("search_results")
            # Otherwise try to load from local file
            elif os.path.exists("storage/key_value_stores/search_results.json"):
                with open("storage/key_value_stores/search_results.json", "r") as f:
                    results_dict = json.load(f)
            
            if not results_dict:
                return {"error": "No search results found"}
            
            # Convert to SearchResults
            search_results = SearchResults(**results_dict)
            
            if not search_results.results:
                return {"error": "No results to filter"}
            
            # Filter results with LLM if token is available
            if self.search_criteria.llm_api_token:
                filtered_listings = filter_properties_with_llm(
                    search_results.results,
                    self.search_criteria,
                    self.search_criteria.llm_api_token
                )
                
                # Update results
                search_results.results = filtered_listings
                search_results.total_results = len(filtered_listings)
                
                # Save filtered results
                save_search_results(search_results)
                
                return {
                    "total_results_after_filtering": len(filtered_listings),
                    "filter_date": datetime.now().isoformat()
                }
            else:
                return {"error": "No LLM API token provided for filtering"}
        
        except Exception as e:
            Actor.log.exception(f"Error filtering properties: {e}")
            return {"error": str(e)}
    
    async def _arun(self, query: str) -> Dict[str, Any]:
        """Async version of _run.
        
        Args:
            query: Filter query
            
        Returns:
            Filtered search results
        """
        return self._run(query)


class SummarizeTool(BaseTool):
    """Tool for summarizing property listings."""
    
    name = "summarize_properties"
    description = "Generate summaries of property listings"
    search_criteria: SearchCriteria = None
    
    def __init__(self, search_criteria: SearchCriteria):
        """Initialize the summarize tool.
        
        Args:
            search_criteria: Search criteria
        """
        super().__init__()
        self.search_criteria = search_criteria
    
    def _run(self, query: str) -> Dict[str, Any]:
        """Run the summarize tool.
        
        Args:
            query: Summarize query (not used, but required by BaseTool)
            
        Returns:
            Summarized search results
        """
        # Try to load saved results
        try:
            results_dict = None
            
            # Try to load from Apify KV store if available
            if hasattr(Actor, 'main_kv_store'):
                results_dict = Actor.main_kv_store.get_value("search_results")
            # Otherwise try to load from local file
            elif os.path.exists("storage/key_value_stores/search_results.json"):
                with open("storage/key_value_stores/search_results.json", "r") as f:
                    results_dict = json.load(f)
            
            if not results_dict:
                return {"error": "No search results found"}
            
            # Convert to SearchResults
            search_results = SearchResults(**results_dict)
            
            if not search_results.results:
                return {"error": "No results to summarize"}
            
            # Generate summaries if LLM API token is available
            if self.search_criteria.llm_api_token:
                summaries = []
                
                for listing in search_results.results:
                    summary = summarize_property(listing, self.search_criteria.llm_api_token)
                    summaries.append({
                        "id": listing.id,
                        "summary": summary,
                        "is_new": listing.is_new
                    })
                
                return {
                    "summaries": summaries,
                    "total_summaries": len(summaries),
                    "summarize_date": datetime.now().isoformat()
                }
            else:
                # Generate basic summaries without LLM
                summaries = []
                
                for listing in search_results.results:
                    basic_summary = (
                        f"{listing.title}: {listing.bedrooms} bed, "
                        f"{listing.bathrooms or 'unknown'} bath {listing.property_type} "
                        f"for ${listing.price:,.2f} in {listing.address.city}, "
                        f"{listing.address.state}."
                    )
                    
                    summaries.append({
                        "id": listing.id,
                        "summary": basic_summary,
                        "is_new": listing.is_new
                    })
                
                return {
                    "summaries": summaries,
                    "total_summaries": len(summaries),
                    "summarize_date": datetime.now().isoformat()
                }
        
        except Exception as e:
            Actor.log.exception(f"Error summarizing properties: {e}")
            return {"error": str(e)}
    
    async def _arun(self, query: str) -> Dict[str, Any]:
        """Async version of _run.
        
        Args:
            query: Summarize query
            
        Returns:
            Summarized search results
        """
        return self._run(query)


class SearchAgentCrew:
    """Crew of agents for property search."""
    
    def __init__(self, search_criteria: SearchCriteria):
        """Initialize the search agent crew.
        
        Args:
            search_criteria: Search criteria
        """
        self.search_criteria = search_criteria
        self.llm = None
        
        # Initialize LLM if token is provided
        if search_criteria.llm_api_token:
            self.llm = ChatOpenAI(
                api_key=search_criteria.llm_api_token,
                temperature=0,
                model="gpt-3.5-turbo"
            )
    
    def run(self) -> SearchResults:
        """Run the search agent crew.
        
        Returns:
            Search results
        """
        # If no LLM, just run the search directly
        if not self.llm:
            Actor.log.info("No LLM API token provided, running basic search without agents")
            search_tool = SearchTool(self.search_criteria)
            search_tool._run("")
            
            # Load and return results
            try:
                # Try loading from Apify KV store if available
                if hasattr(Actor, 'main_kv_store'):
                    results_dict = Actor.main_kv_store.get_value("search_results")
                # Otherwise try to load from local file
                elif os.path.exists("storage/key_value_stores/search_results.json"):
                    with open("storage/key_value_stores/search_results.json", "r") as f:
                        results_dict = json.load(f)
                else:
                    results_dict = None
                
                if results_dict:
                    return SearchResults(**results_dict)
            except Exception as e:
                Actor.log.error(f"Error loading search results: {e}")
            
            # Create empty results if loading failed
            return SearchResults(
                search_criteria=self.search_criteria,
                results=[],
                total_results=0,
                new_results=0,
                sources_searched=[]
            )
        
        # Create tools
        search_tool = SearchTool(self.search_criteria)
        filter_tool = FilterTool(self.search_criteria)
        summarize_tool = SummarizeTool(self.search_criteria)
        
        # Create agents
        search_agent = Agent(
            role="Real Estate Search Specialist",
            goal="Find properties that match the search criteria",
            backstory="You are an expert in finding real estate listings across multiple platforms.",
            verbose=True,
            allow_delegation=True,
            tools=[search_tool],
            llm=self.llm
        )
        
        filter_agent = Agent(
            role="Property Filter Specialist",
            goal="Filter properties to find the best matches for the user",
            backstory="You are an expert in analyzing property details and matching them with user preferences.",
            verbose=True,
            allow_delegation=True,
            tools=[filter_tool],
            llm=self.llm
        )
        
        summarize_agent = Agent(
            role="Property Summarizer",
            goal="Create concise, informative summaries of properties",
            backstory="You are skilled at creating appealing property descriptions that highlight key features.",
            verbose=True,
            allow_delegation=True,
            tools=[summarize_tool],
            llm=self.llm
        )
        
        # Create tasks
        search_task = Task(
            description=(
                f"Search for properties in {self.search_criteria.location} "
                f"with {self.search_criteria.min_bedrooms}+ bedrooms, "
                f"maximum price of ${self.search_criteria.max_price or 'any'}, "
                f"property type: {self.search_criteria.property_type}. "
                f"Search sources: {', '.join(self.search_criteria.sources)}."
            ),
            agent=search_agent,
            expected_output="A report of the total number of properties found"
        )
        
        filter_task = Task(
            description=(
                "Filter the search results to find properties that best match "
                f"the user's criteria, especially regarding amenities: {', '.join(self.search_criteria.amenities)}"
            ),
            agent=filter_agent,
            expected_output="A report of how many properties passed the filtering"
        )
        
        summarize_task = Task(
            description=(
                "Create summaries for each property highlighting key features. "
                "Mark new listings that weren't found in previous searches."
            ),
            agent=summarize_agent,
            expected_output="Summaries of each property"
        )
        
        # Create crew
        crew = Crew(
            agents=[search_agent, filter_agent, summarize_agent],
            tasks=[search_task, filter_task, summarize_task],
            verbose=True
        )
        
        # Run the crew
        try:
            result = crew.kickoff()
            
            # Load and return results
            try:
                # Try loading from Apify KV store if available
                if hasattr(Actor, 'main_kv_store'):
                    results_dict = Actor.main_kv_store.get_value("search_results")
                # Otherwise try to load from local file
                elif os.path.exists("storage/key_value_stores/search_results.json"):
                    with open("storage/key_value_stores/search_results.json", "r") as f:
                        results_dict = json.load(f)
                else:
                    results_dict = None
                
                if results_dict:
                    return SearchResults(**results_dict)
            except Exception as e:
                Actor.log.error(f"Error loading search results: {e}")
        except Exception as e:
            Actor.log.error(f"Error running crew: {e}")
            
        # If we got here, either there was an error or no results were found
        # Create empty results
        return SearchResults(
            search_criteria=self.search_criteria,
            results=[],
            total_results=0,
            new_results=0,
            sources_searched=[]
        ) 