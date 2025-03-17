"""Storage utility functions for Listing Sleuth."""

import json
import os
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pydantic import BaseModel
from apify import Actor

from ..models.property import PropertyListing, SearchResults, SearchCriteria


def save_search_results(results: SearchResults) -> None:
    """Save search results to Apify key-value store.
    
    Args:
        results: Search results to save
    """
    # Convert results to dict for storage
    results_dict = results.model_dump()
    
    # Convert datetime objects to ISO format strings
    results_dict["search_date"] = results_dict["search_date"].isoformat()
    for i, result in enumerate(results_dict["results"]):
        if result.get("listed_date"):
            results_dict["results"][i]["listed_date"] = result["listed_date"].isoformat()
    
    try:
        # Save to Apify key-value store if in production
        if hasattr(Actor, 'main_kv_store'):
            Actor.main_kv_store.set_value("search_results", results_dict)
            
            # Also save the individual listings separately for easier access
            for listing in results.results:
                Actor.main_kv_store.set_value(f"listing_{listing.id}", listing.model_dump())
        else:
            # Local testing - save to a local file
            Actor.log.info("Running in local mode, saving to local file")
            os.makedirs("storage/key_value_stores", exist_ok=True)
            with open("storage/key_value_stores/search_results.json", "w") as f:
                json.dump(results_dict, f)
    except Exception as e:
        Actor.log.error(f"Error saving search results: {e}")


def load_previous_results(search_criteria: SearchCriteria) -> Optional[SearchResults]:
    """Load previous search results from Apify key-value store.
    
    Args:
        search_criteria: Current search criteria, to compare with previous search
        
    Returns:
        Previous search results, or None if no previous results or criteria changed
    """
    # Try to get previous results
    try:
        results_dict = None
        
        # Try to load from Apify KV store first
        if hasattr(Actor, 'main_kv_store'):
            results_dict = Actor.main_kv_store.get_value("search_results")
        
        # If not found or in local mode, try loading from local file
        if not results_dict and os.path.exists("storage/key_value_stores/search_results.json"):
            Actor.log.info("Loading from local file")
            with open("storage/key_value_stores/search_results.json", "r") as f:
                results_dict = json.load(f)
        
        if not results_dict:
            return None
        
        # Parse dates
        results_dict["search_date"] = datetime.fromisoformat(results_dict["search_date"])
        for i, result in enumerate(results_dict["results"]):
            if result.get("listed_date"):
                results_dict["results"][i]["listed_date"] = datetime.fromisoformat(
                    result["listed_date"]
                )
        
        # Convert back to model
        previous_results = SearchResults(**results_dict)
        
        # Check if search criteria has changed
        prev_criteria = previous_results.search_criteria
        if (
            prev_criteria.location != search_criteria.location
            or prev_criteria.property_type != search_criteria.property_type
            or prev_criteria.min_bedrooms != search_criteria.min_bedrooms
            or prev_criteria.max_bedrooms != search_criteria.max_bedrooms
            or prev_criteria.min_price != search_criteria.min_price
            or prev_criteria.max_price != search_criteria.max_price
            or prev_criteria.search_type != search_criteria.search_type
            or set(prev_criteria.sources) != set(search_criteria.sources)
            # Amenities might be in different order but same content
            or set(prev_criteria.amenities) != set(search_criteria.amenities)
        ):
            # Criteria changed, don't use previous results
            return None
        
        return previous_results
    
    except Exception as e:
        Actor.log.error(f"Error loading previous results: {e}")
        return None


def mark_new_listings(
    current_results: List[PropertyListing],
    previous_results: Optional[SearchResults]
) -> List[PropertyListing]:
    """Mark new listings in current results compared to previous results.
    
    Args:
        current_results: Current property listings
        previous_results: Previous search results, or None if no previous results
        
    Returns:
        Updated current property listings with is_new flag set
    """
    if not previous_results:
        # If no previous results, all are new
        for listing in current_results:
            listing.is_new = True
        return current_results
    
    # Get IDs of previous listings
    previous_ids = {listing.id for listing in previous_results.results}
    
    # Mark new listings
    for listing in current_results:
        if listing.id not in previous_ids:
            listing.is_new = True
    
    return current_results


def push_results_to_dataset(results: SearchResults) -> None:
    """Push search results to Apify dataset.
    
    Args:
        results: Search results to push
    """
    # Convert to simple dicts for the dataset
    listings_data = []
    for listing in results.results:
        listing_dict = listing.model_dump()
        # Convert complex types to strings for better compatibility
        listing_dict["address"] = str(listing.address)
        if listing.listed_date:
            listing_dict["listed_date"] = listing.listed_date.isoformat()
        listings_data.append(listing_dict)
    
    try:
        # Push each listing as a separate item
        Actor.push_data(listings_data)
    except Exception as e:
        Actor.log.error(f"Error pushing data to dataset: {e}")
        # In local mode, save to local file
        try:
            os.makedirs("storage/datasets/default", exist_ok=True)
            with open("storage/datasets/default/results.json", "w") as f:
                json.dump(listings_data, f)
            Actor.log.info("Saved results to local file")
        except Exception as e2:
            Actor.log.error(f"Error saving to local file: {e2}") 