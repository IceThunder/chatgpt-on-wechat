import plugins
import time
from bridge.context import ContextType
from bridge.reply import ReplyType
from plugins import *
from common.log import logger
from config import pconf

@plugins.register(name="DialogueArchiver", desc="将对话数据保存到 Elasticsearch 或 MongoDB", version="0.8", author="gemini")
class DialogueArchiver(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.handlers[Event.ON_DECORATE_REPLY] = self.on_decorate_reply
        self.storage_type = None
        self.mongo_collection = None

        try:
            archiver_config = pconf("DialogueArchiver")
            if not archiver_config:
                logger.info("[DialogueArchiver] No config found, plugin disabled.")
                return

            self.storage_type = archiver_config.get("storage_type")
            logger.info(f"[DialogueArchiver] Storage type set to: {self.storage_type}")

            if self.storage_type == "mongodb":
                mongo_config = archiver_config.get("mongodb", {})
                if mongo_config.get("enabled", False):
                    from pymongo import MongoClient
                    client = MongoClient(mongo_config.get("uri", "mongodb://localhost:27017/"),
                                       username=mongo_config.get("username"),
                                       password=mongo_config.get("password"))
                    db = client[mongo_config.get("database", "chatgpt-on-wechat")]
                    self.mongo_collection = db[mongo_config.get("collection", "dialogues")]
                    logger.info("[DialogueArchiver] MongoDB client initialized")
            # Omitted elasticsearch for brevity as it's not being used

        except Exception as e:
            logger.error(f"[DialogueArchiver] Error initializing storage client: {e}", exc_info=True)

        logger.info("[DialogueArchiver] initialized")

    def on_handle_context(self, e_context: EventContext):
        if self.mongo_collection is None:
            return
        
        context = e_context['context']
        if context.type != ContextType.TEXT:
            return

        session_id = context.get("session_id")
        if not session_id:
            return

        dialogue = [{
            "role": "user",
            "content": context.content,
            "timestamp": context.get("create_time", time.time())
        }]
        
        try:
            self.mongo_collection.insert_one({
                "session_id": session_id,
                "dialogue": dialogue,
                "timestamp": time.time()
            })
            logger.info(f"[DialogueArchiver] User input for session {session_id} saved to MongoDB.")
        except Exception as e:
            logger.error(f"[DialogueArchiver] Error saving user input to MongoDB: {e}", exc_info=True)

    def on_decorate_reply(self, e_context: EventContext):
        if self.mongo_collection is None:
            return
            
        reply = e_context['reply']
        context = e_context['context']
        if reply.type != ReplyType.TEXT:
            return

        session_id = context.get("session_id")
        if not session_id:
            return

        bot_reply = {
            "role": "bot",
            "content": reply.content,
            "timestamp": time.time()
        }

        try:
            self.mongo_collection.update_one(
                {"session_id": session_id},
                {"$push": {"dialogue": bot_reply}}
            )
            logger.info(f"[DialogueArchiver] Bot reply for session {session_id} updated in MongoDB.")
        except Exception as e:
            logger.error(f"[DialogueArchiver] Error updating bot reply to MongoDB: {e}", exc_info=True)

    def get_help_text(self, **kwargs):
        return "将对话数据保存到 Elasticsearch 或 MongoDB"