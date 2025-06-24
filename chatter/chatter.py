from memory.memory import Memory
from ncatbot.core import BotClient, GroupMessage, PrivateMessage
from ncatbot.utils import get_log
class Chatter:
	def __init__(self):
		self.memory = Memory()
		self.bot = BotClient()
		self._log = get_log()
	
		@self.bot.group_event()
		async def on_group_message(msg: GroupMessage):
			self._log.info(msg)
			if msg.raw_message == "测试":
				await msg.reply(text="NcatBot 测试成功喵~")

		@self.bot.private_event()
		async def on_private_message(msg: PrivateMessage):
			self._log.info(msg)
			if msg.raw_message == "测试":
				await self.bot.api.post_private_msg(msg.user_id, text="NcatBot 测试成功喵~")
		
		self.bot.run(bt_uin=3871740788,root=3040802074)


	def add_private_message(self, user_id: str, content: str):
		self.memory.add_private_message(user_id, content)

	def add_group_message(self, group_id: str, content: str):
		self.memory.add_group_message(group_id, content)

	def get_private_memory(self, user_id: str):
		for memory in self.private_memory:
			if memory.id == user_id:
				return memory.get_all_messages()
		return None

	def get_group_memory(self, group_id: str):
		for memory in self.group_memory:
			if memory.id == group_id:
				return memory.get_all_messages()
		return None

