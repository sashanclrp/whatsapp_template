import os
import json
import sys
from pathlib import Path
from typing import Optional, Dict
from agency_swarm import Agent, Agency, set_openai_key
from agency_swarm.tools.oai.FileSearch import FileSearch
from openai.types.beta.assistant import ToolResources, ToolResourcesFileSearch
import asyncio
import nest_asyncio
nest_asyncio.apply()

from utils.logger import logger
from utils.redis.redis_handler import RedisHandler

from .prompts import ZomaAgentPrompts
from .helper_functions import VectorStoreHelper, UserContextFile
from .tools import SendLatteTeam, SendReservationContact, OptOutFlow, SendLocation
from .user_threads import UserThreads

from schemas.global_agent_state import GlobalAgentState

class ZomaAgency():
    @staticmethod
    async def zoma_whatsapp_agency(
        api_key: str,
        user_data: dict,
        user_message_text: str,
        verbose: bool = False
    ) -> Dict[str, str]:
        def blocking_agency_call():
            try:
                set_openai_key(api_key)

                # Synchronously retrieve (or create) the vector store id on the main loop
                memory_dir = Path(__file__).parent / 'memory'
                future_vector = asyncio.run_coroutine_threadsafe(
                    VectorStoreHelper.get_or_create_vector_store_for_directory(
                        str(memory_dir),
                        "Latte Sessions Memory"
                    ),
                    GlobalAgentState.loop
                )
                vector_store_id = future_vector.result()
                logger.debug(f"Vector store ID: {vector_store_id}")

                # Prepare tool resources
                tool_resources = ToolResources(
                    file_search=ToolResourcesFileSearch(
                        vector_store_ids=[vector_store_id]
                    )
                )

                zoma_agent = Agent(
                    name="Zoma Agent",
                    description=ZomaAgentPrompts.zoma_agent_description(),
                    instructions=ZomaAgentPrompts.zoma_agent_instructions(),
                    model="gpt-4o-mini",
                    temperature=1,
                    tools=[FileSearch, SendLocation],
                    tool_resources=tool_resources.model_dump()
                )

                def sync_load():
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            UserThreads.load_threads(user_waid=user_data.get('waid')),
                            GlobalAgentState.loop
                        )
                        return future.result()
                    except Exception as e:
                        logger.error(f"Error in sync_load: {str(e)}")
                        return {}

                def sync_save(thread_data):
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            UserThreads.save_threads(user_waid=user_data.get('waid'), new_threads=thread_data),
                            GlobalAgentState.loop
                        )
                        future.result()
                    except Exception as e:
                        logger.error(f"Error in sync_save: {str(e)}")

                agency = Agency(
                    [zoma_agent],
                    threads_callbacks={"load": sync_load, "save": sync_save},
                    shared_instructions=ZomaAgentPrompts.zoma_agency_mission(),
                    temperature=1
                )

                try:
                    if user_data.get('session_status') == "New Session":
                        response = agency.get_completion(
                            message=f"waid:{user_data.get('waid')} \n\n {user_message_text}",
                            verbose=verbose,
                            message_files=[user_data.get('user_context_file_id')]
                        )
                        future_update = asyncio.run_coroutine_threadsafe(
                            RedisHandler.update_user_field(user_data.get('waid'), "session_status", "Active Session"),
                            GlobalAgentState.loop
                        )
                        future_update.result()
                    else:
                        response = agency.get_completion(
                            message=f"waid:{user_data.get('waid')} \n\n {user_message_text}",
                            verbose=verbose
                        )
                except Exception as exc:
                    logger.error(f"Error in agency completion, creating new thread: {str(exc)}")
                    future_delete = asyncio.run_coroutine_threadsafe(
                        UserThreads.delete_threads(user_data.get('waid')),
                        GlobalAgentState.loop
                    )
                    future_delete.result()

                    response = agency.get_completion(
                        message=f"waid:{user_data.get('waid')} \n\n {user_message_text}",
                        verbose=verbose,
                        message_files=[user_data.get('user_context_file_id')]
                    )

                if isinstance(response, dict) and "error" in response:
                    return {"message": f"Lo siento, hubo un error: {response['error']}"}
                elif isinstance(response, str):
                    return {"message": response}
                return response

            except Exception as e:
                err_msg = f"Lo siento, hubo un error: {str(e)}"
                logger.error(err_msg)
                return {"message": err_msg}

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(GlobalAgentState.thread_pool, blocking_agency_call)
        return result

    @staticmethod
    async def simulate_conversation(api_key: str):
        """Simulates a conversation with the TixTek agent in the terminal."""
        # Get user phone number at the start
        # phone_number = input("Please enter your phone number: ")
        phone_number = "573168227670"
        # Create user data structure
        user_data = {
            "waid": phone_number,
            "full_name": "Sasha Canal",
            "birth_date": "1990-01-01",
            "more_about": "I love coffee and music",
            "record_id": "recidCH4GG5AVMFSU"
        }
        
        print("\nStart chatting with Zoma Agent (type 'exit' to end conversation)")
        print("-" * 50)
        
        while True:
            # Get user input
            user_message = input("\nYou: ").strip()
            
            if user_message.lower() == 'exit':
                print("\nEnding conversation. Goodbye!")
                break
                
            # Get agent response
            response = await ZomaAgency.zoma_whatsapp_agency(api_key, user_data, user_message, verbose=False)
            
            # Handle the response
            if "error" in response:
                print(f"\nAgent: Error - {response['error']}")
            else:
                print(f"\nAgent: {response['message']}")