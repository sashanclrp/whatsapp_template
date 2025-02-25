from datetime import datetime
from utils.logger import logger
import pytz

class HelperFunctions:
    @staticmethod
    async def format_date_friendly(iso_date_str: str) -> str:
        """
        Converts ISO date string to a friendly Spanish format.
        Example: '2025-01-16T15:04:09.000Z' -> '16 de enero del 2025'
        """
        try:
            # Parse the ISO date string
            dt = datetime.fromisoformat(iso_date_str.replace('Z', '+00:00'))
            
            # Convert to Spanish month name
            months = {
                1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
                5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
                9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
            }
            
            # Format the date
            return f"{dt.day} de {months[dt.month]} del {dt.year}"
        except Exception as e:
            logger.error(f"Error formatting date {iso_date_str}: {str(e)}")
            return iso_date_str  # Return original string if parsing fails
