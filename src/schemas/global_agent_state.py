from pydantic import BaseModel, ConfigDict
from typing import Dict, Optional, ClassVar
from asyncio import Queue, Future, AbstractEventLoop
from concurrent.futures import ThreadPoolExecutor

class GlobalAgentState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Declare these as ClassVars so that Pydantic doesn't treat them as model fields.
    thread_pool: ClassVar[Optional[ThreadPoolExecutor]] = None
    task_queue: ClassVar[Optional[Queue]] = None
    pending_tasks: ClassVar[Optional[Dict[str, Future]]] = None
    loop: ClassVar[Optional[AbstractEventLoop]] = None

    @classmethod
    def init(cls):
        """
        Initialize the GlobalAgentState with a ThreadPoolExecutor, if not already done.
        """
        if cls.thread_pool is None:
            cls.thread_pool = ThreadPoolExecutor(max_workers=100)
