import json
import os
import sys
from pathlib import Path

# Add the project root directory to the Python path
current_path = Path(__file__).parent  # Gets the directory containing this file
project_root = current_path.parent.parent.parent  # Go up three levels to reach project root
src_path = project_root / 'src'  # Path to src directory

sys.path.append(str(project_root))
sys.path.append(str(src_path))

# Original imports with corrected paths
from src.services.whatsapp_services.basic_endpoints import WhatsAppServiceBasic
from src.services.whatsapp_services.handle_media import WhatsAppServiceMedia
from src.services.whatsapp_services.interactive_message import WhatsAppServiceInteractive
from src.services.whatsapp_services.special_messages import WhatsAppServiceSpecial
from src.services.http_requests.airtable.airtable_main_db import AirtableLatteDB
from src.services.http_requests.open_ai_service import OpenAIService
import json
import os
import requests
from agency_swarm.tools import BaseTool
from typing import List
from pydantic import Field
import asyncio


class SendLatteTeam(BaseTool):
    """
    SendLatteTeam es una herramienta que envía los datos de contacto del equipo de Latte Sessions
    al usuario. Utiliza esta herramienta cuando no puedas responder a una consulta y necesites 
    redirigir al usuario al equipo de Latte Sessions.
    """
    
    to: str = Field(..., description="El waid del usuario, el número de WhatsApp donde se enviará el contacto.")
    
    def run(self):
        """
        Envía los datos de contacto del equipo de Latte Sessions al número de WhatsApp especificado.
        """
        try:
            # Ejecutar la función asíncrona en el bucle de eventos
            respuesta = asyncio.run(self._enviar_contacto())
            return f"Contacto enviado exitosamente: {respuesta}"
        except Exception as e:
            return f"Error al enviar el contacto: {str(e)}"
    
    async def _enviar_contacto(self):
        """
        Método asíncrono auxiliar para enviar el mensaje de contacto.
        """
        contact = {
            "name": {
                "formatted_name": "Latte Team",
                "first_name": "Latte Team"
            },
            "phones": [{
                "phone": "573332739814",
                "type": "WHATSAPP",
                "wa_id": "573332739814"
            }],
            "urls": [{
                "url": "https://lattesessions.com/",
                "type": "WORK"
            }, {
                "url": "https://linktr.ee/lattesessions",
                "type": "WORK"
            }],
            "emails": [{
                "email": "hola@lattesessions.com",
                "type": "WORK"
            }],
            "org": {
                "company": "Latte Sessions",
                "department": "Customer Service",
                "title": "Support Team"
            }
        }
        return await WhatsAppServiceSpecial.send_contact_message(self.to, contact)
    
class SendReservationContact(BaseTool):
    """
    SendReservationContact es una herramienta que envía los datos de contacto del equipo de Reservas
    de Latte Sessions al usuario. Utiliza esta herramienta cuando el usuario necesite hacer una reserva
    o tenga consultas específicas sobre reservaciones.
    """
    
    to: str = Field(..., description="El waid del usuario, el número de WhatsApp donde se enviará el contacto.")
    
    def run(self):
        """
        Envía los datos de contacto del equipo de Reservas al número de WhatsApp especificado.
        """
        try:
            respuesta = asyncio.run(self._enviar_contacto())
            return f"Contacto de reservas enviado exitosamente: {respuesta}"
        except Exception as e:
            return f"Error al enviar el contacto de reservas: {str(e)}"
    
    async def _enviar_contacto(self):
        """
        Método asíncrono auxiliar para enviar el mensaje de contacto.
        """
        contact = {
            "name": {
                "formatted_name": "Latte Reservas",
                "first_name": "Latte Reservas"
            },
            "phones": [{
                "phone": "573332739836",
                "type": "WHATSAPP",
                "wa_id": "573332739836"
            }],
            "urls": [{
                "url": "https://lattesessions.com/",
                "type": "WORK"
            }, {
                "url": "https://linktr.ee/lattesessions",
                "type": "WORK"
            }],
            "emails": [{
                "email": "hola@lattesessions.com",
                "type": "WORK"
            }],
            "org": {
                "company": "Latte Sessions",
                "department": "Reservaciones",
                "title": "Equipo de Reservas"
            }
        }
        return await WhatsAppServiceSpecial.send_contact_message(self.to, contact)

class SendLocation(BaseTool):
    """
    SendLocation es una herramienta que envía una ubicación específica al usuario a través de WhatsApp.
    Utiliza esta herramienta cuando necesites compartir la ubicación del próximo Latte Sessions.
    """
    
    to: str = Field(..., description="El waid del usuario, el número de WhatsApp donde se enviará la ubicación.")
    latitude: float = Field(..., description="Latitud de la ubicación en grados decimales (entre -90 y 90)")
    longitude: float = Field(..., description="Longitud de la ubicación en grados decimales (entre -180 y 180)")
    name: str = Field(None, description="Nombre opcional del lugar (ejemplo: 'Latte Sessions Café')")
    address: str = Field(None, description="Dirección opcional del lugar")
    
    def run(self):
        """
        Envía un mensaje de ubicación al número de WhatsApp especificado.
        """
        try:
            respuesta = asyncio.run(self._enviar_ubicacion())
            return f"Ubicación enviada exitosamente: {respuesta}"
        except Exception as e:
            return f"Error al enviar la ubicación: {str(e)}"
    
    async def _enviar_ubicacion(self):
        """
        Método asíncrono auxiliar para enviar el mensaje de ubicación.
        """
        return await WhatsAppServiceSpecial.send_location(
            to=self.to,
            latitude=self.latitude,
            longitude=self.longitude,
            name=self.name,
            address=self.address
        )

class OptOutFlow(BaseTool):
    pass



# Reservas-> +57 333 2739836
# latte Team -> +57 333 2739814