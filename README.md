# Listing Sleuth: Real Estate Listing Monitor

An agentic real estate listing monitor that helps users find properties that match their specific criteria. This agent scrapes data from popular real estate platforms such as Zillow, Realtor.com, and Apartments.com to provide up-to-date information on available properties.

## Features

- **Multi-source searching**: Simultaneously searches across multiple real estate platforms to find the most comprehensive results.
- **Customizable search criteria**: Filter by location, property type, price range, number of bedrooms, and desired amenities.
- **LLM-powered filtering**: Uses AI to understand user preferences and filter results beyond basic criteria.
- **Regular monitoring**: Runs on a schedule to identify new listings that match your criteria.
- **Detailed property information**: Provides comprehensive details on each property, including price, features, and location data.
- **Autonomous decision-making**: Makes intelligent decisions about which properties best match your criteria.

## How it works

1. **User input**: Specify your desired location, property type, price range, and other preferences.
2. **Data collection**: The agent scrapes data from selected real estate platforms using Apify's specialized actors.
3. **Intelligent filtering**: AI processes the raw data to identify properties that match your requirements, even understanding nuanced preferences.
4. **Results delivery**: Receive a structured report of matching properties, with links to the original listings.
5. **Continuous monitoring**: Run the agent regularly to identify new properties as they become available.

## Getting started

### Prerequisites

- Apify account
- (Optional) OpenAI API key for enhanced AI filtering

### Input parameters

- **Location**: The city or neighborhood to search in (e.g., "San Francisco, CA")
- **Property Type**: Type of property (apartment, house, condo, townhouse, or any)
- **Bedrooms**: Minimum and maximum number of bedrooms
- **Price Range**: Minimum and maximum price (in USD)
- **Amenities**: Desired features (e.g., "parking", "gym", "dishwasher")
- **Search Type**: Whether to search for rental or purchase properties
- **Data Sources**: Which real estate platforms to search (Zillow, Realtor.com, Apartments.com)
- **LLM API Token**: (Optional) OpenAI API token for enhanced filtering

## Example output

The output is a structured JSON report containing details of matching properties, including:

- Property title and address
- Price and number of bedrooms/bathrooms
- Links to original listings
- Available amenities
- Additional property details
- Indication of new listings since last search

## Pricing and Monetization

Listing Sleuth uses Apify's pay-per-event (PPE) pricing model. You will be charged based on the following events:

- **Search Initiated**: $0.10 per search - Charged when you start a new property search
- **Property Found**: $0.05 per property - Charged for each property that matches your criteria
- **Search Completed**: $0.30 per completion - Charged when a full search across all platforms is completed

This pricing model ensures you only pay for value received, rather than computation time or resources used.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Built for the Apify AI Agent competition.

## Python Crawlee with Playwright template

A template for [web scraping](https://apify.com/web-scraping) data from websites starting from provided URLs using Python. The starting URLs are passed through the Actor's input schema, defined by the [input schema](https://docs.apify.com/platform/actors/development/input-schema). The template uses [Crawlee for Python](https://crawlee.dev/python) for efficient web crawling, making requests via headless browser managed by [Playwright](https://playwright.dev/python/), and handling each request through a user-defined handler that uses [Playwright](https://playwright.dev/python/) API to extract data from the page. Enqueued URLs are managed in the [request queue](https://crawlee.dev/python/api/class/RequestQueue), and the extracted data is saved in a [dataset](https://crawlee.dev/python/api/class/Dataset) for easy access.

## Included features

- **[Apify SDK](https://docs.apify.com/sdk/python/)** - a toolkit for building Apify [Actors](https://apify.com/actors) in Python.
- **[Crawlee for Python](https://crawlee.dev/python/)** - a web scraping and browser automation library.
- **[Input schema](https://docs.apify.com/platform/actors/development/input-schema)** - define and validate a schema for your Actor's input.
- **[Request queue](https://crawlee.dev/python/api/class/RequestQueue)** - manage the URLs you want to scrape in a queue.
- **[Dataset](https://crawlee.dev/python/api/class/Dataset)** - store and access structured data extracted from web pages.
- **[Playwright](https://playwright.dev/python/)** - a library for managing headless browsers.

## Resources

- [Video introduction to Python SDK](https://www.youtube.com/watch?v=C8DmvJQS3jk)
- [Webinar introducing to Crawlee for Python](https://www.youtube.com/live/ip8Ii0eLfRY)
- [Apify Python SDK documentation](https://docs.apify.com/sdk/python/)
- [Crawlee for Python documentation](https://crawlee.dev/python/docs/quick-start)
- [Python tutorials in Academy](https://docs.apify.com/academy/python)
- [Integration with Make, GitHub, Zapier, Google Drive, and other apps](https://apify.com/integrations)
- [Video guide on getting scraped data using Apify API](https://www.youtube.com/watch?v=ViYYDHSBAKM)
- A short guide on how to build web scrapers using code templates:

[web scraper template](https://www.youtube.com/watch?v=u-i-Korzf8w)


## Getting started

For complete information [see this article](https://docs.apify.com/platform/actors/development#build-actor-locally). To run the actor use the following command:

```bash
apify run
```

## Deploy to Apify

### Connect Git repository to Apify

If you've created a Git repository for the project, you can easily connect to Apify:

1. Go to [Actor creation page](https://console.apify.com/actors/new)
2. Click on **Link Git Repository** button

### Push project on your local machine to Apify

You can also deploy the project on your local machine to Apify without the need for the Git repository.

1. Log in to Apify. You will need to provide your [Apify API Token](https://console.apify.com/account/integrations) to complete this action.

    ```bash
    apify login
    ```

2. Deploy your Actor. This command will deploy and build the Actor on the Apify Platform. You can find your newly created Actor under [Actors -> My Actors](https://console.apify.com/actors?tab=my).

    ```bash
    apify push
    ```

## Documentation reference

To learn more about Apify and Actors, take a look at the following resources:

- [Apify SDK for JavaScript documentation](https://docs.apify.com/sdk/js)
- [Apify SDK for Python documentation](https://docs.apify.com/sdk/python)
- [Apify Platform documentation](https://docs.apify.com/platform)
- [Join our developer community on Discord](https://discord.com/invite/jyEM2PRvMU)
