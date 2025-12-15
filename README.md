# InnSight

Accommodation recommendation service that uses Chinese natural language queries to find and rank accommodations near points of interest in Japan and Taiwan.

## Features

- **Chinese NLP Parsing**: Extract POIs, locations, trip duration, and filter preferences from natural language queries
- **Geospatial Search**: Find accommodations within travel-time isochrones from your destination
- **Tier-Based Ranking**: Accommodations ranked by proximity (15/30/60 minute driving tiers)
- **Amenity Filtering**: Filter by parking, wheelchair accessibility, kid-friendly, and pet-friendly options
- **REST API**: FastAPI-based API with rate limiting, caching, and CORS support

## Installation

Requires Python 3.13+

```bash
# Clone the repository
git clone <repository-url>
cd innsight

# Install with Poetry
poetry install
```

## Configuration

```bash
cp .env.sample .env
```

| Variable | Description              |
|:---|:-------------------------|
| `ENV` | Current  environment     |
| `API_ENDPOINT` | Backend API endpoint     |
| `ORS_URL` | OpenRouteService API URL |
| `ORS_API_KEY` | OpenRouteService API key |
| `OVERPASS_URL` | Overpass API endpoint    |

## Usage

### API Server

```bash
# Or directly with uvicorn
poetry run uvicorn innsight.app:app --reload
```

## API Endpoints

### Recommendations

#### `POST /recommend`

Get accommodation recommendations based on a natural language query.

## External Services

InnSight integrates with the following services:

- **[Nominatim](https://nominatim.openstreetmap.org/)**: Geocoding service for POI lookup
- **[Overpass API](https://overpass-api.de/)**: OpenStreetMap data queries for accommodations
- **[OpenRouteService](https://openrouteservice.org/)**: Isochrone (travel time polygon) calculations

## License

See LICENSE file for details.