import sqlite3
from db.BaseDB import BaseDB
from llm.LLM import ConcentrateLLM
from ncatbot.core import GroupMessage, PrivateMessage
from datetime import datetime
import yaml
import threading
import os
#subMemory也是一个抽象类
class SubMemory(BaseDB):
	def __init__(self):
		super().__init__()
		self.llm = ConcentrateLLM()
		self.unread_memory = []
		self.lock = threading.Lock()
		self.read_memory = []
		self.pending_memory = []
		with open("config.yaml", "r", encoding="utf-8") as f:
			self.max_length = int(yaml.safe_load(f)["max_length"])
	
	def add_to_memory(self, message: GroupMessage | PrivateMessage):
		raise NotImplementedError("This method should be implemented by subclasses.")
	
	def get_all(self)->dict:
		raise NotImplementedError("This method should be implemented by subclasses.")
	
	def add_self_message(self,message:dict):
		raise NotImplementedError("This method should be implemented by subclasses.")

	
	def process_after_read(self):
		print("Processing after read...")
		if len(self.read_memory) > self.max_length:
			message = self.llm.generate_response(self.unread_memory, self.read_memory, self.pending_memory, self.get_all_from_db())
			print("Generated message:", message)
			self.clear_db()
			self.add_to_db(message)
			with self.lock:
				self.pending_memory = list(self.read_memory)
				self.read_memory.clear()
				
	
#在记忆中，仅有长期记忆保存在数据库中，以时间戳+内容的形式存储
#短期群聊记忆保存为发送时间，消息id，发送人id，发送人昵称，发送人群昵称，发送内容的字典形式
#短期私聊记忆保存为发送时间，消息id，发送内容的字典形式
class PrivateMemory(SubMemory):
	def __init__(self, uin, user_name):
		super().__init__()
		self.uin = uin
		self.user_name = user_name

		if not os.path.exists("db/private_memory"):
			os.makedirs("db/private_memory")

		self.path = f"db/private_memory/{self.uin}.db"
		self.conn = sqlite3.connect(self.path,check_same_thread=False)
		self.cursor = self.conn.cursor()
		self.cursor.execute('''CREATE TABLE IF NOT EXISTS private_memory (
			timestamp TEXT PRIMARY KEY,
			content TEXT NOT NULL
		)''')
		self.conn.commit()

	def add_self_message(self, message):
		try:
			if(message["聊天类型"] == "私聊" and message["聊天id"] == str(self.uin)):
				message.pop("聊天类型", None)
				message.pop("聊天id", None)
				message.pop("行动类型", None)  # 移除行动类型键
				dict_message = {
					"description": "请注意:这是你发送的消息",
					"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
					"content": str(message)
				}
				with self.lock:
					self.read_memory.append(dict_message)
		except KeyError as e:
			print(f"KeyError: {e} in add_self_message method of PrivateMemory class. Message: {message}")

	def add_to_memory(self, message: PrivateMessage):
		text = ""
		for mess in message.message:
			if(mess['type'] == 'text'):
				text = mess['data']['text']
		dict_message = {
			"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
			"message_id": message.message_id,
			"content": text
		}
		with self.lock:
			self.unread_memory.append(dict_message)

	def get_all_from_db(self, *args, **kwargs):
		self.cursor.execute('SELECT * FROM private_memory')
		return self.cursor.fetchall()
	 
	def add_to_db(self, *args, **kwargs):
		string = args[0]
		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		self.cursor.execute('INSERT INTO private_memory (timestamp, content) VALUES (?, ?)', (timestamp, string))
		self.conn.commit()	

	def clear_db(self, *args, **kwargs):
		self.cursor.execute('DELETE FROM private_memory')
		self.conn.commit()

	def get_all(self):
		dict={}
		dict["描述"] = f"私聊记忆,用户:{self.user_name},QQ号:{self.uin}"
		dict["未读记忆"] = list(self.unread_memory)
		dict["已读记忆"] = list(self.read_memory)
		dict["待存记忆"] = self.pending_memory
		dict["长期记忆"] = self.get_all_from_db()
		with self.lock:
			self.read_memory.extend(self.unread_memory)
			self.unread_memory.clear()
		return dict

#在记忆中，仅有长期记忆保存在数据库中，以时间戳+内容的形式存储
class GroupMemory(SubMemory):
	def __init__(self, group_id, group_name):
		super().__init__()
		self.group_id = group_id
		self.group_name = group_name
		
		if not os.path.exists("db/group_memory"):
			os.makedirs("db/group_memory")

		self.path = f"db/group_memory/{self.group_id}.db"
		self.conn = sqlite3.connect(self.path,check_same_thread=False)
		self.cursor = self.conn.cursor()
		self.cursor.execute('''CREATE TABLE IF NOT EXISTS group_memory (
			timestamp TEXT PRIMARY KEY,
			content TEXT NOT NULL
		)''')
		self.conn.commit()

	def add_to_memory(self, message: GroupMessage):
		text = ""
		for mess in message.message:
			if(mess['type'] == 'text'):
				text = mess['data']['text']
		dict_message = {
			"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
			"message_id": message.message_id,
			"user_id": message.sender.user_id,
			"user_nickname": message.sender.nickname,
			"group_nickname": message.sender.card,
			"content": text
		}
		with self.lock:
			self.unread_memory.append(dict_message)

	def clear_db(self, *args, **kwargs):
		self.cursor.execute('DELETE FROM group_memory')
		self.conn.commit()

	def add_self_message(self, message):
		try:
			if(message["聊天类型"] == "群聊" and message["聊天id"] == str(self.group_id)):
				message.pop("聊天类型", None)  # 移除聊天类型键
				message.pop("聊天id", None)  # 移除聊天id键
				message.pop("行动类型", None)  # 移除行动类型键
				dict_message = {
					"description": "请注意:这是你发送的消息",
					"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
					"content": str(message)
				}
				with self.lock:
					self.read_memory.append(dict_message)
		except KeyError as e:
			print(f"KeyError: {e} in add_self_message method of GroupMemory class. Message: {message}")

	def get_all_from_db(self, *args, **kwargs):
		self.cursor.execute('SELECT * FROM group_memory')
		return self.cursor.fetchall()
	
	def add_to_db(self, *args, **kwargs):
		string = args[0]
		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		self.cursor.execute('INSERT INTO group_memory (timestamp, content) VALUES (?, ?)', (timestamp, string))
		self.conn.commit()	

	def get_all(self):
		dict={}
		dict["描述"] = f"群聊记忆,群名:{self.group_name},群号:{self.group_id}"
		dict["未读记忆"] = list(self.unread_memory)
		dict["已读记忆"] = list(self.read_memory)
		dict["待存记忆"] = self.pending_memory
		dict["长期记忆"] = self.get_all_from_db()
		with self.lock:
			self.read_memory.extend(self.unread_memory)
			self.unread_memory.clear()
		return dict