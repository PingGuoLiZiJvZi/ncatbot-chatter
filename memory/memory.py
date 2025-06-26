from db.IndexDB import IndexDB
from db.SubMemory import PrivateMemory, GroupMemory
from ncatbot.core import GroupMessage, PrivateMessage
import yaml

class MemoryManager:
	def __init__(self):
		self.private_indexDB = IndexDB("db/private_index.db")
		self.group_indexDB = IndexDB("db/group_index.db")
		self.private_memory = []
		self.group_memory = []
		self.init_private_index()
		self.init_group_index()

	def init_private_index(self):
		private_index = self.private_indexDB.get_all_from_db()
		for uin, user_name in private_index:
			private_memory = PrivateMemory(uin, user_name)
			self.private_memory.append(private_memory)

	def init_group_index(self):
		group_index = self.group_indexDB.get_all_from_db()
		for group_id, group_name in group_index:
			group_memory = GroupMemory(group_id, group_name)
			self.group_memory.append(group_memory)

	async def add_private_memory(self, message: PrivateMessage):
		uin = message.user_id
		user_name = message.sender.nickname
		if not self.private_indexDB.select_from_db(uin):
			self.private_indexDB.add_to_db(uin, user_name)
			private_memory = PrivateMemory(uin, user_name)
			self.private_memory.append(private_memory)
		else:
			private_memory = next((m for m in self.private_memory if m.uin == uin), None)
		if private_memory:
			private_memory.add_to_memory(message)

	async def add_group_memory(self, message: GroupMessage):
		group_id = message.group_id
		try:
			with open("db/group_name.yaml", "r", encoding="utf-8") as f:
				file = yaml.safe_load(f)
				group_name = file.get(group_id, "群名未知")
		except FileNotFoundError:
			group_name = "群名未知"
			
		if not self.group_indexDB.select_from_db(group_id):
			self.group_indexDB.add_to_db(group_id, group_name)
			group_memory = GroupMemory(group_id, group_name)
			self.group_memory.append(group_memory)
		else:
			group_memory = next((m for m in self.group_memory if m.group_id == group_id), None)
		if group_memory:
			group_memory.add_to_memory(message)

	def get_all_private_memory(self):
		res = [memory.get_all() for memory in self.private_memory]
		print(res)
		return res
	
	def get_all_group_memory(self):
		res = [memory.get_all() for memory in self.group_memory]
		print(res)
		return res