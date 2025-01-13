from sncl import airtable as at
from config.env import AIRTABLE_API_KEY
from utils.logger import logger

class AirtableService:
    
    base_id = "appCEmKh65yHFkUhK"
    table_id = "tblUtCZvAqtkn264n"

    @classmethod
    async def register_user_airtable(cls, to: str, data: dict):
        """
        Register user data in Airtable.
        
        Args:
            to (str): WhatsApp number of the user
            data (dict): User registration data from MessageHandler
        """
        
        
        # Map the registration data to Airtable fields
        airtable_record = {
            "fields": {
                "Nombre": data['full_name'],
                "# de Identificación": int(data['id_number']),  # Fixed typo in field name
                "Tipo de Identificación": {
                    "CC": "Cédula de Ciudadanía",
                    "CE": "Cédula de Extranjería",
                    "PASAPORTE": "Pasaporte"
                }[data['id_type']],
                "Fecha de Nacimiento": data['birth_date'],
                "WhatsApp": int(to),  # Convert WhatsApp number to integer
                "Notas": data['more_about'],
                "Tratamiento De Datos": "Autorizo"  # Set when user accepts data policy
            }
        }
        
        try:
            # Create record in Airtable
            result = at.create_airtable_records(
                base_id=cls.base_id,
                table_id=cls.table_id,
                api_key=AIRTABLE_API_KEY,
                records=airtable_record,
                typecast=True  # Enable typecast for automatic data conversion
            )
            
            return result
            
        except Exception as e:
            raise Exception(f"Error creating Airtable record: {str(e)}")
    
    @classmethod
    async def get_registered_user(cls, to: str):
        """
        Get user data from Airtable by WhatsApp number.
        
        Args:
            to (str): WhatsApp number of the user
            
        Returns:
            dict: User data if found, None if not found
        """
        try:
            # Create filter formula to match WhatsApp number
            filter_formula = f"{{WhatsApp}}={to}"
            
            # Fetch records from Airtable using class variables
            result = at.fetch_filtered_airtable_records(
                base_id=cls.base_id,
                table_id=cls.table_id,
                airt_token=AIRTABLE_API_KEY,
                filter_formula=filter_formula,
                json_format=True
            )
            
            # Check if any records were found
            if result and len(result.get('records', [])) > 0:
                # Return all matching records
                return result['records']
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching user from Airtable: {str(e)}")
            raise Exception(f"Error fetching user data: {str(e)}")
