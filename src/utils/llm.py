"""LLM utility functions for Listing Sleuth."""

import os
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.schema import Document

from ..models.property import PropertyListing, SearchCriteria


def get_llm(api_token: Optional[str] = None) -> ChatOpenAI:
    """Get LLM client.
    
    Args:
        api_token: OpenAI API token. If None, tries to get from environment.
        
    Returns:
        ChatOpenAI instance
    
    Raises:
        ValueError: If API token is not provided and not found in environment.
    """
    token = api_token or os.environ.get("OPENAI_API_KEY")
    if not token:
        raise ValueError(
            "OpenAI API token not provided. Please provide a token in the input "
            "or set the OPENAI_API_KEY environment variable."
        )
    
    return ChatOpenAI(
        api_key=token,
        model="gpt-3.5-turbo",
        temperature=0
    )


def filter_properties_with_llm(
    properties: List[PropertyListing],
    search_criteria: SearchCriteria,
    api_token: Optional[str] = None
) -> List[PropertyListing]:
    """Filter properties with LLM based on search criteria.
    
    Args:
        properties: List of property listings
        search_criteria: Search criteria
        api_token: OpenAI API token
        
    Returns:
        Filtered list of property listings
    """
    if not properties:
        return []
    
    if not api_token and not search_criteria.llm_api_token:
        # Without a token, just do basic filtering
        return properties
    
    llm = get_llm(api_token or search_criteria.llm_api_token)
    parser = PydanticOutputParser(pydantic_object=PropertyListing)
    
    template = """
    You are an AI assistant helping to filter real estate listings based on specific criteria.
    
    The user is looking for the following:
    - Location: {location}
    - Property type: {property_type}
    - Price range: ${min_price} - ${max_price} (0 means no minimum, None means no maximum)
    - Bedrooms: {min_bedrooms} - {max_bedrooms} (None means no maximum)
    - Desired amenities: {amenities}
    
    For each property, evaluate how well it fits the criteria, with special attention to amenities
    and any specific requirements. Return the property object unmodified if it's a good match,
    filtering out properties that don't meet the criteria.
    
    Here are the properties to evaluate:
    {properties}
    
    If the user mentioned any amenities, prioritize properties with those amenities.
    """
    
    # Process in smaller batches to avoid token limits
    batch_size = 5
    filtered_properties = []
    
    for i in range(0, len(properties), batch_size):
        batch = properties[i:i+batch_size]
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | llm
        
        # Simplify property objects for LLM consumption
        simplified_batch = [
            {
                "id": p.id,
                "title": p.title,
                "price": p.price,
                "bedrooms": p.bedrooms,
                "bathrooms": p.bathrooms,
                "property_type": p.property_type,
                "address": str(p.address),
                "amenities": p.amenities,
                "description": p.description,
                "url": str(p.url)
            }
            for p in batch
        ]
        
        result = chain.invoke({
            "location": search_criteria.location,
            "property_type": search_criteria.property_type,
            "min_price": search_criteria.min_price,
            "max_price": search_criteria.max_price,
            "min_bedrooms": search_criteria.min_bedrooms,
            "max_bedrooms": search_criteria.max_bedrooms,
            "amenities": search_criteria.amenities,
            "properties": simplified_batch
        })
        
        # Extract property IDs that the LLM determined to be good matches
        response_text = result.content
        passing_ids = []
        
        # Simple parsing of response - in production, this would be more robust
        for line in response_text.split("\n"):
            if "id:" in line and "good match" in line.lower():
                try:
                    id_part = line.split("id:")[1].strip()
                    property_id = id_part.split()[0].strip(",")
                    passing_ids.append(property_id)
                except IndexError:
                    continue
        
        # Add matching properties to filtered list
        for p in batch:
            if p.id in passing_ids:
                filtered_properties.append(p)
    
    return filtered_properties


def summarize_property(
    property_listing: PropertyListing,
    api_token: Optional[str] = None
) -> str:
    """Generate a natural language summary of a property.
    
    Args:
        property_listing: Property listing to summarize
        api_token: OpenAI API token
        
    Returns:
        Summary of property
    """
    try:
        llm = get_llm(api_token)
    except ValueError:
        # Fall back to basic summary if no API token
        return (
            f"{property_listing.title}: {property_listing.bedrooms} bed, "
            f"{property_listing.bathrooms or 'unknown'} bath {property_listing.property_type} "
            f"for ${property_listing.price:,.2f} in {property_listing.address.city}, "
            f"{property_listing.address.state}."
        )
    
    template = """
    Create a concise, appealing summary of this property listing in one paragraph:
    
    Title: {title}
    Price: ${price}
    Address: {address}
    Property type: {property_type}
    Bedrooms: {bedrooms}
    Bathrooms: {bathrooms}
    Square feet: {square_feet}
    Amenities: {amenities}
    Description: {description}
    
    Keep the summary brief but informative, highlighting key selling points.
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm
    
    result = chain.invoke({
        "title": property_listing.title,
        "price": f"{property_listing.price:,.2f}",
        "address": str(property_listing.address),
        "property_type": property_listing.property_type,
        "bedrooms": property_listing.bedrooms,
        "bathrooms": property_listing.bathrooms or "unknown",
        "square_feet": property_listing.square_feet or "unknown",
        "amenities": ", ".join(property_listing.amenities) or "none specified",
        "description": property_listing.description or "No description provided"
    })
    
    return result.content.strip() 