"""CLI entry point for innsight command."""

import argparse
from typing import List, Optional
import sys

# Import modules from the same package
from .config import AppConfig
from .services import AccommodationSearchService
from .exceptions import GeocodeError, ParseError, ConfigurationError


def _setup_argument_parser() -> argparse.ArgumentParser:
    """Setup and return command line argument parser."""
    parser = argparse.ArgumentParser(
        prog='innsight',
        description='innsight <query>',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('query', help='完整中文需求句')
    return parser


def _output_results(gdf) -> None:
    """Output results to stdout."""
    accommodation_count = len(gdf)
    print(f"找到 {accommodation_count} 筆住宿")
    
    if accommodation_count > 0:
        for _, row in gdf.iterrows():
            name = row.get('name', 'Unknown')
            tier = row.get('tier', 0)
            print(f"name: {name}, tier: {tier}")


def _create_search_service() -> AccommodationSearchService:
    """Factory function to create and configure the search service."""
    config = AppConfig.from_env()
    return AccommodationSearchService(config)


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    # Setup argument parser
    parser = _setup_argument_parser()
    
    if argv is None:
        argv = sys.argv[1:]
    
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code or 0
    
    try:
        # Initialize service through dependency injection
        search_service = _create_search_service()
        
        # Search for accommodations
        gdf = search_service.search_accommodations(args.query)
        
        # Output results
        _output_results(gdf)
        
        return 0
        
    except ValueError as e:
        # Handle environment validation errors from AppConfig.from_env()
        print(str(e), file=sys.stderr)
        return 1
    except ConfigurationError as e:
        print(str(e), file=sys.stderr)
        return 1
    except ParseError as e:
        print(str(e), file=sys.stderr)
        return 1
    except GeocodeError as e:
        print("找不到地點", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())